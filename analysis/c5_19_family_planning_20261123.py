"""Additional19-family synthetic design grid; leaves the prior108 rows frozen."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from analysis.c5_statistical_plan_20261123 import budget,cluster_power,_csv


def generate() -> dict[str,str]:
    rows=[]
    for icc in (0.0,0.2):
        for effect in (0.0,-0.1,-0.2):
            settings=dict(families=19,pairs_per_family=30,delta=effect,discordance=0.3,
                          icc=icc,reach=0.5,loss=0.05,alpha=0.01)
            seed=int(hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:12],16)
            rows.append(cluster_power(**settings,replicates=2000,seed=seed))
    root=Path(__file__).resolve().parents[1]
    result={"version":"c5-19-family-planning-20261123-v1","status":"SYNTHETIC_PROSPECTIVE_PLANNING_ONLY",
            "eligible_for_main_analysis":False,"models":4,"families":19,"prompts":3,"repeats":5,
            "budget":budget(4,19,3),"cluster_power":rows,
            "source_sha256":{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                              ("analysis/c5_19_family_planning_20261123.py","analysis/c5_statistical_plan_20261123.py")},
            "limitations":["The19-family engineering roster still requires independent semantic admission.",
             "Power is model-based under stated paired-difference ICC, independent reach and loss assumptions.",
             "Alpha.01 is the first Holm threshold for four primary model tests at familywise alpha.04.",
             "This is conservative per-model benchmark power, not joint multi-model replication probability.",
             "No model run or human approval occurs in this script."]}
    return {"planning.json":json.dumps(result,indent=2,sort_keys=True)+"\n",
            "power.csv":_csv(rows),"budget.csv":_csv([result["budget"]])}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory",type=Path,required=True)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.output_directory.exists() and not args.check: parser.error("preserve existing output directory")
    outputs=generate()
    if args.check:
        for name,text in outputs.items():
            if (args.output_directory/name).read_text()!=text: raise ValueError(f"output differs:{name}")
        print("VERIFIED_19_FAMILY_SYNTHETIC_PLANNING")
    else:
        args.output_directory.mkdir(parents=True,exist_ok=False)
        for name,text in outputs.items():
            with (args.output_directory/name).open("x",encoding="utf-8",newline="") as handle:handle.write(text)
        print(args.output_directory)


if __name__=="__main__":main()
