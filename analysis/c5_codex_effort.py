"""Recount the bounded Codex CLI effort matrix from verified private records."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from tempfile import TemporaryDirectory

ARMS = ("INDEPENDENT_PARTIAL", "REPEAT_ORIGINAL")
STATES = ("CORRECT", "DEFECTIVE")
DEFECTS = ("PUBLIC_VISIBLE", "PUBLIC_MISSED")
EFFORTS = ("low", "high")
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
STATUSES = ("UNSTARTED", "ONGOING", "TECHNICAL_INVALID", "COMPLETED")


def number(value, *, integer=False):
    if value is None:
        return None
    allowed = (int,) if integer else (int, float)
    if type(value) not in allowed or value < 0 or not math.isfinite(value):
        raise ValueError("Invalid nonnegative measured quantity")
    return value


def safe_id(value, pattern=r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("Unexpected public identifier")
    return value


def stamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def ratio(values):
    """Keep scheduled, observed and identification bounds distinct."""
    values = list(values)
    known = [v for v in values if v is not None]
    if any(type(v) is not bool for v in known):
        raise ValueError("Expected Boolean outcome")
    n, observed, success = len(values), len(known), sum(known)
    return {"scheduled": n, "observed": observed, "success": success,
            "fraction_observed": success / observed if observed else None,
            "bounds_over_scheduled": [success / n, (success + n - observed) / n] if n else None}


def sum_if_complete(values):
    return sum(values) if values and all(v is not None for v in values) else None


def quantitative(values):
    values = list(values)
    known = [v for v in values if v is not None]
    return {"observed": len(known), "eligible": len(values), "sum_observed": sum(known) if known else None,
            "median_observed": median(known) if known else None}


def project_episode(raw):
    model, effort = safe_id(raw["model"], r"gpt-[a-z0-9.-]+"), raw["effort"]
    state, arm, defect, status = (raw[k] for k in ("state", "arm", "defect", "status"))
    if effort not in EFFORTS or state not in STATES or arm not in ARMS or defect not in DEFECTS or status not in STATUSES:
        raise ValueError("Unexpected scheduled condition or episode status")
    correct = state == "CORRECT"
    steps = []
    for seq, item in enumerate(raw["events"], 1):
        action = item["action"]
        if (seq > 3 or seq != item["sequence"] or item["correct_before"] is not correct
                or action not in {None, "repair", "stop", "check"}):
            raise ValueError("Unexpected action order or retained state")
        after, same = item["correct_after"], item["same_candidate"]
        if action is None:
            if after is not None or seq != len(raw["events"]):
                raise ValueError("Invalid action with observed endpoint or later decision")
        elif type(after) is not bool or type(same) is not bool or (same and correct != after):
            raise ValueError("Invalid next candidate")
        elif action in {"check", "stop"} and not same:
            raise ValueError("Nonediting action changed candidate")
        started, finished = (stamp(item.get(k)) for k in ("started_at", "finished_at"))
        usage = item.get("usage") or {}
        tokens = {k: number(usage.get(k), integer=True) for k in TOKEN_FIELDS}
        err = item.get("error")
        steps.append({"sequence": seq, "action": action, "correct_before": correct, "correct_after": after,
                      "same_candidate": same, "error": safe_id(err) if err else None,
                      "duration_seconds": number(item["duration_seconds"]), "usage": tokens,
                      "effective_model_ids": sorted({safe_id(m, r"(?:codex|gpt)[-:.A-Za-z0-9_]{0,99}")
                                                     for m in item.get("effective_model_ids", [])}),
                      "started_at": started.isoformat() if started else None,
                      "finished_at": finished.isoformat() if finished else None})
        correct = after
    completed = status == "COMPLETED"
    terminal = raw["terminal_correct"]
    if (completed and (not steps or type(terminal) is not bool or terminal is not correct)
            or not completed and terminal is not None or status == "UNSTARTED" and steps):
        raise ValueError("Endpoint and completion status disagree")
    if completed and steps[-1]["action"] != "stop" and len(steps) != 3:
        raise ValueError("Unexplained terminal decision")
    first = steps[0] if steps else {}
    inputs = sum_if_complete([s["usage"]["input_tokens"] for s in steps])
    outputs = sum_if_complete([s["usage"]["output_tokens"] for s in steps])
    return {"model": model, "effort": effort, **{key: safe_id(raw[key]) for key in ("episode_id", "case_id", "pair_id")},
            "state": state, "arm": arm, "defect": defect, "status": status, "terminal_correct": terminal,
            "first_decision_corrected": (first["action"] == "repair" and first["correct_after"])
                if state == "DEFECTIVE" and first.get("action") else None,
            "explicit_stop": steps[-1]["action"] == "stop" if completed else None,
            "cli_attempts": len(steps), "checks": sum(s["action"] == "check" for s in steps),
            "decisions_above_shortest_success": len(steps) - (1 if state == "CORRECT" else 2) if terminal is True else None,
            "unchanged_repairs": sum(s["action"] == "repair" and s["same_candidate"] for s in steps),
            "duration_seconds": sum_if_complete([s["duration_seconds"] for s in steps]),
            "input_plus_output_tokens": inputs + outputs if inputs is not None and outputs is not None else None,
            "steps": steps}


def summarize(rows):
    done = [r for r in rows if r["status"] == "COMPLETED"]
    attempted_steps = [s for r in rows for s in r["steps"]]
    checks = [s for s in attempted_steps if s["action"] == "check"]
    return {"scheduled": len(rows), "completed": len(done), "statuses": dict(Counter(r["status"] for r in rows)),
            "technical_errors": dict(Counter(s["error"] for s in attempted_steps if s["error"])),
            "preserved": ratio(r["terminal_correct"] for r in rows if r["state"] == "CORRECT"),
            "repaired": ratio(r["terminal_correct"] for r in rows if r["state"] == "DEFECTIVE"),
            "corrected_on_first_decision": ratio(r["first_decision_corrected"] for r in rows if r["state"] == "DEFECTIVE"),
            "explicit_stop": ratio(r["explicit_stop"] for r in rows),
            "all_cli_attempts": len(attempted_steps), "valid_actions": sum(s["action"] is not None for s in attempted_steps),
            "completed_episode_decisions": quantitative(r["cli_attempts"] for r in done),
            "decisions_above_shortest_success": quantitative(r["decisions_above_shortest_success"] for r in done if r["terminal_correct"]),
            "all_observed_checks": len(checks), "checks_on_already_correct_candidate": sum(s["correct_before"] for s in checks),
            "all_observed_unchanged_repairs": sum(r["unchanged_repairs"] for r in rows),
            "unchanged_repairs_from_correct_starts": sum(r["unchanged_repairs"] for r in rows if r["state"] == "CORRECT"),
            "complete_episode_active_seconds": quantitative(r["duration_seconds"] for r in done),
            "complete_episode_input_plus_output_tokens": quantitative(r["input_plus_output_tokens"] for r in done),
            "per_call_token_coverage": {k: quantitative(s["usage"][k] for s in attempted_steps) for k in TOKEN_FIELDS},
            "returned_model_identifiers": sorted({m for s in attempted_steps for m in s["effective_model_ids"]}),
            "calls_with_returned_model_id": sum(bool(s["effective_model_ids"]) for s in attempted_steps)}


def matched(rows):
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case_id"]][row["effort"]] = row
    complete = [(pair["low"], pair["high"]) for pair in by_case.values()
                if all(pair[e]["status"] == "COMPLETED" for e in EFFORTS)]
    result = {"scheduled_cases": len(by_case), "complete_pairs": len(complete)}
    measures = ("terminal_correct", "cli_attempts", "checks", "unchanged_repairs",
                "duration_seconds", "input_plus_output_tokens")
    for key in measures:
        delta = [h[key] - l[key] for l, h in complete if l[key] is not None and h[key] is not None]
        result[key] = {"observed_pairs": len(delta), "high_greater": sum(x > 0 for x in delta),
                       "equal": sum(x == 0 for x in delta), "high_lower": sum(x < 0 for x in delta),
                       "mean_high_minus_low": sum(delta) / len(delta) if delta else None,
                       "median_high_minus_low": median(delta) if delta else None}
    return result


def build_report(archive):
    confs = [(x["model"], x["effort"]) for x in archive["configurations"]]
    if len(set(confs)) != len(confs) or any((m, level) not in confs for m, _ in confs for level in EFFORTS):
        raise ValueError("Duplicate or unmatched model-effort settings")
    rows = [project_episode(r) for r in archive["episodes"]]
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"], row["effort"]].append(row)
    if len({r["episode_id"] for r in rows}) != len(rows) or set(groups) != set(confs):
        raise ValueError("Unexpected duplicate episodes or configuration coverage")
    reference = None
    for group in groups.values():
        design = {(r["case_id"], r["pair_id"], r["state"], r["arm"], r["defect"]) for r in group}
        cells = {(r["state"], r["arm"], r["defect"]) for r in group}
        if len(group) != 8 or len(cells) != 8 or len({r["case_id"] for r in group}) != 8:
            raise ValueError("Expected the same eight distinct scheduled cells in every configuration")
        if reference is not None and design != reference:
            raise ValueError("Conditions differ across matched configurations")
        reference = design
    names = list(dict.fromkeys(m for m, _ in confs))
    start = [stamp(s["started_at"]) for r in rows for s in r["steps"] if s["started_at"]]
    finish = [stamp(s["finished_at"]) for r in rows for s in r["steps"] if s["finished_at"]]
    by_model = {}
    for model in names:
        by_model[model] = {}
        for effort in EFFORTS:
            group = groups[model, effort]
            by_model[model][effort] = summarize(group)
            by_model[model][effort]["by_checker"] = {a: summarize([r for r in group if r["arm"] == a]) for a in ARMS}
        by_model[model]["matched_high_minus_low"] = matched(groups[model, "low"] + groups[model, "high"])
    source_digests = {}
    for path, digest in archive["source_sha256s"].items():
        if (Path(path).is_absolute() or ".." in Path(path).parts
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)):
            raise ValueError("Source provenance must have a relative project path")
        source_digests[path] = safe_id(digest, r"[0-9a-f]{64}")
    frozen = stamp(archive.get("frozen_at"))
    return {"schema_version": "c5-codex-effort-comparison-v1",
            "study": "Descriptive CLI evaluation on one authored four-entry arithmetic table",
            "security_applicability": "NOT_APPLICABLE", "eligible_for_main_analysis": False,
            "frozen_at": frozen.isoformat() if frozen else None, "plan_sha256": safe_id(archive["plan_sha256"], r"[0-9a-f]{64}"),
            "collection_source_sha256s": source_digests, "cli_version": safe_id(archive["cli_version"], r"codex-cli [0-9A-Za-z.+-]{1,50}"),
            "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "first_observed_start_utc": min(start).isoformat() if start else None,
            "last_observed_finish_utc": max(finish).isoformat() if finish else None,
            "observed_capture_span_seconds": (max(finish) - min(start)).total_seconds() if start and finish else None,
            "definitions": {
                "quality": "Four correct and four defective starts per setting. Missing terminal outcomes retain their scheduled denominator and [0,1] bounds.",
                "first_step": "Among initially defective starts, a valid first repair with a correct result; observed before any later requested check. Later loss cannot erase an observed first action.",
                "resources": "All recorded invocations include technical failures. Complete-episode comparisons use only completed episodes. An unchanged repair resubmits exactly the same table.",
                "shortest_success": "Among terminally correct episodes only, the feasible minimum is 1 decision (stop) for a correct start and 2 (repair then stop) for a defective start. An action above that minimum may be informative.",
                "time": "Episode active time sums CLI subprocess durations in that episode. Overall capture span is first recorded start to last recorded finish, including gaps and concurrent workers.",
                "tokens": "Input and output form the total. Cached input and reasoning output are separately reported subcounts when present. Missing usage stays unknown. Token counts do not establish cost.",
                "paired_effect": "High minus low on the identical case_id in the same model. All signs are numerical. For decisions, latency and tokens, a negative difference denotes less use at high. Ties are retained.",
                "scope": "Effort and model are requested CLI settings. Observed runtime metadata cannot attest model weights or internal reasoning. Repeated starts from one task give no general model ranking."},
            "all_episodes": summarize(rows), "by_effort": {e: summarize([r for r in rows if r["effort"] == e]) for e in EFFORTS},
            "models": by_model, "episode_ledger": rows}


def quantity(value, digits=1):
    return "—" if value is None else f"{value:,.{digits}f}"


def report_md(report):
    total = report["all_episodes"]
    lines = ["# Как меняется поведение Codex при смене уровня рассуждения", "",
        f"Завершено **{total['completed']}/{total['scheduled']}** эпизодов, зафиксировано **{total['all_cli_attempts']}** обращений к CLI. "
        "В каждой настройке модель получает по четыре правильные и четыре дефектные таблицы для одной задачи удвоения. "
        "В обеих группах проверка изначально сообщает об ошибке. В испытании оценивается функциональность. Безопасность здесь не проверяется.",
        "", "| Запрошенная модель | Усилие | Завершено | Сохранено | Исправлено | Исправлено сразу | Явных остановок | Действий¹ | Проверок² | Повторных правок² | Медиана с¹ | Медиана токенов¹ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, model in report["models"].items():
        for e in EFFORTS:
            r = model[e]
            cells = [name, e, f"{r['completed']}/{r['scheduled']}"]
            for key in ("preserved", "repaired", "corrected_on_first_decision", "explicit_stop"):
                a = r[key]
                cells.append(f"{a['success']}/{a['observed']}" if a["observed"] else "—")
            cells += [quantity(r["completed_episode_decisions"]["sum_observed"], 0),
                      str(r["all_observed_checks"]), str(r["all_observed_unchanged_repairs"]),
                      quantity(r["complete_episode_active_seconds"]["median_observed"]),
                      quantity(r["complete_episode_input_plus_output_tokens"]["median_observed"], 0)]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "¹ Сумма действий по завершённым эпизодам. Время эпизода — сумма длительностей его вызовов CLI. "
        "Медианы рассчитаны для завершённых эпизодов с полными измерениями. Число токенов включает вход и выход. "
        "Кэшированные входные токены и токены рассуждения не прибавляются повторно. Время включает задержки клиента и сервера.",
        "", "² Проверки и повторные отправки точно той же таблицы посчитаны по всем зарегистрированным действиям. "
        "Если ни одного эпизода не начато, ноль означает отсутствие наблюдавшихся действий. Пропущенные исходы показаны прочерком.",
        "", "## Попарное сравнение high и low", "",
        "Каждая пара начинается с одного и того же варианта задачи. В тройках показано число случаев, "
        "где high дал больше / столько же / меньше, чем low. Для правильности «больше» означает лучший исход, "
        "для числа действий — больший расход. Расчёты опираются на пары с двумя завершёнными эпизодами.",
        "", "| Модель | Полных пар | Правильность (+/=/-) | Действия (+/=/-) | Медиана разницы, с | Медиана разницы, токены |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, model in report["models"].items():
        paired = model["matched_high_minus_low"]
        def signs(key):
            x = paired[key]
            return f"{x['high_greater']}/{x['equal']}/{x['high_lower']}" if x["observed_pairs"] else "—"
        cells = [name, f"{paired['complete_pairs']}/{paired['scheduled_cases']}", signs("terminal_correct"),
                 signs("cli_attempts"), quantity(paired["duration_seconds"]["median_high_minus_low"]),
                 quantity(paired["input_plus_output_tokens"]["median_high_minus_low"], 0)]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Один запуск на условие. Изменение в отдельной паре может зависеть от случайности ответа и нагрузки сервера. "
        "Параллельное выполнение влияет на наблюдаемое время. Названия моделей и уровней — параметры запроса. "
        "Ответы CLI могут содержать дополнительные идентификаторы, их наличие отмечено в данных.",
        "", "[Полный журнал обезличенных действий и знаменатели](results.json)", ""]
    if total["technical_errors"]:
        coverage = ", ".join(f"{code} ({n})" for code, n in sorted(total["technical_errors"].items()))
        lines[2] += " Технические исходы зарегистрированных вызовов: " + coverage + "."
    return "\n".join(lines)


def save(output, report, check=False):
    generated = {"results.json": (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(),
                 "comparison.md": report_md(report).encode()}
    if output.exists() or check:
        if not all((output / name).is_file() and (output / name).read_bytes() == content
                   for name, content in generated.items()):
            raise ValueError("Saved report differs or is missing; use a fresh output directory")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as tmp:
        bundle = Path(tmp)/"bundle"
        bundle.mkdir()
        for name, content in generated.items():
            (bundle/name).write_bytes(content)
        bundle.rename(output)


def main():
    from experiments.c5_codex_effort import verify_archive
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="private archive to replay")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(verify_archive(args.root))
    save(args.output_dir, report, args.check)
    print(json.dumps({k: report["all_episodes"][k] for k in ("scheduled", "completed", "all_cli_attempts")}, indent=2))


if __name__ == "__main__":
    main()
