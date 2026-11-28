"""Recount the paper's feedback comparisons from public files, without model access."""
from ast import literal_eval
from hashlib import sha256
import json
from pathlib import Path
import re

from analysis import checker_timing_pilot_20261126 as timing
from analysis import pprint_postedit_report as postedit
from analysis import pprint_display_report as display
from analysis import reference_example_report as reference
from analysis import cross_project_display_report as cross
from analysis import c5_horizon_sensitivity_20261128 as historical
from data.c5.check_release import verify as verify_historical_release
from paper.c5 import check_effort, followup_results

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"


def read(path):
    return json.loads(path.read_bytes())


def must_equal(found, expected, description):
    if found != expected:
        raise ValueError(f"{description}: {found!r} != {expected!r}")


def table_rows(text, number):
    pattern = rf"^\*\*Table {number}\.[^\n]*\n\n((?:\|[^\n]+\n)+)"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ValueError(f"Cannot locate manuscript Table {number}")
    return [[field.strip() for field in line.strip("|").split("|")] for line in match[1].splitlines()[2:]]


def fraction(flags):
    return f"{sum(flags)}/{len(flags)}" if flags else "—"


def check_timing(paper):
    directory = ANALYSIS / "checker_timing_20261126"
    data = read(directory / "results.json")
    must_equal(timing.render(data), (directory / "comparison.md").read_text(), "Timing report")
    table = table_rows(paper, 5)
    for col, arm in enumerate(("early", "late"), 1):
        episodes = [ep for ep in data["episodes"] if ep["timing"] == arm]
        outcomes = []
        for turn, state, success in ((1,"defective",True),(1,"correct",False),(2,"defective",True),
                                     (2,"correct",False),(2,None,True)):
            values = [ep["steps"][turn-1]["correct_after"] is success for ep in episodes
                      if (state is None or ep["state"] == state) and len(ep["steps"]) >= turn
                      and ep["steps"][turn-1]["status"] == "OK"]
            outcomes.append(fraction(values))
        must_equal([row[col] for row in table], outcomes, f"Table 5, {arm}")
    print("Table 5 verified against the two-decision timing ledger.")


def check_displays(paper):
    for number, directory, arms in (
        (6, ANALYSIS/"pprint_postedit_20261127", postedit.PROBES),
        ("S1", ANALYSIS/"pprint_display_20261128", display.ARMS),
    ):
        ledger = read(directory/"results.json")
        report = postedit.render(ledger) if number == 6 else display.replay(directory)
        must_equal(report, (directory/"comparison.md").read_text(), f"Display report {number}")
        table = table_rows(paper, number)
        must_equal(len(table), len(arms), f"Table {number} row count")
        variants = read(directory/"calibration.json")["variants"]
        for row, arm in zip(table, arms):
            key = "arm" if number == "S1" else "probe"
            selections = [r for r in ledger["rows"] if r[key] == arm and r["status"] == "OK"]
            faulty = [r for r in selections if not r["before_correct"]]
            working = [r for r in selections if r["before_correct"]]
            fixed = fraction([all(t["passed"] for t in variants[r["after_variant"]]["checks"]) for r in faulty])
            preserved = fraction([all(t["passed"] for t in variants[r["after_variant"]]["checks"]) for r in working])
            if number == 6:
                bad_versions = {r["before_variant"] for r in faulty}
                if len(bad_versions) != 1:
                    raise ValueError("Table 6 assumes a single faulty starting implementation")
                bad_variant, = bad_versions
                probe = {"1,2": "single", "2,10": "mixed"}[arm]
                rendered = literal_eval(variants[bad_variant]["outputs"][probe])
                order = " then ".join(map(str, rendered))
                must_equal(row, [arm.replace(",", " and "), order, fixed, preserved], f"Table 6, {arm}")
            else:
                rewrites = fraction([r["after_correct"] and r["before_variant"] != r["after_variant"] for r in working])
                label = {"none": "No new output", "shared": "Keys 3 and 7", "revealing": "Keys 3 and 20"}[arm]
                must_equal(row, [label, fixed, preserved, rewrites], f"Table S1, {arm}")
        print(f"Table {number} verified against menu selections and held-out checks.")


def check_reference(paper):
    directory = ANALYSIS/"reference_example_20261128"
    summary = reference.verify(directory)
    must_equal(reference.report(summary), (directory/"comparison.md").read_text(), "Reference example report")
    table = table_rows(paper, "S3")
    modes = summary["modes"]
    expected = []
    for arm, name in (("none","None"), ("shared","Shared example"), ("revealing","Distinguishing example")):
        stats = modes[arm]
        cells = [name, f"{stats['valid_calls']}/{stats['scheduled_calls']}"]
        for state in ("repair","preservation"):
            assessed = stats["assessed_" + state]
            cells.append(f"{stats['correct_' + state]}/{assessed}" if assessed else "—")
        expected.append(cells)
    must_equal(table, expected, "Table S3")
    print("Table S3 verified. Blocks choosing the correct program for both target answers:",
          summary["primary"]["both_correct"], "of", summary["blocks"])


def check_projects(paper):
    directory = ANALYSIS / "cross_project_display_20261128"
    must_equal(cross.replay(directory), (directory / "comparison.md").read_text(), "Cross-project report")
    rows = read(directory / "results.json")["rows"]
    expected = []
    for project, name in (("dateutil", "dateutil"), ("cpython", "CPython")):
        for arm, label in (("none", "None"), ("shared", "Shared output"), ("revealing", "Revealing output")):
            group = [r for r in rows if r["project"] == project and r["arm"] == arm and r["status"] == "OK"]
            expected.append([name, label] + [fraction([r["after_correct"] for r in group if r["before_correct"] is state])
                                              for state in (False, True)])
    must_equal(table_rows(paper, "S2"), expected, "Table S2")
    print("Table S2 verified against the seven starting implementations and matched decisions.")


def verify():
    sums = ROOT/"SHA256SUMS"
    if sums.is_file():
        for line in sums.read_text().splitlines():
            digest, name = line.split("  ", 1)
            must_equal(sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    for name in ("checker_timing_20261126", "pprint_postedit_20261127", "pprint_display_20261128", "reference_example_20261128", "cross_project_display_20261128", *followup_results.STUDIES):
        study = ANALYSIS / name
        plan = read(study / "plan.json")
        must_equal(sha256((study / "plan.json").read_bytes()).hexdigest(),
                   read(study / "results.json")["plan_sha256"], f"{name} plan digest")
        key = "workflow_sha256" if name == "matplotlib_replication_20261128" else "source_sha256"
        for path, digest in plan[key].items():
            must_equal(sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)
    paper = (ROOT/"paper/c5/manuscript.md").read_text()
    audit = historical.audit()
    hist = ANALYSIS/"c5_horizon_sensitivity_20261128"
    must_equal(audit, read(hist/"results.json"), "Historical paired outcomes")
    must_equal(historical.report(audit), (hist/"comparison.md").read_text(), "Historical report")
    ledger = verify_historical_release(ROOT / "data/c5")
    keys = ("early_stop", "first_inspect", "ever_regressed", "final_regressed", "submissions")
    must_equal([row[1:] for row in table_rows(paper, "S4")],
               [[str(n) for n in ledger[key + "_PASS_FAIL"]] for key in keys], "Table S4")
    print("Table S4 and the paired transitions of Figure S2 verified from the 78 historical decisions.")
    check_effort.verify(ANALYSIS/"c5_effort_panel_20261124.json", ANALYSIS/"c5_codex_effort_20261124/results.json",
                        ROOT/"docs/c5_codex_catalog_20261124.json")
    print("Code and effort comparisons verified from the released effort ledger.")
    check_timing(paper)
    check_displays(paper)
    check_projects(paper)
    check_reference(paper)
    followup_results.verify_paper(paper,table_rows)


if __name__ == "__main__":
    verify()
