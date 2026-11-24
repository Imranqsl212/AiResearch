"""Package the four candidate decision-budget schedules and their analysis protocol."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from experiments import c5_budget_runner as runner
from experiments.main_collector import _canonical
from paper.c5.prepare_registration import ROOT, ROSTER, digest

PROTOCOL = "docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md"
DESIGN = "analysis/c5_budget_design_20261124"
INPUTS = (
    PROTOCOL, "experiments/c5_budget_README.md", ROSTER,
    "analysis/c5_budget_statistics.py", "analysis/c5_budget_power_20261124.py",
    "analysis/c5_statistical_plan_20261123.py", "analysis/power_simulation.py",
    f"{DESIGN}/planning.json", f"{DESIGN}/power.csv", f"{DESIGN}/budget.json",
)


def assemble(destination):
    records = {name: (ROOT / name).read_bytes() for name in INPUTS}
    budget = json.loads(records[f"{DESIGN}/budget.json"])
    identifiers = [model["requested_id"] for model in json.loads(records[ROSTER])["models"]]
    if len(identifiers) != budget["models"] or len(identifiers) != len(set(identifiers)):
        raise ValueError("Candidate models and planning simulation disagree")
    schedules = []
    for model in identifiers:
        plan = runner.build_plan(model=model, endpoint="https://openrouter.ai/api/v1/chat/completions",
                                 seed=20261124, roster="broad19", repeats=5, prompt_count=3,
                                 temperature=0.3, token_parameter="max_tokens")
        runner.verify_plan(plan)
        for name, expected in plan["source_file_sha256s"].items():
            if name not in records:
                records[name] = (ROOT / name).read_bytes()
            if digest(records[name]) != expected:
                raise ValueError(f"Scheduled source differs: {name}")
        name = f"schedules/{model.replace('/', '--')}.json"
        raw = _canonical(plan) + b"\n"
        records[name] = raw
        schedules.append({"model": model, "path": name, "plan_sha256": digest(raw),
                          **{k: plan[k] for k in ("family_count", "planned_precursors", "maximum_hosted_calls")}})
    if (sum(x["planned_precursors"] for x in schedules) != budget["precursors"]
            or sum(x["maximum_hosted_calls"] for x in schedules) != budget["total_decisions_max"]):
        raise ValueError("Runtime and statistical call budgets disagree")
    files = "".join(f"{digest(raw)}  {name}\n" for name, raw in sorted(records.items()))
    records["protocol.md"] = (records[PROTOCOL] + b"\n\n## Frozen candidate inputs\n\n"
                              + b"The two auxiliary studies and the November 23 stopping plan are separate. "
                              + b"The archived model catalogue's price example is for the older design. "
                              + b"Provider routes and a spending limit require a later decision.\n\n```text\n"
                              + files.encode() + b"```\n")
    protocol_hash = digest(records["protocol.md"])
    binding = [f"preregistration_sha256: {protocol_hash}"]
    binding.extend("plan_sha256: " + item["plan_sha256"] for item in schedules)
    records["draft_osf_answer.txt"] = ("\n".join(binding) + "\n").encode()
    receipt = {"status": "LOCAL_DRAFT_NO_REGISTRATION_NO_MODEL_CALLS",
               "protocol_sha256": protocol_hash, "models": schedules,
               "precursor_slots": budget["precursors"], "upper_bound_model_decisions": budget["total_decisions_max"]}
    records["receipt.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    records["SHA256SUMS.txt"] = "".join(f"{digest(raw)}  {name}\n"
                                        for name, raw in sorted(records.items())).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as folder:
        candidate = Path(folder) / "packet.zip"
        with ZipFile(candidate, "w") as archive:
            for name, raw in sorted(records.items()):
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, raw)
        with ZipFile(candidate) as archive:
            if archive.testzip() or any(archive.read(name) != raw for name, raw in records.items()):
                raise ValueError("Budget study packet failed byte verification")
        if destination.exists():
            if candidate.read_bytes() != destination.read_bytes():
                raise FileExistsError(f"Choose a fresh output path: {destination}")
        else:
            destination.hardlink_to(candidate)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(assemble(parser.parse_args().output), indent=2))
