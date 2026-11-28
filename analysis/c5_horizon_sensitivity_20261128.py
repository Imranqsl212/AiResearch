"""Reconstruct paired correctness at decisions two and three from the public C5 release."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from data.c5.check_release import verify

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/c5"
OUTPUT = ROOT / "analysis/c5_horizon_sensitivity_20261128"
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
STATE = {
    (False, False): "Neither passes",
    (True, False): "Truthful only",
    (False, True): "False-failure only",
    (True, True): "Both pass",
}
PREFIXES = (2, 3)


def retained_states(events):
    """All selected programs initially pass. Ended branches retain their last candidate."""
    correct = True
    states = []
    for index, event in enumerate(events, 1):
        if event["step"] != index:
            raise ValueError("Steps must be contiguous within each verified arm")
        if event["action"] == "ATTEMPT":
            correct = event["finite_oracle"] == "SECURE"
        states.append(correct)
    return states + [correct] * (3 - len(states))


def paired_states(rows):
    arms = defaultdict(list)
    for row in rows:
        arms[row["family"], row["pair"], row["arm"]].append(row)
    pairs = []
    for family, pair in sorted({(family, pair) for family, pair, _ in arms}):
        trajectories = [retained_states(arms[family, pair, arm]) for arm in ARMS]
        states = [tuple(path[k - 1] for path in trajectories) for k in PREFIXES]
        # false-arm failure minus truthful-arm failure equals truthful pass minus false-arm pass.
        d2, d3 = [int(truthful) - int(false) for truthful, false in states]
        pairs.append({"family": family, "pair": pair,
                      "state2": STATE[states[0]], "state3": STATE[states[1]],
                      "d2": d2, "d3": d3})
    return pairs


def summarize(pairs):
    families = defaultdict(list)
    for pair in pairs:
        families[pair["family"]].append(pair)
    summary = {"pairs": len(pairs), "families": len(families)}
    for key in ("d2", "d3"):
        totals = [sum(p[key] for p in members) for members in families.values()]
        by_family = [Fraction(total, len(members)) for total, members in zip(totals, families.values())]
        summary[key] = {"pair_weighted": str(Fraction(sum(totals), len(pairs))),
                        "family_weighted": str(sum(by_family) / len(families))}
    return summary


def audit(directory=DATA):
    verify(directory)
    data = (directory / "trajectories.jsonl").read_bytes()
    pairs = paired_states([json.loads(line) for line in data.splitlines()])
    cells = Counter((p["state2"], p["state3"]) for p in pairs)
    exclusions = {}
    within = {}
    for family in sorted({p["family"] for p in pairs}):
        within[family] = summarize([p for p in pairs if p["family"] == family])
        exclusions[family] = summarize([p for p in pairs if p["family"] != family])
    return {"data_kind": "exploratory historical sensitivity",
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "definition": "Fraction failing under FALSE_FAIL minus fraction failing under TRUTHFUL_PASS.",
            "full_cohort": summarize(pairs), "within_family": within, "leave_one_family_out": exclusions,
            "pairs": pairs, "positive_to_negative_or_negative_to_positive":
                sum(p["d2"] * p["d3"] < 0 for p in pairs),
            "paired_transitions": {s: {t: cells[s, t] for t in STATE.values()} for s in STATE.values()}}


def percentage(value):
    return f"{100 * Fraction(value):+.1f}" if Fraction(value) else "0.0"


def report(a):
    cohort = a["full_cohort"]
    rows = [
        "# Which pairs account for the historical reversal?",
        "",
        f"The public ledger contains {cohort['pairs']} paired continuations across {cohort['families']} selected task families. Each started from a verified program with a known three-decision limit. After an early stop the recorded final candidate is carried forward. All outcomes below concern the retained candidate's bounded correctness.",
        "",
        "## Changes in paired outcomes",
        "",
        "Rows give the pair's outcome after decision two and columns after decision three. Each history pair contributes once. A pass refers to the finite reference. The two middle categories identify the feedback arm whose candidate passes.",
        "",
        "| At decision two / at decision three | " + " | ".join(STATE.values()) + " |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for before, transitions in a["paired_transitions"].items():
        rows.append(f"| {before} | " + " | ".join(str(transitions[t]) for t in STATE.values()) + " |")
    changed = [p for p in a["pairs"] if p["d2"] != p["d3"]]
    family_switches = sum(Fraction(f["d2"]["pair_weighted"]) * Fraction(f["d3"]["pair_weighted"]) < 0
                          for f in a["within_family"].values())
    rows += [
        "",
        f"In {a['positive_to_negative_or_negative_to_positive']}/{cohort['pairs']} pairs, the sole passing arm switched from one side to the other. The paired difference changed in {len(changed)}/{cohort['pairs']} pairs across {len(set(p['family'] for p in changed))} families. Within-family means crossed from strictly positive to strictly negative or vice versa in {family_switches}/{cohort['families']} families. The JSON lists the states and contrasts for every pair and family.",
        "",
        "## Sensitivity to omitting one family",
        "",
        "A positive contrast means more failing candidates under false feedback. The first weighting gives each pair equal weight. The second takes the mean paired contrast within each family and weights those family means equally. Entries are percentage-point differences rounded to one decimal place. The JSON preserves exact fractions.",
        "",
        "| Family omitted | Retained pairs | Pair-weighted at 2 | Pair-weighted at 3 | Family-weighted at 2 | Family-weighted at 3 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in [("None", cohort), *a["leave_one_family_out"].items()]:
        contrasts = [percentage(item[decision][weight]) for weight in ("pair_weighted", "family_weighted")
                     for decision in ("d2", "d3")]
        rows.append(f"| {name} | {item['pairs']} | " + " | ".join(contrasts) + " |")
    rows += [
        "",
        "These deletions measure sensitivity to the composition of the observed cohort. They reuse histories and do not yield independent replications, sampling intervals, or estimates of what an agent would have done under an announced two-decision budget.",
        "",
        "Run `python3 -B -m analysis.c5_horizon_sensitivity_20261128` from the repository root to verify both files against the released trajectory ledger.",
    ]
    return "\n".join(rows) + "\n"


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write", action="store_true", help="Regenerate the two analysis outputs.")
    args = cli.parse_args()
    results = audit()
    outputs = {"results.json": json.dumps(results, indent=2) + "\n", "comparison.md": report(results)}
    if args.write:
        OUTPUT.mkdir(exist_ok=True)
        for name, value in outputs.items():
            (OUTPUT / name).write_text(value, encoding="utf-8")
    else:
        for name, value in outputs.items():
            if (OUTPUT / name).read_text(encoding="utf-8") != value:
                raise ValueError(f"{name} differs from the replay")
        print("Verified paired trajectories and all family exclusions.")


if __name__ == "__main__":
    main()
