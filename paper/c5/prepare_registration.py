"""Assemble a local OSF draft with exact inputs and per-model schedule hashes."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
ROSTER = "docs/c5_model_candidates.json"
SAP = "docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assemble(target, roster):
    records = {name: (ROOT / name).read_bytes() for name in (
        ROSTER, SAP, "experiments/PROSPECTIVE_FINITE.md", "docs/C5_MIXED_LOGISTIC_SENSITIVITY_20261123.md",
        "analysis/power_simulation.py",
        "analysis/c5_statistical_plan_20261123.py", "analysis/c5_statistical_plan_20261123/planning.json",
        "analysis/c5_19_family_planning_20261123.py", "analysis/c5_19_family_planning_20261123/planning.json",
        "analysis/c5_mixed_logistic_20261123.py", "analysis/c5_mixed_logistic_requirements_20261123.txt",
        "analysis/c5_prospective_endpoints.py", "analysis/c5_statistical_summary_20261123.py",
        "docs/PROSPECTIVE_ENDPOINT_READER.md",
    )}
    input_hashes = "".join(f"{digest(raw)}  {name}\n" for name, raw in sorted(records.items()))
    records["protocol.md"] = (
        b"# C5 local registration draft\n\n"
        b"Prepared for independent review. This packet has no registration timestamp. "
        b"The schedules contain candidates for hosted collection and confer no task admission. "
        b"Resolve the model routes, sampling population, human review and budget before finalizing.\n\n"
        + records[SAP] + b"\n\n" + records["experiments/PROSPECTIVE_FINITE.md"]
        + b"\n\n## Bound input files\n\n```text\n" + input_hashes.encode() + b"```\n"
    )
    summary = {"status": "LOCAL_DRAFT_NO_REGISTRATION_NO_COLLECTION", "roster": roster,
               "protocol_sha256": digest(records["protocol.md"]), "models": []}
    with TemporaryDirectory() as folder:
        for model in json.loads(records[ROSTER])["models"]:
            model_id = model["requested_id"]
            name = model_id.replace("/", "--") + ".json"
            output = Path(folder) / name
            command = [
                sys.executable, "-B", "-m", "experiments.prospective_finite", "plan",
                "--model", model_id, "--endpoint", "https://openrouter.ai/api/v1/chat/completions",
                "--repeats", "5", "--prompt-count", "3", "--temperature", "0.3",
                "--token-parameter", "max_tokens", "--output", str(output),
            ]
            if roster != "v7eight":
                command.extend(["--roster", roster])
            subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.PIPE)
            data = output.read_bytes()
            plan = json.loads(data)
            records["schedules/" + name] = data
            summary["models"].append({
                "model": model_id, "path": "schedules/" + name, "plan_sha256": digest(data),
                **{k: plan[k] for k in ("family_count", "planned_precursors", "maximum_hosted_calls")},
            })
    binding = [f"preregistration_sha256: {summary['protocol_sha256']}"]
    binding.extend("plan_sha256: " + model["plan_sha256"] for model in summary["models"])
    records["draft_osf_answer.txt"] = ("\n".join(binding) + "\n").encode()
    records["README.md"] = (
        b"# Local registration candidate\n\nThe exact protocol and each full schedule accompany the "
        b"response bindings. These bindings identify this candidate only. Regenerate after any change "
        b"to protocol, schedule or bound code, then register the final version before collection. "
        b"The candidate has no external registration ID, signature or collection authority.\n"
    )
    records["receipt.json"] = (json.dumps(summary, indent=2) + "\n").encode()
    records["SHA256SUMS.txt"] = "".join(f"{digest(raw)}  {name}\n"
        for name, raw in sorted(records.items())).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w") as archive:
        for name, raw in sorted(records.items()):
            entry = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, raw)
    with ZipFile(target) as archive:
        if archive.testzip() or any(archive.read(k) != v for k, v in records.items()):
            raise ValueError("Registration archive failed byte verification")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--roster", choices=("v7eight", "broad19"), required=True)
    arguments = parser.parse_args()
    print(json.dumps(assemble(arguments.output, arguments.roster), indent=2))
