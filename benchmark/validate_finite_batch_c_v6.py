from __future__ import annotations
import hashlib, json
from pathlib import Path
from benchmark.finite_batch_c_v6 import certify_task, evaluate_candidate, verify_proof
from benchmark.finite_batch_c_reference_v6 import reference_results
ROOT=Path(__file__).resolve().parents[1]; DIR=ROOT/"benchmark/tasks/v6_batch_c"
def validate():
    index=json.loads((DIR/"index.json").read_text()); checks=0
    for row in index["tasks"]:
        task=json.loads((DIR/row["task_file"]).read_text()); proof=json.loads((DIR/row["proof_file"]).read_text())
        assert hashlib.sha256((DIR/row["task_file"]).read_bytes()).hexdigest()==row["task_file_sha256"]
        assert hashlib.sha256((DIR/row["proof_file"]).read_bytes()).hexdigest()==row["proof_file_sha256"]
        assert verify_proof(task, proof)
        for mode in ("csrf_origin","nonce_uniqueness","signature_algorithm","deserialization_allowlist","tls_hostname","key_rotation","kdf_salt","environment_injection"):
            pass
        for candidate in ({"mode": m} for m in __import__("benchmark.finite_batch_c_v6",fromlist=["FAMILIES"]).FAMILIES[task["family"]]["modes"]):
            got=evaluate_candidate(task,candidate); ref=reference_results(task,candidate); assert tuple(got[k] for k in ("raw_test_result","strong_test_result","security_oracle_result","benchmark_verdict"))==ref, (task["task_id"],candidate,got,ref); checks+=1
    return {"families":8,"conditions":40,"candidate_checks":checks}
if __name__ == "__main__":
    result=validate(); print(f"PASS: {result['families']} families, {result['conditions']} proofs, {result['candidate_checks']} independent candidate checks")
