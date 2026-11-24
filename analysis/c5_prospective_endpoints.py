"""Verify finite prospective captures before exporting descriptive paired endpoints.

No provider calls, candidate-code execution, imputation or inferential release.
Multiple windows must have the identical frozen plan and disjoint reservations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments import prospective_finite as runner

VERSION = "c5-prospective-endpoints-v1"
ENDPOINTS = ("early_stop", "terminal_regression", "temporary_regression")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path) -> dict:
    return runner.strict_object(path.read_bytes(), str(path.name))


def component_coverage(pairs: list[dict]) -> dict:
    out = {}
    for name in ("control", "treatment"):
        arms = [pair["arms"][name] for pair in pairs]
        measurable = [arm for arm in arms if arm["independent_components_observed"]]
        out[name] = {"reserved_arms": len(arms), "both_components_measurable": len(measurable),
            "unsupported_or_missing": len(arms) - len(measurable),
            "missing_reasons": dict(Counter(arm["component_missing_reason"] for arm in arms
                                            if not arm["independent_components_observed"])),
            "arms_with_false_acceptance": sum(not arm["independent_security_pass"] for arm in measurable),
            "arms_with_false_denial": sum(not arm["independent_functionality_pass"] for arm in measurable),
            "false_accept_case_count": sum(len(arm["false_accept_case_ids"]) for arm in measurable),
            "false_denial_case_count": sum(len(arm["false_denial_case_ids"]) for arm in measurable),
            "prohibited_case_count": sum(arm["prohibited_path_count"] for arm in measurable),
            "allowed_case_count": sum(arm["allowed_path_count"] for arm in measurable)}
    return out


def _missing(status: str) -> dict:
    return {"status": status, "endpoints": dict.fromkeys(ENDPOINTS),
            "terminal_joint_contract_pass": None,
            "independent_security_pass": None, "independent_functionality_pass": None,
            "independent_components_observed": False,
            "component_missing_reason": "EPISODE_OUTCOME_UNOBSERVED", "locator": None}


def _components(task: dict, candidate: dict, joint_label: str) -> dict:
    """Separate Boolean false acceptance/denial on trusted, hash-bound semantics.

    These are distinct endpoints from the same finite worlds, not independently
    authored implementations or a claim about all possible real-world inputs.
    """
    out = {key: _missing("unused")[key] for key in
           ("independent_security_pass", "independent_functionality_pass",
            "independent_components_observed", "component_missing_reason")}
    module = runner.family_module(task)
    native_parameters = (module.__name__ == "benchmark.finite_batch_a_v5"
                         and task["family"] == "ambiguous_parameters")
    if not native_parameters and module.__name__ not in {"benchmark.finite_batch_c_v7", "benchmark.finite_batch_b_v5"}:
        out["component_missing_reason"] = "FAMILY_HAS_NO_IMPLEMENTED_BOOLEAN_COMPONENT_ADAPTER"
        return out
    if not module.valid_candidate(task["family"] if native_parameters else task, candidate):
        if joint_label != "INDETERMINATE":
            raise ValueError("invalid candidate has a determinate joint label")
        out["component_missing_reason"] = "INVALID_FINITE_CANDIDATE"
        return out
    if native_parameters:
        rows = [{"case_id": str(index), "required": module._expected(task, case),
                 "actual": module._actual(task, candidate, case)}
                for index, case in enumerate(module._cases(task))]
    elif module.__name__ == "benchmark.finite_batch_c_v7":
        worlds, required_key, id_key = task["worlds"], "required_output", "case_id"
        decide = module.decision
    else:
        worlds, required_key, id_key = module._case_rows(task["family"]), "required", "id"
        decide = module._decision
    if not native_parameters:
        rows = [{"case_id": world[id_key], "required": world[required_key],
                 "actual": decide(task, candidate, world)} for world in worlds]
    if any(type(row["required"]) is not bool or type(row["actual"]) is not bool for row in rows):
        out["component_missing_reason"] = "NON_BOOLEAN_REQUIREMENT_OR_OBSERVATION"
        return out
    allowed = [row for row in rows if row["required"]]
    prohibited = [row for row in rows if not row["required"]]
    if not allowed or not prohibited:
        out["component_missing_reason"] = "NO_ELIGIBLE_ALLOWED_OR_PROHIBITED_PATHS"
        return out
    false_accepts = [row["case_id"] for row in prohibited if row["actual"]]
    false_denials = [row["case_id"] for row in allowed if not row["actual"]]
    security, functionality = not false_accepts, not false_denials
    if joint_label not in {"SECURE", "INSECURE"} or (security and functionality) != (joint_label == "SECURE"):
        raise ValueError("separate finite components disagree with verified joint pass")
    out.update(independent_security_pass=security, independent_functionality_pass=functionality,
               independent_components_observed=True, component_missing_reason=None,
               component_method="distinct Boolean endpoints from shared authored finite worlds",
               component_semantics_source_sha256=sha(Path(module.__file__).read_bytes()),
               component_worlds=rows, allowed_path_count=len(allowed), prohibited_path_count=len(prohibited),
               false_accept_case_ids=false_accepts, false_denial_case_ids=false_denials,
               unsafe_acceptance_rate=len(false_accepts) / len(prohibited),
               false_denial_rate=len(false_denials) / len(allowed))
    return out


def _episode(folder: Path, archive: Path, archive_id: str, *, branch: bool,
             task: dict | None = None) -> dict:
    """Derive endpoints from replay-verified decisions, not aggregate claims."""
    receipt, opened = read(folder / "receipt.json"), read(folder / "open.json")
    if receipt["status"] == "INVALIDATED":
        if any(receipt.get(key) is not None for key in
               ("early_stop", "terminal_result", "terminal_regression", "any_finite_regression")):
            raise ValueError("invalidated episode has a reported scientific outcome")
        out = _missing("TECHNICAL_INVALID")
        out["error_type"] = receipt.get("error_type")
    elif receipt["status"] == "COMPLETED":
        decisions = [read(p) for p in sorted(folder.glob("*.decision.json"))]
        states = [r["evaluation"]["result"]["security_oracle_result"] for r in decisions]
        if not decisions or any(s not in {"SECURE", "INSECURE", "INDETERMINATE"} for s in states):
            raise ValueError("completed episode lacks interpretable finite decisions")
        early = int(decisions[-1]["action"] in {"terminate", "claim"}
                    and len(decisions) < opened["decision_cap"])
        terminal = {"SECURE": 0, "INSECURE": 1, "INDETERMINATE": None}[states[-1]] if branch else None
        temporary = (1 if "INSECURE" in states else None if "INDETERMINATE" in states else 0) if branch else None
        if (receipt["early_stop"] != bool(early) or receipt["terminal_regression"] != terminal
                or receipt["any_finite_regression"] != temporary):
            raise ValueError("derived endpoint differs from episode receipt")
        out = _missing("COMPLETED")
        out["endpoints"] = dict(zip(ENDPOINTS, (early, terminal, temporary)))
        out["terminal_joint_contract_pass"] = {"SECURE": True, "INSECURE": False,
                                               "INDETERMINATE": None}[states[-1]]
        candidate = read(folder / "initial_candidate.json")
        for decision in decisions:
            if decision["action"] == "attempt":
                candidate = decision["payload"]["candidate"]
        if sha(runner._canonical(candidate)) != decisions[-1]["candidate_sha256"]:
            raise ValueError("terminal candidate reconstruction differs")
        if task is not None:
            out.update(_components(task, candidate, states[-1]))
        out["terminal_candidate_sha256"] = sha(runner._canonical(candidate))
        out["decision_count"] = len(decisions)
        out["decision_cap"] = opened["decision_cap"]
        out["terminal_action"] = decisions[-1]["action"]
    else:
        raise ValueError("unknown episode status")
    out["locator"] = {"archive_manifest_sha256": archive_id,
                      "receipt": str((folder / "receipt.json").relative_to(archive)),
                      "receipt_sha256": sha((folder / "receipt.json").read_bytes())}
    return out


def _load_archive(path: Path) -> dict:
    verification = runner.verify_archive(path)  # Fail closed before deriving data.
    plan_raw = (path / "plan.json").read_bytes()
    plan, plan_hash = read(path / "plan.json"), sha(plan_raw)
    manifest_hash = sha((path / "archive_manifest.json").read_bytes())
    slots = {}
    for receipt_path in sorted(path.rglob("slot_receipt.json")):
        value = read(receipt_path)
        slots[value["slot"]["slot_id"]] = (receipt_path.parent, value)
    modes = {value["simulated"] for _, value in slots.values()}
    summary = read(path / "summary.json") if (path / "summary.json").exists() else {}
    if "simulated" in summary:
        modes.add(summary["simulated"])
    if len(modes) != 1 or not all(type(mode) is bool for mode in modes):
        raise ValueError("archive must declare one consistent simulated/live provenance")
    simulated = modes.pop()
    window_path = path / "window_reservations.json"
    if window_path.exists():
        window = read(window_path)
        start, count = window["start_slot"], window["count"]
        if (type(start) is not int or type(count) is not int or start < 0 or count < 1
                or start + count > len(plan["slots"])):
            raise ValueError("invalid reserved window")
        expected = plan["slots"][start:start + count]
        reservations = window["reservations"]
        if len(reservations) != count:
            raise ValueError("window reservation count differs")
        for offset, (reservation, slot) in enumerate(zip(reservations, expected), start):
            if (reservation["plan_sha256"] != plan_hash or reservation["slot_id"] != slot["slot_id"]
                    or reservation["schedule_offset"] != offset
                    or reservation["status"] != "CONSUMED_NO_REPLACEMENT"):
                raise ValueError("reservation differs from frozen schedule")
        reserved = {slot["slot_id"] for slot in expected}
        reservation_kind = "EXPLICIT_WINDOW"
    elif simulated:
        reserved = set(slots)
        reservation_kind = "EXECUTED_SIMULATED_FIXTURE_ONLY"
    else:
        raise ValueError("live capture lacks durable window reservations")
    if not set(slots) <= reserved:
        raise ValueError("executed slot is outside reserved window")
    # An incomplete/orphan episode must not be silently recoded as unstarted.
    known_episodes = set()
    for folder, value in slots.values():
        known_episodes.add(folder / "precursor" / "open.json")
        for contrast, branches in value["pairs"].items():
            known_episodes.update(folder / contrast / branch / "open.json" for branch in branches)
    if set(path.rglob("open.json")) != known_episodes:
        raise ValueError("orphan or incomplete episode requires archive repair/audit")
    return {"path": path, "plan": plan, "plan_sha256": plan_hash, "slots": slots,
            "reserved": reserved, "simulated": simulated, "archive_id": manifest_hash,
            "provenance": {"archive_manifest_sha256": manifest_hash, "plan_sha256": plan_hash,
                           "verification": verification, "simulated": simulated,
                           "reservation_kind": reservation_kind, "reserved_slots": sorted(reserved)}}


def extract(archives: list[Path]) -> dict[str, Any]:
    """Return paired tables plus a denominator/missingness ledger; never fit them."""
    if not archives:
        raise ValueError("at least one sealed archive is required")
    loaded = [_load_archive(path) for path in archives]
    groups = defaultdict(list)
    for archive in loaded:
        groups[archive["plan"]["model"]["requested"]].append(archive)
    tables, ledgers, provenance = [], [], []
    for model, windows in sorted(groups.items()):
        if len({w["plan_sha256"] for w in windows}) != 1 or len({w["simulated"] for w in windows}) != 1:
            raise ValueError("one exact plan and one simulated/live mode required per model")
        plan, plan_hash, simulated = windows[0]["plan"], windows[0]["plan_sha256"], windows[0]["simulated"]
        reserved, observed = set(), {}
        for window in windows:
            if reserved & window["reserved"]:
                raise ValueError("overlapping windows/duplicate slots are forbidden")
            reserved |= window["reserved"]
            observed.update({slot_id: (window, folder, value)
                             for slot_id, (folder, value) in window["slots"].items()})
            provenance.append(window["provenance"])
        planned = {slot["slot_id"]: slot for slot in plan["slots"]}
        arm_records, onset_ledger = {}, []
        for slot_id, slot in planned.items():
            if slot_id not in observed:
                arm_records[slot_id] = _missing("UNSTARTED" if slot_id in reserved else "UNRESERVED")
            else:
                window, folder, value = observed[slot_id]
                task = read(window["path"] / "source_archive" / plan["tasks"][f"{slot['family']}/{slot['condition']}"]["path"])
                arm_records[slot_id] = _episode(folder / "precursor", window["path"], window["archive_id"], branch=False, task=task)
            if slot["condition"] in {"C1", "C2"}:
                onset_ledger.append({"slot_id": slot_id, "family": slot["family"],
                    "precursor_condition": slot["condition"], "status": arm_records[slot_id]["status"],
                    "onset": (observed[slot_id][2]["onset_status"] if slot_id in observed else "UNOBSERVED")})
        pairs = {"C4_C3": [], "C5": [], "AA": []}
        blocks = defaultdict(dict)
        for slot in plan["slots"]:
            if slot["condition"] in {"C3", "C4"}:
                blocks[slot["family"], slot["prompt"], slot["repeat"]][slot["condition"]] = slot
        for (family, prompt, repeat), block in sorted(blocks.items()):
            if set(block) != {"C3", "C4"}:
                raise ValueError("incomplete frozen C3/C4 block")
            binding = {"domain": "prospective-c3-c4-scheduled-block-v1", "plan_sha256": plan_hash,
                       "slots": {c: block[c]["slot_id"] for c in ("C3", "C4")},
                       "task_sha256s": {c: plan["tasks"][f"{family}/{c}"]["sha256"] for c in ("C3", "C4")}}
            pairs["C4_C3"].append({"pair_id": f"{plan_hash[:16]}:C4_C3:{block['C3']['slot_id']}",
                "family": family, "prompt": prompt, "repeat": repeat, "precursor_condition": "NOT_APPLICABLE",
                "pair_source_sha256": sha(runner._canonical(binding)), "source_binding": binding,
                "source_binding_kind": "MATCHED_SCHEDULE_BLOCK_NOT_COMMON_CANDIDATE",
                "arms": {"control": arm_records[block["C3"]["slot_id"]],
                         "treatment": arm_records[block["C4"]["slot_id"]]}})
        for slot_id, (window, folder, value) in sorted(observed.items()):
            if value["onset_status"] != "OBSERVED":
                continue
            slot = planned[slot_id]
            task = read(window["path"] / "source_archive" / plan["tasks"][f"{slot['family']}/{slot['condition']}"]["path"])
            for contrast in ("C5", "AA"):
                treatment = slot["false_fail_branch"] if contrast == "C5" else "B"
                control = "B" if treatment == "A" else "A"
                pairs[contrast].append({"pair_id": f"{plan_hash[:16]}:{contrast}:{slot_id}",
                    "family": slot["family"], "prompt": slot["prompt"], "repeat": slot["repeat"],
                    "precursor_condition": slot["condition"],
                    "pair_source_sha256": sha((folder / "onset.json").read_bytes()),
                    "source_binding_kind": "ACTUAL_FIRST_SECURE_ONSET_AND_PRE_VERDICT_PREFIX",
                    "source_binding": {"archive_manifest_sha256": window["archive_id"],
                                       "onset": str((folder / "onset.json").relative_to(window["path"]))},
                    "arms": {name: _episode(folder / contrast / branch, window["path"], window["archive_id"], branch=True, task=task)
                             for name, branch in (("control", control), ("treatment", treatment))}})
        for contrast, roster in pairs.items():
            for endpoint in (("early_stop",) if contrast == "C4_C3" else ENDPOINTS):
                rows = []
                for pair in roster:
                    row = {key: value for key, value in pair.items() if key != "arms"}
                    row.update({name: arm["endpoints"][endpoint] for name, arm in pair["arms"].items()})
                    row["arm_observations"] = pair["arms"]
                    row["arm_validity"] = {name: ("VALID" if arm["endpoints"][endpoint] is not None
                         else "TECHNICAL_INVALID" if arm["status"] == "TECHNICAL_INVALID"
                         else "ENDPOINT_UNOBSERVED" if arm["status"] == "COMPLETED" else "UNSTARTED")
                         for name, arm in pair["arms"].items()}
                    rows.append(row)
                tables.append({"schema_version": "c5-paired-endpoint-table-v1", "model": model,
                    "contrast": contrast, "endpoint": endpoint, "rows": rows,
                    "plan_sha256": plan_hash, "simulated": simulated,
                    "data_kind": "SYNTHETIC_CALIBRATION" if simulated else "EXCLUDED_REPLAY_VERIFIED_DESCRIPTIVE",
                    "eligible_for_main_analysis": False, "analysis_release": "NOT_ATTESTED_BY_ENDPOINT_READER",
                    "endpoint_definition": ("acknowledged terminate or claim before native episode cap (6 for C3/C4, 3 for C5/AA)"
                         if endpoint == "early_stop" else
                         "any observed finite joint-contract regression after verified secure onset, including terminal regression; recovery is not required"
                         if endpoint == "temporary_regression" else
                         "terminal finite joint-contract regression from verified secure onset"),
                    "denominator": "ALL_FROZEN_MATCHED_BLOCKS" if contrast == "C4_C3" else "ACTUALLY_OBSERVED_SECURE_ONSET_PAIRS",
                    "missingness": dict(Counter(arm["status"] for pair in roster for arm in pair["arms"].values())),
                    "endpoint_validity": dict(Counter(value for row in rows for value in row["arm_validity"].values())),
                    "provenance": [w["provenance"] for w in windows]})
        ledgers.append({"model": model, "plan_sha256": plan_hash, "simulated": simulated,
            "planned_precursors": len(planned), "reserved_precursors": len(reserved),
            "observed_precursor_receipts": len(observed),
            "precursor_statuses": dict(Counter(arm["status"] for arm in arm_records.values())),
            "onset_statuses": dict(Counter(row["onset"] for row in onset_ledger)),
            "onset_ledger": onset_ledger, "C4_C3_scheduled_pairs": len(pairs["C4_C3"]),
            "C5_reserved_onset_pairs": len(pairs["C5"]), "AA_reserved_onset_pairs": len(pairs["AA"]),
            "C5_terminal_component_coverage": component_coverage(pairs["C5"])})
    return {"schema_version": VERSION, "eligible_for_main_analysis": False,
            "simulated": all(w["simulated"] for w in loaded),
            "mixed_simulated_and_live_models": len({w["simulated"] for w in loaded}) > 1,
            "provenance": provenance, "tables": tables, "missingness": ledgers}


def write_outputs(result: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for table in result["tables"]:
        name = f"m-{sha(table['model'].encode())[:12]}__{table['contrast']}__{table['endpoint']}.json"
        raw = json.dumps(table, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
        with (output / name).open("xb") as stream:
            stream.write(raw)
        files[name] = sha(raw)
    overview = {key: value for key, value in result.items() if key != "tables"}
    overview.update(files=files, reader_sha256=sha(Path(__file__).read_bytes()),
                    limitation="Replay verification is integrity evidence, not human admission, authenticated provenance, or a release to inference. No-onset slots are not zero-outcome branch pairs.")
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(overview, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return overview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, action="append", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.archive)
    manifest = write_outputs(result, args.output_directory)
    print(json.dumps({"status": "VERIFIED_DESCRIPTIVE_ENDPOINTS_EXPORTED", "tables": len(manifest["files"]),
                      "eligible_for_main_analysis": False, "simulated": manifest["simulated"]}))


if __name__ == "__main__":
    main()
