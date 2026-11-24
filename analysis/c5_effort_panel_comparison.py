"""Readable, model-free comparison of the public six-task Codex panel."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import median

LEVELS = ("low", "medium", "high", "xhigh", "max", "ultra")
TASKS = ("A", "B", "C", "D", "E", "F")
CORRECT_START = {"B", "D", "E"}
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def show(value, digits=1, signed=False):
    if value is None:
        return "—"
    if value == int(value):
        return f"{value:+.0f}" if signed else str(int(value))
    return format(value, ("+" if signed else "") + f".{digits}f")


def fraction(pair):
    numerator, denominator = pair
    return f"{numerator}/{denominator}" if denominator else "—"


def validate(rows):
    models = {}
    for row in rows:
        model, effort = row["model"], row["effort"]
        if not re.fullmatch(r"gpt-[a-z0-9.-]+", model) or effort not in LEVELS or effort in models.get(model, {}):
            raise ValueError("Invalid or duplicate configuration")
        tasks = row["tasks"]
        if len({t["task"] for t in tasks}) != len(tasks):
            raise ValueError("Repeated task in a panel response")
        for t in tasks:
            if (t["task"] not in TASKS or t["starting_correct"] is not (t["task"] in CORRECT_START)
                    or type(t["valid"]) is not bool or (t["valid"] and type(t["final_correct"]) is not bool)
                    or (not t["valid"] and t["final_correct"] is not None)):
                raise ValueError("Invalid task state")
        valid = [t for t in tasks if t["valid"]]
        values = [t["final_correct"] for t in valid]
        if row["valid_tasks"] != len(valid) or row["correct"] != sum(values):
            raise ValueError("Incorrect public task total")
        for key, starting in (("preserved", True), ("repaired", False)):
            group = [t for t in valid if t["starting_correct"] is starting]
            if row[key] != [sum(t["final_correct"] for t in group), len(group)]:
                raise ValueError("Incorrect preservation or repair denominator")
        if row["unnecessary_rewrites"] != sum(t["unnecessary_rewrite"] for t in valid):
            raise ValueError("Incorrect redundant-rewrite count")
        models.setdefault(model, {})[effort] = row
    return dict(sorted(models.items(), reverse=True))


def task_cells(row):
    tasks = {t["task"]: t for t in row["tasks"] if t["valid"]}
    return "".join(
        ("✓" if tasks[k]["final_correct"] else "×") if k in tasks else "·" for k in TASKS)


def compare(base, other):
    if min(base["valid_tasks"], other["valid_tasks"]) != 6:
        return None
    before = {t["task"]:t["final_correct"] for t in base["tasks"]}
    after = {t["task"]:t["final_correct"] for t in other["tasks"]}
    gains = [key for key in TASKS if not before[key] and after[key]]
    losses = [key for key in TASKS if before[key] and not after[key]]
    def difference(left, right):
        return None if left is None or right is None else right - left
    return {"net":len(gains)-len(losses), "gains":gains, "losses":losses,
            "output":difference(base["usage"]["output_tokens"], other["usage"]["output_tokens"]),
            "seconds":difference(base["elapsed_seconds"], other["elapsed_seconds"])}


def metric(values):
    observed = [value for value in values if value is not None]
    return show(median(observed), signed=True) + f" ({len(observed)})" if observed else "—"


def render(panel, digest):
    if panel["schema"] != "c5-codex-effort-panel-v1":
        raise ValueError("Unexpected panel schema")
    rows = panel["rows"]
    models = validate(rows)
    statuses = Counter(r["status"] for r in rows)
    complete = [r for r in rows if r["valid_tasks"] == 6]
    partial = [r for r in rows if 0 < r["valid_tasks"] < 6]
    first = ["# Сравнение уровней усилия Codex на шести задачах", "",
             f"Моделей в каталоге — **{len(models)}**, поддерживаемых сочетаний — **{len(rows)}**. "
             f"Полные ответы получены в **{len(complete)}** сочетаниях, частичные — в {len(partial)}. "
             f"Ещё {len(rows)-len(complete)-len(partial)} сочетаний не дали оцениваемых ответов. "
             f"Всего оценено {sum(r['valid_tasks'] for r in rows)} из {6*len(rows)} запланированных решений.",
             "", "Каждое сочетание получило один запрос с теми же шестью задачами. На старте три таблицы верны, "
             "у трёх ошибочна одна ячейка. Если сохранить все таблицы без изменений, итог составит **3/6**. "
             "Верный ответ требует проверки каждой таблицы на всех перечисленных входах.", "",
             "## Сколько задач решено", "",
             "В ячейке указаны верные и оценённые ответы. «Н/Д» означает, что сочетание запланировано, "
             "но результат отсутствует. Тире означает, что такого уровня нет в каталоге.", "",
             "| Модель | low | medium | high | xhigh | max | ultra |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for model, group in models.items():
        cells = []
        for level in LEVELS:
            row = group.get(level)
            if row is None:
                cell = "—"
            elif row["valid_tasks"]:
                cell = fraction((row["correct"],row["valid_tasks"]))
            else:
                cell = "Н/Д"
            cells.append(cell)
        first.append("| " + model + " | " + " | ".join(cells) + " |")
    first.extend(["", "## Что изменилось относительно low", "",
                  "Каждая пара сравнивает одну модель на одних и тех же шести задачах при двух уровнях усилия. "
                  "В этот раздел входят только пары с шестью оцениваемыми ответами с обеих сторон. "
                  "Изменение времени и выходных токенов рассчитано в каждой паре отдельно. В скобках указано число доступных измерений.",
                  "", "| Уровень против low | Полных пар | Выше / столько же / ниже | Исправлено / потеряно задач | Медиана Δ времени, с | Медиана Δ выходных токенов |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"])
    pairs = []
    for level in LEVELS[1:]:
        matched = []
        for model, group in models.items():
            if level not in group or "low" not in group:
                continue
            item = compare(group["low"], group[level])
            if item is not None:
                matched.append(item)
                pairs.append((model,level,item))
        higher = sum(p["net"] > 0 for p in matched)
        lower = sum(p["net"] < 0 for p in matched)
        tied = len(matched) - higher - lower
        first.append(f"| {level} | {len(matched)} | {higher} / {tied} / {lower} | "
                     f"{sum(len(p['gains']) for p in matched)} / {sum(len(p['losses']) for p in matched)} | "
                     f"{metric(p['seconds'] for p in matched)} | {metric(p['output'] for p in matched)} |")
    first.extend(["", "### Пары по моделям", "",
                  "Плюс показывает больший результат или больший расход по сравнению с low. В столбцах задач перечислены их обозначения A–F.",
                  "", "| Модель | Уровень | Δ верных | Стали верны | Стали ошибочны | Δ времени, с | Δ выходных токенов |",
                  "| --- | --- | ---: | --- | --- | ---: | ---: |"])
    for model, level, p in pairs:
        first.append(f"| {model} | {level} | {show(p['net'],signed=True)} | {', '.join(p['gains']) or '—'} | "
                     f"{', '.join(p['losses']) or '—'} | {show(p['seconds'],signed=True)} | {show(p['output'],signed=True)} |")
    first.extend(["", "## Результаты каждого запроса", "",
                  "«Оценено» даёт покрытие из шести задач. В последовательности A–F символ ✓ означает правильный итог, × — ошибку, "
                  "· — отсутствие оценки. «Лишние» считает предложения заменить исходно верную таблицу, включая повтор её содержимого. "
                  "Кэшированные токены уже входят во входные, а токены рассуждения — в выходные. Время включает запуск CLI и сеть.",
                  "", "| Модель | Усилие | Статус | Оценено | A–F | Сохранено | Исправлено | Лишние | Время, с | Вход | Из кэша | Выход | Рассуждение |",
                  "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for group in models.values():
        for level in LEVELS:
            if level not in group:
                continue
            row = group[level]
            fields = [row["model"],level,row["status"],f"{row['valid_tasks']}/6",task_cells(row),
                      fraction(row["preserved"]),fraction(row["repaired"]),
                      show(row["unnecessary_rewrites"]) if row["preserved"][1] else "—",show(row["elapsed_seconds"])]
            fields.extend(show(row["usage"][k]) for k in TOKEN_KEYS)
            first.append("| " + " | ".join(fields) + " |")
    first.extend(["", "Для сравнения скорости доступно одно измерение на сочетание. На него влияют очередь, сеть, кэш и длина ответа. "
                  "Задачи в запросе делят общий контекст. Сравнение описывает эти таблицы и эти вызовы. "
                  "Названия моделей и уровней взяты из параметров CLI. Проверить серверную конфигурацию по этим данным невозможно.",
                  "", "Статусы в публичном захвате — " + ", ".join(f"`{k}` ({n})" for k,n in sorted(statuses.items())) + ".",
                  "", f"SHA-256 исходной публичной таблицы — `{digest}`.", ""])
    return "\n".join(first)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    raw = args.panel.read_bytes()
    contents = render(json.loads(raw),sha256(raw).hexdigest())
    if args.output.exists():
        if args.output.read_text() != contents:
            raise FileExistsError("Choose a fresh path for a changed report")
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x") as file:
            file.write(contents)


if __name__ == "__main__":
    main()
