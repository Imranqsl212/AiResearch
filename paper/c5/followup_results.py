"""Reconstruct follow-up tables from frozen assignments and observed choices."""
from collections import Counter
import csv
import json
from pathlib import Path

from analysis import feedback_factorial_report as factorial
from analysis import free_patch_report as free_patch
from analysis import output_provenance_report as provenance
from analysis import production_patch_report as production
from analysis.matplotlib_axis_integration_20261128 import replay as axis_replay
from analysis import quix_contract_reversal_report as reversal
from analysis import replicate_display_report as replica
from analysis import selection_disclosure_report, replicate_display_permutation, quix_contract_matched_pairs, matplotlib_replication_report, quix_rule_omission_report
from analysis import matplotlib_order_types, production_patch_examples, quix_upstream_tests, production_patch_components, feedback_resources, quix_expanded_domain, quix_syntax_controls, swe_recheck

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
STUDIES = ("feedback_factorial_20261128", "free_patch_20261128", "production_patch_20261128",
           "replicate_display_20261128", "output_provenance_20261128", "quix_contract_reversal_20261128",
           "matplotlib_replication_20261128", "quix_rule_omission_20261128", "selection_disclosure_20261128")
DISPLAY = {"none":"No output", "shared":"Shared output", "revealing":"Revealing output"}
SOURCES = {"anonymous":"Unspecified candidate", "named":"Named candidate", "required":"Target requirement"}


COHORT_NAMES = {
    "feedback_factorial_20261128": "Actual and required output",
    "free_patch_20261128": "QuixBugs expression patches",
    "production_patch_20261128": "Historical maintenance fixes",
    "replicate_display_20261128": "CPython duplicate draws",
    "output_provenance_20261128": "Same value, different sources",
    "quix_contract_reversal_20261128": "Opposing QuixBugs contracts",
    "matplotlib_replication_20261128": "Matplotlib repeated prompts",
    "quix_rule_omission_20261128": "QuixBugs definitions omitted",
    "selection_disclosure_20261128": "Disclosure of example selection",
}


def coverage_rows():
    rows = []
    for study in STUDIES:
        records = read(ANALYSIS / study / "results.json")["rows"]
        captured = sum(r.get("native_response_sha256") is not None for r in records)
        usable = sum(r["status"] == "OK" for r in records)
        rows.append([COHORT_NAMES[study], str(len(records)), str(captured), str(usable)])
    return rows


def read(path):
    return json.loads(path.read_bytes())


def frac(n, d):
    return f"{n}/{d}" if d else "—"


def pct(value):
    return f"{100*value:.1f}%" if value is not None else "—"


def verify_report(directory, computed):
    if computed != (directory / "comparison.md").read_text():
        raise ValueError(f"Recomputed report differs in {directory.name}")


def summarize():
    d = ANALYSIS / STUDIES[0]
    factor = factorial.verify(d)
    verify_report(d, factorial.report(factor))
    experiments = []
    for study, module in ((STUDIES[1], free_patch), (STUDIES[2], production)):
        d = ANALYSIS / study
        verify_report(d, module.verify(d))
        experiments.append(read(d / "results.json")["rows"])
    d = ANALYSIS / STUDIES[3]
    repeat = replica.verify(d)
    verify_report(d, replica.report(repeat))
    d = ANALYSIS / STUDIES[4]
    origin = provenance.verify(d)
    verify_report(d, provenance.report(origin))
    d = ANALYSIS / STUDIES[5]
    verify_report(d, reversal.verify(d))
    flipped = reversal.summarize(read(d / "results.json")["rows"], read(d / "calibration.json"))
    return factor, experiments, repeat, origin, flipped


def tables(factor, experiments, repeat, origin, flipped):
    result = {1: [], 2: [], 3: [], 4: [], 7: []}
    for word in ("hidden", "explicit"):
        for arm, title in (("none","neither"),("actual","actual"),("required","required"),("both","both")):
            counts = factor["cells"][word][arm]
            result[3].append([f"{word.capitalize()} / {title}", frac(counts["valid"],counts["scheduled"]),
                              frac(counts["repair_passed"],counts["repair_scored"]),
                              frac(counts["preservation_passed"],counts["preservation_scored"])])
    for label, data in zip(("QuixBugs", "Maintenance fixes"), experiments):
        for arm, shown in DISPLAY.items():
            rows = [r for r in data if r["arm"] == arm and r["status"] == "OK"]
            outcomes = []
            for state in ("faulty", "working"):
                values = [r["passes"] for r in rows if r["start"] == state]
                outcomes.append(frac(sum(values),len(values)))
            result[4].append([label,shown,*outcomes])
    for key, label in (("source","Selected implementation"),("function","Held-out pass")):
        e = repeat["estimates"][key]
        result[7].append([label, pct(e["cross_mean"]), pct(e["within_mean"]), f"{100*e['complete_mean']:+.1f}" if e["complete_mean"] is not None else "—"])
    for key, label in SOURCES.items():
        counts = origin["tracking"][key]
        result[2].append([label,frac(counts["both_aligned"],counts["complete"]),
                           str(counts["always_keep"]),str(counts["always_switch"])])
    for arm, name in (("concealed","Withheld"),("upstream","Upstream behavior"),("alternative","Alternative behavior")):
        c=Counter(flipped["arms"][arm])
        result[1].append([name,frac(c["usable"],c["scheduled"]),frac(c["success_repair"],c["total_repair"]),
                           frac(c["success_preserve"],c["total_preserve"])])
    return result


def raw_statuses():
    return {s: Counter(r["status"] for r in read(ANALYSIS/s/"results.json")["rows"]) for s in STUDIES}


def verify_stopping():
    local = read(ANALYSIS / "historical_protocol_stop_recount_20261104.json")
    rows = local["cases"]
    counted = Counter(r["stop_event"] for r in rows)
    self_labels = [r for r in rows if r["stop_event"] == "AGENT_SELF_TERMINATION"]
    nudge = sum(r["code_path_for_self_label"] == "ADAPTER_NUDGE_LIMIT" for r in self_labels)
    requested = sum(bool(r["prior_acknowledged_terminate_tool_steps"]) for r in self_labels)
    if (len({r["slot_id"] for r in rows}), nudge, requested) != (40, 38, 13) or counted != local["stop_event_counts"]:
        raise ValueError("Local controller path and request counts differ")
    with (ROOT / "external_audit_20261122/episodes.csv").open(newline="") as file:
        external = list(csv.DictReader(file))
    counts = Counter((r["series"], r["stop_class"]) for r in external)
    expected = {("A", "controller_boundary"): 6, ("A", "agent_acknowledged"): 2,
                ("A", "unknown"): 2, ("B", "unknown"): 10}
    roster = read(ROOT / "external_audit_20261122/selection.json")["slots"]
    if counts != expected or {(r["series"], r["instance_id"]) for r in external} != {(r["series"], r["instance_id"]) for r in roster}:
        raise ValueError("SWE-bench terminal episode roster or actions differ")
    print("Historical stop attribution verified from 40 local and 20 external episode records.")


def verify_swe():
    directory = ANALYSIS / "swe_recheck_20261128"
    sources = read(directory / "sources.json")
    selection = ROOT / "external_audit_20261122/selection.json"
    roster = {(r["series"], r["instance_id"]): r for r in sources["rows"]}
    pinned = [(r["series"], r["instance_id"]) for r in read(selection)["slots"]]
    if len(pinned) != 20 or len(roster) != 20 or set(pinned) != set(roster):
        raise ValueError("External source roster differs")
    baseline = {}
    for prefix in ("", "wrapper_"):
        data = read(directory / (prefix + "results.json"))
        keys = [(r["series"], r["instance_id"]) for r in data["rows"]]
        if len(keys) != 20 or set(keys) != set(roster):
            raise ValueError("Public trace outcomes omit a reserved episode")
        for key, row in zip(keys, data["rows"]):
            source = roster[key]
            if any(row[k] != source[k] for k in ("available", "trace_url", "benchmark_resolved")) or row["trace_sha256"] != source.get("raw_sha256"):
                raise ValueError("External outcome and source disagree")
            if row["available"] != (row["commands"] is not None):
                raise ValueError("Missing trajectory counted as observed")
            if prefix and any((row["commands"] or {}).get(cmd) != calls for cmd, calls in baseline[key].items()):
                raise ValueError("The wrapper extension dropped an original admitted command")
            if not prefix:
                baseline[key] = row["commands"] or {}
        if swe_recheck.report(data) != (directory / (prefix + "comparison.md")).read_text():
            raise ValueError("SWE-bench trace recount differs")
    print("SWE-bench command-repeat summaries verified from all 20 reserved rows.")


def verify_paper(paper, table_rows):
    computed = tables(*summarize())
    for n, rows in computed.items():
        if table_rows(paper,n) != rows:
            raise ValueError(f"Manuscript Table {n} differs from the released choices")
        print(f"Table {n} verified.")
    if table_rows(paper, "S8") != coverage_rows():
        raise ValueError("Manuscript coverage differs from the complete rosters")
    directory = ANALYSIS / "matplotlib_replication_20261128"
    verify_report(directory, matplotlib_replication_report.verify(directory))
    directory = ANALYSIS / "quix_rule_omission_20261128"
    omission = quix_rule_omission_report.verify(directory)
    verify_report(directory, quix_rule_omission_report.report(omission))
    for name, bound in read(ANALYSIS / "replicate_display_20261128/permutation_plan.json")["sha256"].items():
        if swe_recheck.digest((ROOT / name).read_bytes()) != bound:
            raise ValueError("Secondary randomization analysis differs from its recorded plan")
    replicate_display_permutation.verify()
    disclose = ANALYSIS / "selection_disclosure_20261128"
    verify_report(disclose, selection_disclosure_report.report(selection_disclosure_report.verify(disclose)))
    verify_stopping()
    verify_swe()
    components = production_patch_components.compute()
    production_dir = ANALYSIS / STUDIES[2]
    if components != read(production_dir / "component_scores.json") or production_patch_components.render(components) != (production_dir / "components.md").read_text():
        raise ValueError("Maintenance component grades differ")
    if matplotlib_order_types.evaluate(production_dir) != read(production_dir / "order_types.json"):
        raise ValueError("Scalar interval order types differ")
    axis_replay.verify()
    print("Recorded Matplotlib axis limits and the upstream test verdict verified for all three source versions.")
    pair_dir = ANALYSIS / "quix_contract_reversal_20261128"
    pairs = quix_contract_matched_pairs.compute(pair_dir)
    if pairs != read(pair_dir / "matched_pairs.json") or quix_contract_matched_pairs.render(pairs) != (pair_dir / "matched_pairs.md").read_text():
        raise ValueError("Matched pair grades and expressions differ")
    production_patch_examples.verify()
    quix_upstream_tests.verify()
    quix_syntax_controls.verify()
    expanded = quix_expanded_domain.compute()
    directory = quix_expanded_domain.OUT
    if expanded != read(directory / "results.json"):
        raise ValueError("Expanded input-domain grades differ")
    verify_report(directory, quix_expanded_domain.report(expanded, read(directory / "plan.json")))
    resources = feedback_resources.OUTPUT
    resource_rows = read(resources / "results.json")
    closure = read(resources / "collection_status.json")
    if closure["resource_ledger_sha256"] != swe_recheck.digest((resources / "results.json").read_bytes()) or closure["statuses"] != Counter(r["status"] for r in resource_rows["rows"]):
        raise ValueError("End-of-collection ledger differs")
    verify_report(resources, feedback_resources.recount(resource_rows))
    print("Additional expression controls, expanded finite domains, and session resource counts verified.")


def markdown_table(header, rows):
    return "\n".join("| " + " | ".join(row) + " |" for row in (header, ["---"]*len(header), *rows))
