"""Summarize a saved paired CPython post-edit experiment, without launching models."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


PROBES = ("1,2", "2,10")


def cell(value):
    return str(value).replace("|", r"\|").replace("\n", " ")


def ratio(count, denominator):
    return f"{count}/{denominator}" if denominator else "—"


def index_pairs(rows):
    pairs = defaultdict(dict)
    for row in rows:
        key = (row["model"], row["parent_id"])
        probe = row["probe"]
        if probe not in PROBES or probe in pairs[key]:
            raise ValueError("Unknown or duplicate probe in a parent pair")
        if type(row["before_correct"]) is not bool or not row["before_variant"]:
            raise ValueError("Invalid parent state")
        if row["status"] == "OK":
            if type(row["after_correct"]) is not bool or not row["after_variant"] or not row["choice"]:
                raise ValueError("Successful response lacks a scored choice")
            if row["before_variant"] == row["after_variant"] and row["before_correct"] != row["after_correct"]:
                raise ValueError("Unchanged code has inconsistent scores")
            if row["choice"] == "keep" and row["before_variant"] != row["after_variant"]:
                raise ValueError("Keeping the current implementation changed its code")
        elif any(row.get(field) is not None for field in ("after_correct", "after_variant", "choice")):
            raise ValueError("Missing or erroneous response contains a scored outcome")
        pairs[key][probe] = row
    for arms in pairs.values():
        if set(arms) != set(PROBES):
            raise ValueError("Each source requires two scheduled rows, including missing responses")
        a, b = (arms[probe] for probe in PROBES)
        if (a["before_correct"], a["before_variant"]) != (b["before_correct"], b["before_variant"]):
            raise ValueError("The two arms did not start from the same state")
    return pairs


def render(data):
    rows = data["rows"]
    pairs = index_pairs(rows)
    models = sorted({model for model, _ in pairs})
    broken = Counter(model for (model, _), arms in pairs.items() if not arms[PROBES[0]]["before_correct"])
    working_count = len(pairs) - sum(broken.values())
    lines = ["# CPython: что изменил вывод проверки после первой правки", "",
             f"Из {len(pairs)} сохранённых состояний форматтера {working_count} прошли отложенные проверки "
             f"после первой правки, {sum(broken.values())} содержали ошибку. От каждого состояния продолжили "
             "две ветви. Модель видела вывод текущего кода на одной паре ключей и могла сделать один ход.", ""]
    if broken:
        sources = ", ".join(f"{cell(model)} ({n})" for model, n in sorted(broken.items()))
        lines.extend([f"Модели, давшие исходные состояния с ошибкой: {sources}.", ""])
    lines += ["## Исправления и сохранения", "",
              "Исходное состояние здесь — версия сразу после первой правки. Исправление засчитывается, когда "
              "версия с ошибкой после нового хода проходит все отложенные проверки. Сохранение включает выбор "
              "другой реализации, если она тоже проходит эти проверки. Оценённые ответы формируют знаменатель "
              "для каждого исхода. Прочерк означает отсутствие соответствующих наблюдений.", "",
              "| Модель | Ключи | Оценено / назначено | Исправлено среди сломанных | Сохранено среди рабочих | Сломано среди рабочих |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for model in [None, *models]:
        for probe in PROBES:
            selected = [r for r in rows if r["probe"] == probe and (model is None or r["model"] == model)]
            valid = [r for r in selected if r["status"] == "OK"]
            faulty = [r["after_correct"] for r in valid if not r["before_correct"]]
            working = [r["after_correct"] for r in valid if r["before_correct"]]
            lines.append("| " + " | ".join([cell(model or "Все модели"), probe, ratio(len(valid), len(selected)),
                         ratio(sum(faulty), len(faulty)), ratio(sum(working), len(working)),
                         ratio(working.count(False), len(working))]) + " |")
    lines += ["", "## Сопоставление ветвей из одного состояния", "",
              "Каждая полная пара входит ровно в один из четырёх столбцов исходов. Для неполной пары "
              "хотя бы один исход неизвестен.", "",
              "| Цель | Полных пар / назначено | Только 1,2 | Только 2,10 | Обе ветви | Ни одна |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for correct, label in ((False, "Исправить поломку"), (True, "Сохранить рабочий код")):
        eligible = [arms for arms in pairs.values() if arms[PROBES[0]]["before_correct"] == correct]
        joint = Counter(tuple(arms[p]["after_correct"] for p in PROBES) for arms in eligible
                        if all(arms[p]["status"] == "OK" for p in PROBES))
        counts = [joint[key] for key in ((True, False), (False, True), (True, True), (False, False))]
        lines.append("| " + " | ".join([label, ratio(sum(counts), len(eligible)), *map(str, counts)]) + " |")
    lines += ["", "## Исход каждого состояния", "",
              "В столбцах для каждого набора ключей указаны итоговый вариант и его результат на отложенных входах. "
              "Статус ответа приведён вместо оценки, если результат неизвестен.", "",
              "| Модель | Исходный эпизод | После первой правки | Вывод на 1,2 | Вывод на 2,10 |",
              "| --- | --- | --- | --- | --- |"]
    for (model, parent_id), arms in sorted(pairs.items()):
        parent = arms[PROBES[0]]
        start = f"{cell(parent['before_variant'])} ({'рабочий' if parent['before_correct'] else 'с ошибкой'})"
        cells = [cell(model), cell(parent_id), start]
        for p in PROBES:
            arm = arms[p]
            if arm["status"] != "OK":
                cells.append(cell(arm["status"]))
            else:
                cells.append(f"{cell(arm['after_variant'])} ({'прошёл' if arm['after_correct'] else 'ошибка'})")
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Это предварительный опыт до независимой проверки случая людьми. Все эпизоды относятся к одной "
              "задаче CPython и ограниченному меню вариантов кода. Повторные решения по одной задаче не дают "
              "оценки эффекта для других проектов или свободно написанных правок.", "",
              "[Журнал решений](results.json) · [Зафиксированный план](plan.json)", "",
              f"SHA-256 плана — `{data['plan_sha256']}`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = render(json.loads(args.input.read_bytes()))
    if args.output.exists():
        if args.output.read_text() != content:
            raise ValueError("Saved report differs from the current ledger")
    else:
        args.output.write_text(content)
