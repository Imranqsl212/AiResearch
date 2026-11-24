"""Model-free C5 planning, paired summaries and verified historical descriptions.

No network/model calls; no prospective eligibility is created. Inference is
opt-in and assumption-dependent, never authentication or release clearance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import NormalDist, fmean
from typing import Any

from analysis.power_simulation import (
    _regularized_beta, student_t_critical_one_sided, student_t_survival,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "c5-statistical-plan-20261123-v1"
MIN_FAMILIES = 15


def binomial_cdf(k: int, n: int, p: float) -> float:
    if n < 0 or not 0 <= p <= 1:
        raise ValueError("invalid binomial parameters")
    if k < 0:
        return 0.0
    if k >= n or p == 0:
        return 1.0
    if p == 1:
        return 0.0
    return _regularized_beta(1 - p, n - k, k + 1)


def exact_mcnemar(treatment_only: int, control_only: int) -> float:
    """IID-pair reference test; not appropriate for nested pairs as independent units."""
    if any(type(v) is not int or v < 0 for v in (treatment_only, control_only)):
        raise ValueError("discordant counts must be nonnegative integers")
    return min(1.0, 2 * binomial_cdf(min(treatment_only, control_only),
                                   treatment_only + control_only, 0.5))


@lru_cache(maxsize=None)
def _critical_discordance(m: int, alpha: float) -> int:
    low, high = -1, m // 2
    while low < high:
        k = (low + high + 1) // 2
        if 2 * binomial_cdf(k, m, 0.5) <= alpha:
            low = k
        else:
            high = k - 1
    return low


def exact_iid_power(n: int, delta: float, discordance: float, alpha: float) -> float:
    """Average exact conditional McNemar rejection over M~Binomial(n,q).

    P(D=+1)=(q+delta)/2, P(D=-1)=(q-delta)/2. Concordant
    cells need not be specified for this reference calculation.
    """
    if type(n) is not int or n < 1 or not 0 < alpha < 1:
        raise ValueError("invalid n/alpha")
    if not 0 < discordance <= 1 or abs(delta) > discordance:
        raise ValueError("require |delta| <= discordance <= 1")
    theta = (discordance + delta) / (2 * discordance)
    total = 0.0
    for m in range(n + 1):
        if discordance == 1:
            weight = float(m == n)
        else:
            weight = math.exp(math.lgamma(n + 1) - math.lgamma(m + 1)
                              - math.lgamma(n - m + 1) + m * math.log(discordance)
                              + (n - m) * math.log1p(-discordance))
        k = _critical_discordance(m, alpha)
        if k >= 0:
            reject = binomial_cdf(k, m, theta) + binomial_cdf(k, m, 1 - theta)
            total += weight * reject
    return min(1.0, max(0.0, total))


def approximate_iid_pairs(delta: float, discordance: float, alpha: float,
                          power: float = 0.8) -> int:
    if not 0 < abs(delta) <= discordance <= 1 or not 0 < alpha < 1 or not 0.5 < power < 1:
        raise ValueError("invalid planning assumptions")
    z = NormalDist()
    return math.ceil((z.inv_cdf(1 - alpha / 2) * math.sqrt(discordance)
                      + z.inv_cdf(power) * math.sqrt(discordance - delta * delta)) ** 2
                     / (delta * delta))


def family_interval(values: list[float], *, alpha: float = 0.05) -> dict[str, Any]:
    """Student-t approximation across independent family aggregates, not action rows."""
    if not 0 < alpha < 1 or any(not math.isfinite(x) or not -1 <= x <= 1 for x in values):
        raise ValueError("invalid family values or alpha")
    n = len(values)
    out = {"estimate": fmean(values) if values else None, "n_families": n,
           "ci_low": None, "ci_high": None, "p_value": None,
           "method": "NOT_ESTIMABLE"}
    if n < MIN_FAMILIES:
        return out
    mean = fmean(values)
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    if variance == 0:
        return out
    se = math.sqrt(variance / n)
    critical = student_t_critical_one_sided(n - 1, alpha / 2)
    out.update(ci_low=max(-1.0, mean - critical * se),
               ci_high=min(1.0, mean + critical * se),
               p_value=min(1.0, 2 * student_t_survival(abs(mean / se), n - 1)),
               method="equal-family Student-t approximation; independent-family assumption")
    return out


def holm(p_values: list[float | None]) -> list[float | None]:
    """Keep every planned hypothesis; missing tests consume their original slot."""
    if any(p is not None and (type(p) not in (int, float) or not math.isfinite(p)
                             or not 0 <= p <= 1) for p in p_values):
        raise ValueError("invalid p-value")
    result: list[float | None] = [None] * len(p_values)
    running = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)),
                                       key=lambda i: 1 if p_values[i] is None else p_values[i])):
        p = p_values[index]
        if p is not None:
            running = max(running, min(1.0, (len(p_values) - rank) * p))
            result[index] = running
    return result


def summarize_pairs(rows: list[dict[str, Any]], *, inference: bool = False) -> dict[str, Any]:
    """One model/contrast/endpoint per call; control,treatment binary or null.

    All scheduled selected-onset pairs, including missing branches, are required.
    No-onset precursors are a separate population and must not be inserted here.
    Input roster completeness/provenance must be verified upstream.
    """
    seen = set()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not all(isinstance(row.get(k), str) and row[k] for k in ("pair_id", "family")):
            raise ValueError("pair_id and family required")
        if row["pair_id"] in seen:
            raise ValueError("duplicate pair_id")
        seen.add(row["pair_id"])
        for arm in ("control", "treatment"):
            if arm not in row or (row[arm] is not None and
                                   (type(row[arm]) not in (int, bool) or row[arm] not in (0, 1))):
                raise ValueError("binary outcome or explicit null required")
        groups[row["family"]].append(row)
    family_rows = []
    table = {"neither": 0, "control_only": 0, "treatment_only": 0, "both": 0}
    for family, members in sorted(groups.items()):
        complete = [r for r in members if r["control"] is not None and r["treatment"] is not None]
        ds = [int(r["treatment"]) - int(r["control"]) for r in complete]
        for r in complete:
            table[("both" if r["control"] and r["treatment"] else "control_only" if r["control"]
                   else "treatment_only" if r["treatment"] else "neither")] += 1
        lower = fmean((0 if r["treatment"] is None else int(r["treatment"]))
                      - (1 if r["control"] is None else int(r["control"])) for r in members)
        upper = fmean((1 if r["treatment"] is None else int(r["treatment"]))
                      - (0 if r["control"] is None else int(r["control"])) for r in members)
        family_rows.append({"family": family, "scheduled_pairs": len(members),
                            "complete_pairs": len(complete), "difference": fmean(ds) if ds else None,
                            "control_rate": fmean(int(r["control"]) for r in complete) if complete else None,
                            "treatment_rate": fmean(int(r["treatment"]) for r in complete) if complete else None,
                            "missing_bound_low": lower, "missing_bound_high": upper})
    values = [r["difference"] for r in family_rows if r["difference"] is not None]
    complete_count = sum(table.values())
    result = {"scheduled_pairs": len(rows), "complete_pairs": complete_count,
              "incomplete_pairs": len(rows) - complete_count, "scheduled_families": len(groups),
              "contributing_families": len(values), "pair_table": table,
              "pair_weighted_difference": ((table["treatment_only"] - table["control_only"])
                                             / complete_count if complete_count else None),
              "equal_family_difference": fmean(values) if values else None,
              "discordance_rate": ((table["treatment_only"] + table["control_only"])
                                    / complete_count if complete_count else None),
              "missing_bound_low": fmean(r["missing_bound_low"] for r in family_rows) if family_rows else None,
              "missing_bound_high": fmean(r["missing_bound_high"] for r in family_rows) if family_rows else None,
              "family_rows": family_rows, "population_inference": None,
              "leave_one_family_out": [fmean(values[:i] + values[i+1:]) for i in range(len(values))]
                                      if len(values) > 1 else []}
    if inference:
        result["population_inference"] = {
            "difference": family_interval(values),
            "control_rate": family_interval([r["control_rate"] for r in family_rows if r["control_rate"] is not None]),
            "treatment_rate": family_interval([r["treatment_rate"] for r in family_rows if r["treatment_rate"] is not None]),
            "warning": "Model-based approximation, conditional on contributing families; not source validation or confirmatory eligibility.",
        }
        for key in ("control_rate", "treatment_rate"):
            interval = result["population_inference"][key]
            if interval["ci_low"] is not None:
                interval["ci_low"] = max(0.0, interval["ci_low"])
    return result


def cluster_power(*, families: int, pairs_per_family: int, delta: float,
                  discordance: float, icc: float, reach: float, loss: float,
                  alpha: float, replicates: int, seed: int) -> dict[str, Any]:
    """Synthetic Dirichlet-multinomial paired differences; ICC is for D, not Y."""
    if families < MIN_FAMILIES or pairs_per_family < 1 or replicates < 1:
        raise ValueError("invalid simulation size")
    if not 0 <= abs(delta) <= discordance <= 1 or not 0 <= icc < 1 or not 0 < reach <= 1 or not 0 <= loss < 1:
        raise ValueError("invalid simulation assumptions")
    if not 0 < alpha < 1:
        raise ValueError("invalid alpha")
    rng = random.Random(seed)
    probabilities = [(discordance - delta) / 2, 1 - discordance, (discordance + delta) / 2]
    critical = {f: student_t_critical_one_sided(f - 1, alpha / 2)
                for f in range(MIN_FAMILIES, families + 1)}
    rejected = estimable = pairs = total_families = 0
    for _ in range(replicates):
        values = []
        for _family in range(families):
            if icc:
                concentration = (1 - icc) / icc
                draws = [rng.gammavariate(p * concentration, 1) if p else 0 for p in probabilities]
                denom = sum(draws)
                if denom == 0:
                    raise ValueError("Dirichlet gamma draws underflowed; unsupported extreme ICC/probabilities")
                probs = [v / denom for v in draws]
            else:
                probs = probabilities
            ds = []
            for _pair in range(pairs_per_family):
                if rng.random() >= reach or rng.random() < loss:
                    continue
                x = rng.random()
                ds.append(-1 if x < probs[0] else 0 if x < probs[0] + probs[1] else 1)
            pairs += len(ds)
            if ds:
                values.append(fmean(ds))
        n = len(values)
        total_families += n
        if n < MIN_FAMILIES:
            continue
        mean = fmean(values)
        ss = sum((v - mean) ** 2 for v in values)
        if not ss:
            continue
        estimable += 1
        rejected += abs(mean) / math.sqrt(ss / ((n - 1) * n)) > critical[n]
    rate = rejected / replicates
    z = 1.959963984540054
    denom = 1 + z*z/replicates
    center = (rate + z*z/(2*replicates))/denom
    half = z*math.sqrt(rate*(1-rate)/replicates+z*z/(4*replicates**2))/denom
    return {"families": families, "pairs_per_family": pairs_per_family, "delta": delta,
            "discordance": discordance, "difference_icc": icc, "reach": reach, "pair_loss": loss,
            "alpha": alpha, "replicates": replicates, "seed": seed, "rejections": rejected,
            "rejection_probability": rate, "monte_carlo_low": max(0.0, center-half),
            "monte_carlo_high": min(1.0, center+half), "nonestimable": replicates-estimable,
            "mean_complete_pairs": pairs/replicates, "mean_contributing_families": total_families/replicates}


def budget(models: int, families: int, prompts: int, repeats: int = 5) -> dict[str, int | float]:
    if models not in (4, 5, 6) or families < 1 or prompts not in (2, 3) or repeats < 5:
        raise ValueError("budget requires 4–6 models, 2–3 prompts and at least 5 repeats")
    cells = models * families * prompts * repeats
    aa_pairs = 2 * cells
    return {"models": models, "families": families, "prompts": prompts, "repeats": repeats,
            "c1_c2_precursors": 2*cells, "c3_c4_full_episodes": 2*cells,
            "c5_pair_reservations": 2*cells, "c5_continuations_max": 4*cells,
            "aa_pair_reservations": aa_pairs, "aa_continuations_max": 2*aa_pairs,
            "total_episode_or_branch_max": 8*cells+2*aa_pairs,
            "provider_decisions_max": 36*cells+6*aa_pairs}


def historical() -> dict[str, Any]:
    # Existing readers verify archived bytes and replay bounded data structures;
    # no arbitrary candidate source, model, provider API, or external process runs.
    from analysis.audit_c5_remaining_onsets import audit
    from analysis.c5_paired_regression_recount_20261101 import recount
    from analysis.fresh_matched_verdict_pilot_20261101 import build_report as first_wave
    from analysis.v7_second_wave_20261101 import build_report as second_wave
    checked = [("analysis/c5_remaining_onsets_audit_20261005.json", audit()),
               ("analysis/c5_paired_regression_recount_20261101.json", recount()),
               ("analysis/fresh_matched_verdict_pilot_20261101.json", first_wave()),
               ("analysis/v7_second_wave_20261101.json", second_wave())]
    hashes = {}
    for name, actual in checked:
        raw = (ROOT/name).read_bytes()
        if json.loads(raw) != actual:
            raise ValueError(f"historical replay differs from saved result: {name}")
        hashes[name] = hashlib.sha256(raw).hexdigest()
    old, regression, first, second = [d for _, d in checked]
    reg = {r["slot_id"]: r for r in regression["pairs"]}
    groups: dict[str, list[dict[str, Any]]] = {"persistent_veto_14_pairs": []}
    for row in old["rows"]:
        for endpoint, key in (("early_stop", "early_voluntary_stop"),
                              ("terminal_regression", "final_finite_property_regression"),
                              ("temporary_regression", "any_post_onset_finite_regression")):
            arms = row["arms"] if endpoint == "early_stop" else reg[row["slot_id"]]["arms"]
            groups["persistent_veto_14_pairs"].append({"pair_id":row["slot_id"], "family":row["family"],
                         "endpoint":endpoint, "control":arms["TRUTHFUL_PASS"][key],
                         "treatment":arms["FALSE_FAIL"][key]})
    for name, section in (("one_shot_first_wave", first["fresh_schedule"]),
                          ("one_shot_second_wave", second["second_wave"])):
        groups[name] = []
        for row in section["slots"]:
            if row["pair"] is None:
                continue  # Valid no-onset is counted in reach, never a zero pair.
            for endpoint, key in (("early_stop", "early_voluntary_stop"),
                                  ("terminal_regression", "terminal_finite_property_regression")):
                arms = row["pair"]["arms"]
                groups[name].append({"pair_id":row["family"], "family":row["family"],
                                     "endpoint":endpoint, "control":arms["TRUTHFUL_PASS"][key],
                                     "treatment":arms["FALSE_FAIL"][key]})
    summaries = []
    pair_rows = []
    for cohort, rows in groups.items():
        for endpoint in sorted({r["endpoint"] for r in rows}):
            selected = [r for r in rows if r["endpoint"] == endpoint]
            summary = summarize_pairs(selected)
            summaries.append({"cohort":cohort, "endpoint":endpoint, "summary":summary})
        pair_rows += [dict(cohort=cohort, **r) for r in rows]
    return {"status":"EXCLUDED_POST_HOC_DESCRIPTIVE_ONLY", "eligible_for_main_analysis":False,
            "verified_source_results_sha256":hashes, "summaries":summaries, "pairs":pair_rows,
            "reach":{"persistent_veto":{"scheduled":40,"valid":30,"onsets":14},
                     "one_shot_first_wave":{"scheduled":4,"onsets":3},
                     "one_shot_second_wave":{"scheduled":4,"onsets":2}},
            "limitations":["Selected, excluded cohorts; no population intervals or causal p-values.",
                           "Persistent and one-shot feedback and sequential waves are not pooled.",
                           "No new model run; finite-property labels do not establish general security."]}


def _csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def generate(replicates: int = 2000) -> dict[str, str]:
    power = []
    for effect in (0.1, 0.2):
        for q in (0.2, 0.3, 0.5):
            for alpha in (0.05, 0.04/4, 0.04/6):
                n = approximate_iid_pairs(effect, q, alpha)
                power.append({"absolute_effect":effect,"discordance":q,"alpha":alpha,
                              "normal_approx_pairs_for_80pct":n,
                              "exact_power_at_approx_n":exact_iid_power(n,effect,q,alpha),
                              "exact_power_at_100_pairs":exact_iid_power(100,effect,q,alpha)})
    simulations = []
    for families in (20, 40):
        for prompts in (2, 3):
            for q in (0.2, 0.5):
                for icc in (0.0, 0.2):
                    for models in (4, 6):
                        for effect in (0.0, -0.1, -0.2):
                            settings = dict(families=families,pairs_per_family=10*prompts,delta=effect,
                                            discordance=q,icc=icc,reach=0.5,loss=0.05,alpha=0.04/models)
                            seed = int(hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:12],16)
                            row = cluster_power(**settings,replicates=replicates,seed=seed)
                            row.update(models=models,prompts=prompts)
                            simulations.append(row)
    # Lower/higher reach and severe technical pair loss are planning stresses,
    # not estimates inferred from precursor failures in the old pilot.
    for families in (20, 40):
        for reach in (0.35, 0.8):
            for effect in (0.0, -0.1, -0.2):
                settings = dict(families=families,pairs_per_family=20,delta=effect,
                                discordance=0.5,icc=0.2,reach=reach,loss=0.25,alpha=0.04/6)
                seed = int(hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:12],16)
                row = cluster_power(**settings,replicates=replicates,seed=seed)
                row.update(models=6,prompts=2)
                simulations.append(row)
    budgets = [budget(m,f,p) for m in (4,6) for f in (20,40) for p in (2,3)]
    old = historical()
    summary_rows = []
    family_rows = []
    for row in old["summaries"]:
        s = row["summary"]
        summary_rows.append({"cohort":row["cohort"],"endpoint":row["endpoint"],
            **{k:s[k] for k in ("complete_pairs","contributing_families","pair_weighted_difference",
                               "equal_family_difference","discordance_rate")},
            **s["pair_table"],"population_ci":"NOT_ESTIMATED","causal_p_value":"NOT_ESTIMATED"})
        family_rows += [dict(cohort=row["cohort"],endpoint=row["endpoint"],**f) for f in s["family_rows"]]
    result = {"version":VERSION,"status":"PROSPECTIVE_UNFROZEN_DRAFT_AND_EXCLUDED_DESCRIPTIONS",
              "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "eligible_for_main_analysis":False,"iid_power":power,"cluster_power":simulations,
              "budgets":budgets,"historical":old,
              "simulation_notes":["Synthetic planning only; no model outputs generated.",
               "Alpha is first Holm threshold .04/M: conservative per-model benchmark, not joint multi-model power.",
               "ICC refers to within-family paired differences; reach and technical loss are independent in this grid.",
               "Null rows check this simulation's rejection behavior; they do not validate a real population model."]}
    return {"planning.json":json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",
            "iid_power.csv":_csv(power),"cluster_power.csv":_csv(simulations),"budget.csv":_csv(budgets),
            "historical_summary.csv":_csv(summary_rows),"historical_pairs.csv":_csv(old["pairs"]),
            "historical_families.csv":_csv(family_rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--output-directory",type=Path,required=True)
    plan.add_argument("--replicates",type=int,default=2000)
    plan.add_argument("--check",action="store_true")
    summary = sub.add_parser("summarize")
    summary.add_argument("--input",type=Path,required=True)
    summary.add_argument("--output",type=Path,required=True)
    summary.add_argument("--assume-independent-families",action="store_true")
    args = parser.parse_args()
    if args.command == "summarize":
        data = json.loads(args.input.read_text())
        if data.get("schema_version") != "c5-paired-endpoint-table-v1" or not isinstance(data.get("rows"),list):
            parser.error("expected c5-paired-endpoint-table-v1 with rows for one model/contrast/endpoint")
        if (not isinstance(data.get("model"), str) or not data["model"]
                or data.get("contrast") not in {"C5", "C4_C3", "AA"}
                or data.get("endpoint") not in {"early_stop", "terminal_regression", "temporary_regression"}):
            parser.error("one model, contrast C5/C4_C3/AA and named endpoint required")
        for row in data["rows"]:
            if any(key in row and row[key] != data[key] for key in ("model", "contrast", "endpoint")):
                parser.error("mixed model/contrast/endpoint rows are not allowed")
        out = summarize_pairs(data["rows"],inference=args.assume_independent_families)
        out.update(model=data["model"],contrast=data["contrast"],endpoint=data["endpoint"],input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                   confirmatory_eligibility="NOT_ATTESTED_BY_THIS_TOOL")
        with args.output.open("x",encoding="utf-8") as stream:
            json.dump(out,stream,indent=2,sort_keys=True,allow_nan=False)
            stream.write("\n")
    else:
        if args.output_directory.exists() and not args.check:
            parser.error("output directory already exists; preserve prior artifacts")
        outputs = generate(args.replicates)
        if args.check:
            for name,text in outputs.items():
                if (args.output_directory/name).read_text() != text:
                    raise ValueError(f"saved output differs: {name}")
            print("VERIFIED_C5_STATISTICAL_PLANNING_AND_HISTORICAL_DESCRIPTIONS")
        else:
            args.output_directory.mkdir(parents=True,exist_ok=False)
            for name,text in outputs.items():
                with (args.output_directory/name).open("x",encoding="utf-8",newline="") as stream:
                    stream.write(text)
            print(args.output_directory)


if __name__ == "__main__":
    main()
