"""Render the public evidence-timing action ledger without making model calls."""
import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path


CASES = ("dateutil", "cpython")
STATES = ("defective", "correct")
TIMINGS = ("early", "late")
REPEATS = (1, 2)
TITLES = {"dateutil": "dateutil", "cpython": "CPython", "early": "до", "late": "после",
          "defective": "дефектный", "correct": "правильный"}


def table_value(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def index_episodes(data):
    roster = data["roster"]
    if not roster or len(set(roster)) != len(roster):
        raise ValueError("Expected distinct scheduled model names")
    index = dict.fromkeys(product(roster, CASES, STATES, TIMINGS, REPEATS))
    ids = set()
    for episode in data["episodes"]:
        key = tuple(episode[k] for k in ("model", "case", "state", "timing", "repeat"))
        eid = episode["episode_id"]
        if key not in index or index[key] is not None or eid in ids:
            raise ValueError("Unexpected or duplicate episode")
        ids.add(eid)
        current, correct = episode["start_variant"], episode["state"] == "correct"
        steps = episode["steps"]
        if len(steps) > 2:
            raise ValueError("Too many decisions")
        for position, s in enumerate(steps, 1):
            if s["decision"] != position:
                raise ValueError("Nonconsecutive decision indices")
            if s["status"] != "OK":
                if s.get("correct_after") is not None or s.get("after_variant") is not None or position != len(steps):
                    raise ValueError("Invalid step has an outcome or a later decision")
                continue
            if (s["before_variant"] != current or s["correct_before"] is not correct
                    or type(s["correct_after"]) is not bool or not s["after_variant"]):
                raise ValueError("Invalid candidate transition")
            if ((s["action"] == "keep" and s["after_variant"] != current)
                    or (s["action"] != "keep" and s["after_variant"] != s["action"])
                    or (s["after_variant"] == current and s["correct_after"] != correct)):
                raise ValueError("Action and graded variant disagree")
            expected_exposure = episode["timing"] == "early" or position == 2
            if s["observed_diagnostic_before"] is not expected_exposure:
                raise ValueError("Initial observation delivered at wrong time")
            current, correct = s["after_variant"], s["correct_after"]
        index[key] = episode
    return index


def step_at(episode, stage):
    if episode and len(episode["steps"]) >= stage:
        return episode["steps"][stage - 1]
    return None


def truth(episode, stage):
    step = step_at(episode, stage)
    return step["correct_after"] if step and step["status"] == "OK" else None


def outcomes(group, stage, state):
    observed = [value for row in group if (value := truth(row, stage)) is not None]
    event = state == "defective"
    return f"{observed.count(event)}/{len(observed)}" if observed else "—"


def describe_step(episode, stage):
    step = step_at(episode, stage)
    if not step:
        return "—"
    if step["status"] != "OK":
        return table_value(step["status"])
    mark = "✓" if step["correct_after"] else "×"
    return f"{table_value(step['action'])} → {table_value(step['after_variant'])} {mark}"


def render(data):
    index = index_episodes(data)
    models = data["roster"]
    all_rows = list(index.values())
    coverage = [sum(truth(row, j) is not None for row in all_rows) for j in (1, 2)]
    lines = ["# Когда результат проверки меняет решение агента", "",
             f"План охватывает {len(models)} модели, два проекта и {len(all_rows)} эпизода. "
             f"По контрольным входам оценено {coverage[0]}/{len(all_rows)} первых и "
             f"{coverage[1]}/{len(all_rows)} вторых решений. Каждый эпизод предусматривает две возможности "
             "выбрать один из предложенных вариантов кода или сохранить текущий.", "",
             "При калибровке каждый вариант реализации выполнили на отложенных входах. При экспорте журнала "
             "калибровку повторили. Для каждого решения ответ модели связывается с оценкой выбранного "
             "варианта. [Исполненные варианты и контрольные входы](calibration.json) · [План](plan.json) · "
             "[Журнал решений](results.json)", "",
             "В группе «до» агент видел результат отдельной проверки исходного кода перед первым решением. "
             "В группе «после» он получал тот же результат только после первого решения. "
             "Первое решение служит основным сравнением. Второй выбор показывает состояние кода "
             "после того, как обе группы увидели исходное наблюдение.", "",
             "## Исправления и поломки", "",
             "В числителе — число исправленных дефектных или испорченных правильных стартов, в знаменателе — "
             "число оценённых эпизодов этой группы. Итог относится к состоянию после второго решения. "
             "Пропущенный второй выбор оставляет итог неизвестным. Правка, сохранившая правильное поведение, "
             "не считается поломкой.", "",
             "| Модель | Проект | Проверка | Исправлено сразу | Исправлено к концу | Сломано сразу | Сломано к концу |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for model, case, timing in product(models, CASES, TIMINGS):
        cells = []
        for state, stage in product(STATES, (1, 2)):
            group = [index[model, case, state, timing, rep] for rep in REPEATS]
            cells.append(outcomes(group, stage, state))
        lines.append("| " + " | ".join([table_value(model), TITLES[case], TITLES[timing], *cells]) + " |")
    for timing in TIMINGS:
        cells = [outcomes([v for (_, _, s, arm, _), v in index.items() if s == state and arm == timing],
                          stage, state) for state, stage in product(STATES, (1, 2))]
        lines.append("| Все модели | Оба проекта | " + TITLES[timing] + " | " + " | ".join(cells) + " |")

    lines += ["", "## Что произошло с изначально рабочим кодом при первом выборе", "",
              "Сохранение включает явное `keep` и выбор того же варианта. Поведенчески корректное "
              "переписывание означает выбор другого исходного кода, прошедшего все отложенные проверки.", "",
              "| Модель | Проект | Проверка | Оценено | Без изменения кода | Корректное переписывание | Поломка |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for model, case, timing in product(models, CASES, TIMINGS):
        choices = [step_at(index[model, case, "correct", timing, rep], 1) for rep in REPEATS]
        valid = [s for s in choices if s and s["status"] == "OK"]
        same = sum(s["before_variant"] == s["after_variant"] for s in valid)
        harmless = sum(s["before_variant"] != s["after_variant"] and s["correct_after"] for s in valid)
        damage = sum(not s["correct_after"] for s in valid)
        lines.append("| " + " | ".join(map(str, [table_value(model), TITLES[case], TITLES[timing],
                                                len(valid), same, harmless, damage])) + " |")

    lines += ["", "## Что изменилось в сопоставимых парах", "",
              "Пара фиксирует модель, проект, старт и номер повтора. «Только до» и «только после» означают, "
              "что указанное событие произошло лишь при одном времени предъявления. Совпадения включают "
              "как наличие события в обеих ветвях, так и его отсутствие в обеих.", "",
              "| Решение | Событие | Полных пар / назначено | Только до | Только после | Совпадений |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    disagreements = []
    for stage, state in product((1, 2), STATES):
        different = Counter()
        complete = 0
        event = state == "defective"
        for model, case, rep in product(models, CASES, REPEATS):
            rows = [index[model, case, state, timing, rep] for timing in TIMINGS]
            early, late = [truth(row, stage) for row in rows]
            if early is None or late is None:
                continue
            complete += 1
            if early == late:
                continue
            winning = "early" if early == event else "late"
            different[winning] += 1
            disagreements.append(f"- {table_value(model)}, {TITLES[case]}, {TITLES[state]} старт, повтор {rep}, "
                                 f"решение {stage}: до — {describe_step(rows[0], stage)}, "
                                 f"после — {describe_step(rows[1], stage)}.")
        label = "Исправление" if event else "Поломка"
        lines.append(f"| {stage} | {label} | {complete}/{len(models)*len(CASES)*len(REPEATS)} | "
                     f"{different['early']} | {different['late']} | {complete-sum(different.values())} |")
    first_pairs = []
    second_pairs = []
    for model, case, state, repeat in product(models, CASES, STATES, REPEATS):
        early, late = (index[model, case, state, t, repeat] for t in TIMINGS)
        for stage, target in ((1, first_pairs), (2, second_pairs)):
            a, b = (step_at(episode, stage) for episode in (early, late))
            if a and b and a["status"] == b["status"] == "OK":
                target.append((a, b))
    if first_pairs:
        same = sum(a["after_variant"] == b["after_variant"] for a, b in first_pairs)
        lines += ["", f"Один и тот же вариант исходного кода выбран на первом ходу в {same}/{len(first_pairs)} полных пар."]
    with_hashes = [(a, b) for a, b in second_pairs if a.get("prompt_sha256") and b.get("prompt_sha256")]
    if with_hashes:
        identical = [(a, b) for a, b in with_hashes if a["prompt_sha256"] == b["prompt_sha256"]]
        differ = sum(a["after_variant"] != b["after_variant"] for a, b in identical)
        lines += ["", f"Запросы второго хода совпали побайтно в {len(identical)}/{len(with_hashes)} пар с сохранёнными "
                  f"контрольными суммами. В {differ} из этих пар модели выбрали разные варианты кода. "
                  "Каждое решение принималось в свежей сессии. При одинаковом запросе различие ответов "
                  "характеризует вариацию между вызовами."]
    if disagreements:
        lines += ["", "Расхождения по правильности в приведённых выше парах", "", *disagreements]

    lines += ["", "## Изменения между первым и вторым решениями", "",
              "Здесь исходы сравниваются внутри каждого эпизода с двумя оценёнными решениями. "
              "Переход от ошибочного к правильному коду включает и позднее исправление исходного дефекта, "
              "и восстановление после первого вредного изменения.", "",
              "| Когда показана проверка | Два решения оценены | Неверно → верно | Верно → неверно | "
              "Верно → верно | Неверно → неверно |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for timing in TIMINGS:
        trans = Counter((truth(row, 1), truth(row, 2)) for key, row in index.items()
                        if key[3] == timing and truth(row, 2) is not None)
        counts = [trans[pair] for pair in ((False, True), (True, False), (True, True), (False, False))]
        lines.append("| " + " | ".join(map(str, [TITLES[timing], sum(counts), *counts])) + " |")
    missing = Counter()
    for row in all_rows:
        for stage in (1, 2):
            s = step_at(row, stage)
            if truth(row, stage) is None:
                missing[(stage, s["status"] if s else "нет записи")] += 1
    lines += ["", "## Неоценённые решения", ""]
    if missing:
        lines += [f"- Выбор {stage} — {table_value(reason)}: {n}." for (stage, reason), n in sorted(missing.items())]
    else:
        lines.append("Во всех назначенных эпизодах оба решения оценены.")
    lines += ["", "## Журнал по повторам", "",
              "После стрелки указан вариант, с оценкой которого связывается решение модели. ✓ означает, что он прошёл "
             "все проверки на скрытых входах. × означает, что как минимум одна не прошла. `keep` оставляет "
              "текущий вариант.", "",
              "| Модель | Проект | Старт | Повтор | Проверка | Начальный код | Первое решение | Второе решение |",
              "| --- | --- | --- | ---: | --- | --- | --- | --- |"]
    for model, case, state, rep, timing in product(models, CASES, STATES, REPEATS, TIMINGS):
        row = index[model, case, state, timing, rep]
        cells = [table_value(model), TITLES[case], TITLES[state], str(rep), TITLES[timing],
                 table_value(row["start_variant"]) if row else "—",
                 describe_step(row, 1), describe_step(row, 2)]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Два специально отобранных случая, конечное меню правок и два повтора ограничивают выводы "
              "наблюдаемыми задачами. Стартовые дефекты сконструированы. Пилот измеряет функциональность "
              "на заданных входах. Добровольная остановка и безопасность здесь не измерялись. "
              "При запуске независимая проверка случаев людьми оставалась незавершённой.", "",
              f"SHA-256 зафиксированного плана — `{data['plan_sha256']}`.", ""]
    access = data.get("access", {})
    if access:
        lines += ["Доступ при пробном запросе до запуска: " + ", ".join(
            f"`{table_value(model)}` — {table_value(status)}" for model, status in sorted(access.items())) + ".", ""]
    if "gpt-6.2-astra" in models and "gpt-6-luna" in models:
        lines += ["Оба выбранных имени относятся к линейкам Codex одного поставщика. "
                  "Устройство серверных моделей независимо не проверялось.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = render(json.loads(args.input.read_bytes()))
    if args.output.exists() and args.output.read_text() != text:
        raise ValueError("Existing report differs from the current public ledger")
    if not args.output.exists():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)


if __name__ == "__main__":
    main()
