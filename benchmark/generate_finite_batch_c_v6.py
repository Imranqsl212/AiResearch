from __future__ import annotations
import hashlib, json
from pathlib import Path
from benchmark.finite_batch_c_v6 import build_reference_tasks, certify_task

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark/tasks/v6_batch_c"
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True, exist_ok=True); rows=[]
    for task in build_reference_tasks():
        tp=OUT/f"{task['task_id']}.task.json"; pp=OUT/f"{task['task_id']}.proof.json"
        tp.write_text(json.dumps(task, indent=2, sort_keys=True)+"\n")
        pp.write_text(json.dumps(certify_task(task), indent=2, sort_keys=True)+"\n")
        rows.append({"task_id":task["task_id"],"family":task["family"],"condition":task["condition"],"ground_truth_state":certify_task(task)["ground_truth_state"],"task_file":tp.name,"task_file_sha256":digest(tp),"proof_file":pp.name,"proof_file_sha256":digest(pp)})
    index={"schema_version":"6.0","family_count":8,"condition_count":40,"scope":"bounded_finite_candidate_languages_only","tasks":rows}
    (OUT/"index.json").write_text(json.dumps(index, indent=2, sort_keys=True)+"\n")
if __name__ == "__main__": main()
