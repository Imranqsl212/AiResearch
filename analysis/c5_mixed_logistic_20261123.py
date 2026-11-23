"""Optional Bayesian mixed-logistic sensitivity; never fits historical pilots.

Requires the separate pinned optional dependencies. Only the synthetic smoke
fixture is exercised during development. Posterior intervals are variational
approximations, not frequentist confidence intervals or confirmatory p-values.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import random
import re
import warnings
from pathlib import Path
from typing import Any

from analysis.c5_statistical_plan_20261123 import summarize_pairs

VERSION = "c5-mixed-logistic-sensitivity-20261123-v1"
SCHEMA = "c5-glmm-branch-table-v1"
MIN_FAMILIES = 15


class AnalysisRefusal(ValueError):
    """An explicit analysis boundary, not a silently repaired dataset."""


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def validate_input(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if data.get("schema_version") != SCHEMA:
        raise AnalysisRefusal("unsupported input schema")
    if data.get("data_kind") not in {"SYNTHETIC_CALIBRATION", "PROSPECTIVE_REPLAY_VERIFIED"}:
        raise AnalysisRefusal("historical/excluded/unspecified data are forbidden for this sensitivity fit")
    if data.get("contrast") not in {"C5","C4_C3","AA"} or data.get("endpoint") not in {"early_stop","terminal_regression"}:
        raise AnalysisRefusal("one named contrast and endpoint required")
    models = data.get("models")
    prompts = data.get("prompts")
    for values, low, high, name in ((models,4,6,"models"),(prompts,2,3,"prompts")):
        if (not isinstance(values,list) or not low <= len(values) <= high
                or any(not isinstance(v,str) or not v for v in values) or len(set(values)) != len(values)):
            raise AnalysisRefusal(f"freeze {low}–{high} distinct {name}")
    roster = data.get("pair_roster")
    rows = data.get("rows")
    if not isinstance(roster,list) or not roster or not isinstance(rows,list):
        raise AnalysisRefusal("explicit nonempty pair roster and branch rows required")
    pairs = {}
    for item in roster:
        if not all(isinstance(item.get(k),str) and item[k] for k in
                   ("pair_id","model","family","prompt","precursor_condition","pair_source_sha256")):
            raise AnalysisRefusal("pair metadata incomplete")
        if item["model"] not in models or item["prompt"] not in prompts:
            raise AnalysisRefusal("unplanned model/prompt")
        if not re.fullmatch(r"[0-9a-f]{64}",item["pair_source_sha256"]):
            raise AnalysisRefusal("source SHA-256 required")
        if data["contrast"] in {"C5","AA"} and item["precursor_condition"] not in {"C1","C2"}:
            raise AnalysisRefusal("C5/AA precursor must be C1 or C2")
        key=(item["model"],item["pair_id"])
        if key in pairs:
            raise AnalysisRefusal("duplicate roster pair")
        pairs[key] = {"metadata":dict(item),"arms":{}}
    for row in rows:
        key=(row.get("model"),row.get("pair_id"))
        if key not in pairs or type(row.get("treatment")) is not int or row["treatment"] not in (0,1):
            raise AnalysisRefusal("unplanned pair or treatment")
        pair=pairs[key]
        treatment=row["treatment"]
        if treatment in pair["arms"]:
            raise AnalysisRefusal("duplicate branch")
        status=row.get("validity")
        outcome=row.get("outcome")
        if status == "VALID":
            if type(outcome) not in (bool,int) or outcome not in (0,1):
                raise AnalysisRefusal("valid branch must have binary endpoint")
        elif status in {"TECHNICAL_INVALID","UNSTARTED"}:
            if outcome is not None:
                raise AnalysisRefusal("missing/invalid branch endpoint must be null")
        else:
            raise AnalysisRefusal("explicit validity required")
        pair["arms"][treatment]=dict(row)
    complete=[]
    counts={"scheduled_pairs":len(pairs),"complete_pairs":0,"incomplete_pairs":0,
            "excluded_pair_ids":[],"model_pair_summaries":{},
            "source_validation":"Declared pair source hashes/roster checked for consistency only; upstream replay not independently attested."}
    for model in models:
        descriptive=[]
        for (m,pair_id),pair in pairs.items():
            if m != model: continue
            if set(pair["arms"]) != {0,1}:
                raise AnalysisRefusal("all scheduled branches, including missing ones, must be explicit")
            meta=pair["metadata"]
            outcomes=[pair["arms"][t]["outcome"] for t in (0,1)]
            descriptive.append({"pair_id":pair_id,"family":meta["family"],
                                "control":outcomes[0],"treatment":outcomes[1]})
            if any(v is None for v in outcomes):
                counts["incomplete_pairs"]+=1
                counts["excluded_pair_ids"].append({"model":model,"pair_id":pair_id,
                    "validity":[pair["arms"][t]["validity"] for t in (0,1)]})
                continue
            counts["complete_pairs"]+=1
            # Delimited JSON prevents collisions from ':' in user-supplied IDs.
            cluster=json.dumps([meta["family"],model,pair_id],separators=(",",":"))
            for treatment in (0,1):
                complete.append(dict(meta,treatment=treatment,outcome=int(outcomes[treatment]),pair_cluster=cluster))
        summary=summarize_pairs(descriptive)
        counts["model_pair_summaries"][model]=summary
        if summary["contributing_families"] < MIN_FAMILIES:
            raise AnalysisRefusal(f"insufficient complete-pair families for {model}: require {MIN_FAMILIES}")
    if len({r["outcome"] for r in complete}) < 2:
        raise AnalysisRefusal("degenerate all-zero/all-one endpoint; fixed-effect separation")
    counts["complete_branches"]=len(complete)
    counts["complete_families"]=len({r["family"] for r in complete})
    return complete,counts


def separation_kind(x: Any, y: Any) -> str | None:
    """Linear-program feasibility check for fixed-design complete/quasi separation."""
    import numpy as np
    from scipy.optimize import linprog
    z=(2*np.asarray(y)-1)[:,None]*np.asarray(x)
    bounds=[(None,None)]*z.shape[1]
    result=linprog(np.zeros(z.shape[1]),A_ub=-z,b_ub=-np.ones(z.shape[0]),bounds=bounds,method="highs")
    if result.success:
        return "complete"
    if result.status != 2:
        raise AnalysisRefusal("separation feasibility solver failed")
    result=linprog(np.zeros(z.shape[1]),A_ub=np.vstack([-z,-z.sum(axis=0)]),
                   b_ub=np.r_[np.zeros(z.shape[0]),-1.0],bounds=bounds,method="highs")
    if result.success:
        return "quasi_complete"
    if result.status != 2:
        raise AnalysisRefusal("quasi-separation feasibility solver failed")
    return None


def synthetic_fixture(*,families: int=20,seed: int=20261123) -> dict[str,Any]:
    """Known logistic data-generating process; names never denote real models."""
    rng=random.Random(seed)
    models=[f"synthetic_model_{i}" for i in range(4)]
    prompts=["synthetic_prompt_0","synthetic_prompt_1"]
    roster=[]; rows=[]
    for f in range(families):
        family=f"synthetic_family_{f:03}"
        intercept=rng.gauss(0,0.65)
        slope=rng.gauss(0,0.30)
        for m,model in enumerate(models):
            for p,prompt in enumerate(prompts):
                for c,condition in enumerate(("C1","C2")):
                    pair_id=f"f{f}-m{m}-p{p}-c{c}"
                    roster.append(dict(pair_id=pair_id,model=model,family=family,prompt=prompt,
                                       precursor_condition=condition,pair_source_sha256=_sha([seed,pair_id])))
                    onset=rng.gauss(0,0.50)
                    for treatment in (0,1):
                        eta=0.6+0.15*m+0.10*p-0.10*c+intercept+onset+(-0.9+slope)*treatment
                        y=int(rng.random()<1/(1+math.exp(-eta)))
                        rows.append(dict(pair_id=pair_id,model=model,treatment=treatment,
                                         outcome=y,validity="VALID"))
    return {"schema_version":SCHEMA,"data_kind":"SYNTHETIC_CALIBRATION",
            "contrast":"C5","endpoint":"early_stop","models":models,"prompts":prompts,
            "pair_roster":roster,"rows":rows,
            "synthetic_truth":{"seed":seed,"family_intercept_sd":0.65,"family_treatment_slope_sd":0.30,
                               "onset_intercept_sd":0.50,"treatment_log_odds":-0.9,
                               "family_intercept_slope_covariance":0.0}}


def integrate_logistic(linear: Any,variance: Any,*,points: int=60) -> Any:
    """Marginalize a normal random effect using deterministic Gauss-Hermite nodes."""
    import numpy as np
    from scipy.special import expit
    linear=np.asarray(linear,dtype=float)
    variance=np.asarray(variance,dtype=float)
    if (linear.ndim!=2 or variance.shape!=(linear.shape[0],) or points<2
            or not np.all(np.isfinite(linear)) or not np.all(np.isfinite(variance))
            or np.any(variance<0)):
        raise AnalysisRefusal("invalid quadrature inputs")
    nodes,weights=np.polynomial.hermite.hermgauss(points)
    answer=np.zeros_like(linear)
    for node,weight in zip(nodes,weights/math.sqrt(math.pi)):
        answer+=weight*expit(linear+np.sqrt(2*variance)[:,None]*node)
    return answer


def fit_sensitivity(data: dict[str,Any],*,fe_prior_sd: float=2.0,log_sd_prior_sd: float=0.5,
                    posterior_draws: int=2000,seed: int=20261123,maxiter: int=1000,
                    allow_prospective: bool=False) -> dict[str,Any]:
    rows,audit=validate_input(data)
    if data["data_kind"] != "SYNTHETIC_CALIBRATION" and not allow_prospective:
        raise AnalysisRefusal("prospective fit requires explicit allow_prospective; no historical data are accepted")
    if not 0 < fe_prior_sd <= 10 or not 0 < log_sd_prior_sd <= 2:
        raise AnalysisRefusal("prior scale outside supported sensitivity range")
    if posterior_draws < 100 or maxiter < 1:
        raise AnalysisRefusal("at least100 posterior draws and positive maxiter required")
    import numpy as np
    import pandas as pd
    import patsy
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    frame=pd.DataFrame(rows)
    origins=sorted({p["precursor_condition"] for p in data["pair_roster"]})
    expected={(m,p,c) for m in data["models"] for p in data["prompts"] for c in origins}
    observed={(r["model"],r["prompt"],r["precursor_condition"]) for r in rows}
    if expected-observed:
        raise AnalysisRefusal("unsupported balanced standardization cell after pair missingness")
    formula="outcome ~ treatment * C(model) + treatment * C(prompt)"
    if frame.precursor_condition.nunique()>1:
        formula+=" + C(precursor_condition)"
    components={"family_intercept":"0 + C(family)",
                "family_treatment_slope":"0 + C(family):treatment",
                "onset_intercept":"0 + C(pair_cluster)"}
    model=BinomialBayesMixedGLM.from_formula(formula,components,frame,
                                            fe_p=fe_prior_sd,vcp_p=log_sd_prior_sd)
    rank=int(np.linalg.matrix_rank(model.exog))
    if rank != model.exog.shape[1]:
        raise AnalysisRefusal("fixed-effect design is rank deficient; no automatic term deletion")
    separation=separation_kind(model.exog,model.endog)
    if separation:
        raise AnalysisRefusal(f"fixed-effect {separation} separation; no prior-driven inferential result released")
    n=model.k_fep+model.k_vcp+model.k_vc
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        fit=model.fit_vb(mean=np.zeros(n),sd=np.full(n,0.5),fit_method="L-BFGS-B",
                        minim_opts={"maxiter":maxiter,"gtol":1e-7,"ftol":1e-13})
    opt=fit.optim_retvals
    if not opt.success or not all(np.all(np.isfinite(v)) for v in
                                  (fit.fe_mean,fit.fe_sd,fit.vcp_mean,fit.vcp_sd)):
        raise AnalysisRefusal(f"variational optimizer did not converge: {opt.message}")
    if float(np.max(np.abs(opt.jac)))>1e-3:
        raise AnalysisRefusal("variational optimizer residual gradient exceeds1e-3")
    # Mean-field posterior draws; no claim of a full covariance or MCMC sample.
    rng=np.random.default_rng(seed)
    beta=rng.normal(fit.fe_mean,fit.fe_sd,size=(posterior_draws,model.k_fep))
    log_sd=rng.normal(fit.vcp_mean,fit.vcp_sd,size=(posterior_draws,model.k_vcp))
    variance=np.exp(2*log_sd)
    if not np.all(np.isfinite(variance)):
        raise AnalysisRefusal("nonfinite posterior variance draw")
    component_index={name:i for i,name in enumerate(model.vcp_names)}
    marginal=[]
    quadrature_error=0.0
    for model_name in data["models"]:
        predictions=[]
        for treatment in (0,1):
            grid=pd.DataFrame([dict(model=model_name,prompt=p,precursor_condition=c,treatment=treatment)
                               for p in data["prompts"]
                               for c in origins])
            x=np.asarray(patsy.build_design_matrices([model.data.design_info],grid)[0])
            linear=beta@x.T
            v=(variance[:,component_index["family_intercept"]]
               +treatment*variance[:,component_index["family_treatment_slope"]]
               +variance[:,component_index["onset_intercept"]])
            probabilities=integrate_logistic(linear,v,points=60)
            check=integrate_logistic(linear,v,points=120)
            quadrature_error=max(quadrature_error,float(np.max(np.abs(probabilities-check))))
            if quadrature_error>1e-4:
                raise AnalysisRefusal("60/120-point quadrature disagreement exceeds1e-4")
            predictions.append(probabilities.mean(axis=1))
        difference=predictions[1]-predictions[0]
        marginal.append({"model":model_name,"control_probability":float(predictions[0].mean()),
                         "treatment_probability":float(predictions[1].mean()),
                         "marginal_risk_difference":float(difference.mean()),
                         "approximate_credible_low":float(np.quantile(difference,.025)),
                         "approximate_credible_high":float(np.quantile(difference,.975))})
    coefficients=[]
    for name,mean,sd in zip(model.fep_names,fit.fe_mean,fit.fe_sd):
        coefficients.append({"term":name,"posterior_mean_log_odds":float(mean),
                             "posterior_sd":float(sd),"approximate_credible_low":float(mean-1.95996398454*sd),
                             "approximate_credible_high":float(mean+1.95996398454*sd)})
    random_effects=[]
    for name,mean,sd in zip(model.vcp_names,fit.vcp_mean,fit.vcp_sd):
        random_effects.append({"component":name,"posterior_median_sd":float(np.exp(mean)),
                               "approximate_credible_low_sd":float(np.exp(mean-1.95996398454*sd)),
                               "approximate_credible_high_sd":float(np.exp(mean+1.95996398454*sd))})
    return {"version":VERSION,"status":"BAYESIAN_VARIATIONAL_SENSITIVITY_ONLY",
            "data_kind":data["data_kind"],"contrast":data["contrast"],"endpoint":data["endpoint"],
            "input_content_sha256":_sha(data),"analysis_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "confirmatory_eligibility":"NOT_ATTESTED","historical_pilot_fitted":False,
            "formula":formula,"variance_components":components,
            "random_covariance":"Independent family intercept and slope; covariance fixed to zero, not estimated.",
            "priors":{"fixed_effects_normal_mean":0,"fixed_effects_normal_sd":fe_prior_sd,
                      "log_random_sd_normal_mean":0,"log_random_sd_normal_sd":log_sd_prior_sd},
            "audit":audit,"fixed_effect_rank":rank,"fixed_effect_columns":model.exog.shape[1],
            "random_effect_columns":model.k_vc,"fixed_effect_separation":None,
            "optimizer":{"method":"L-BFGS-B","success":bool(opt.success),"message":str(opt.message),
                         "iterations":int(opt.nit),"objective":float(opt.fun),
                         "gradient_infinity_norm":float(np.max(np.abs(opt.jac)))},
            "warnings":[str(w.message) for w in captured],"coefficients":coefficients,
            "random_effect_standard_deviations":random_effects,"marginal_effects":marginal,
            "standardization":"Per-model balanced prompt/precursor grid; integrate independent Gaussian family/intercept/slope/onset effects with60-point Gauss-Hermite quadrature. Conditional-on-onset target, not all-task policy effect.",
            "quadrature_check":{"points":60,"comparison_points":120,
                                "max_absolute_probability_difference":quadrature_error,"tolerance":1e-4},
            "uncertainty":"95% mean-field variational posterior credible intervals; approximate and potentially too narrow, not frequentist CIs or Holm p-values.",
            "posterior_draws":posterior_draws,"posterior_seed":seed,
            "package_versions":{name:importlib.metadata.version(name) for name in
                                ("numpy","scipy","pandas","patsy","statsmodels")},
            "python_version":platform.python_version()}


def _csv(rows: list[dict[str,Any]]) -> str:
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()


def write_result(output: Path,result: dict[str,Any],fixture: dict[str,Any]|None=None) -> None:
    if output.exists(): raise FileExistsError("output directory exists; prior fit preserved")
    output.mkdir(parents=True,exist_ok=False)
    files={"fit.json":json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",
           "coefficients.csv":_csv(result["coefficients"]),
           "marginal_effects.csv":_csv(result["marginal_effects"]),
           "random_effects.csv":_csv(result["random_effect_standard_deviations"])}
    if fixture is not None:
        files["synthetic_fixture.json"]=json.dumps(fixture,indent=2,sort_keys=True)+"\n"
    for name,text in files.items():
        with (output/name).open("x",encoding="utf-8",newline="") as handle: handle.write(text)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("smoke","fit"))
    parser.add_argument("--input",type=Path)
    parser.add_argument("--output-directory",type=Path,required=True)
    parser.add_argument("--fe-prior-sd",type=float,default=2.0)
    parser.add_argument("--log-sd-prior-sd",type=float,default=0.5)
    parser.add_argument("--posterior-draws",type=int,default=2000)
    parser.add_argument("--allow-prospective",action="store_true")
    args=parser.parse_args()
    if args.output_directory.exists(): parser.error("output directory exists")
    if args.command=="fit" and args.input is None: parser.error("fit requires --input")
    data=synthetic_fixture() if args.command=="smoke" else json.loads(args.input.read_text())
    result=fit_sensitivity(data,fe_prior_sd=args.fe_prior_sd,log_sd_prior_sd=args.log_sd_prior_sd,
                          posterior_draws=args.posterior_draws,allow_prospective=args.allow_prospective)
    write_result(args.output_directory,result,data if args.command=="smoke" else None)
    print(json.dumps({"status":result["status"],"data_kind":result["data_kind"],
                      "complete_pairs":result["audit"]["complete_pairs"],
                      "optimizer_success":result["optimizer"]["success"],"output":str(args.output_directory)}))


if __name__=="__main__": main()
