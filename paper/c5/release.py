"""Build inspectable data-deposit and blind-review candidates without uploading them."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
from pypdf import PdfReader
from data.c5.check_release import verify
from paper.c5.check_cli_table import verify as verify_cli, FILENAME as CLI_FILENAME
from paper.c5.check_effort import verify as verify_effort

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/c5"
SENSITIVE = re.compile(rb"(?:/Users/|/home/[^/\s]+/|/var/folders/|PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})")
IDENTITY = re.compile(rb"imranqsl212|AiResearch|zakirov|iosifova|kramich", re.I)


def payload(blind):
    verify(DATA)
    cli_path = ROOT / "analysis" / CLI_FILENAME
    verify_cli(cli_path)
    common = ["trajectories.jsonl", "event.schema.json", "check_release.py", "provenance.json",
              "terminal_boolean_cases.json"]
    result = {name:(DATA/name).read_bytes() for name in common}
    result[CLI_FILENAME] = cli_path.read_bytes()
    result["check_cli_table.py"] = (ROOT / "paper/c5/check_cli_table.py").read_bytes()
    result["c5_cli_repair_timing_20261124.json"] = (ROOT / "analysis/c5_cli_repair_timing_20261124.json").read_bytes()
    for name, relative in (
        ("codex_effort_sequential.json", "analysis/c5_codex_effort_20261124/results.json"),
        ("codex_effort_panel.json", "analysis/c5_effort_panel_20261124.json"),
        ("codex_effort_panel_reference.json", "analysis/c5_effort_panel_reference_20261124.json"),
        ("codex_effort_format_audit.json", "analysis/c5_effort_format_audit_20261124.json"),
        ("codex_effort_design.md", "docs/C5_CODEX_EFFORT_DESIGN_20261124.md"),
        ("c5_codex_catalog_20261124.json", "docs/c5_codex_catalog_20261124.json"),
    ):
        result[name] = (ROOT / relative).read_bytes()
    verify_effort(ROOT/"analysis/c5_effort_panel_20261124.json", ROOT/"analysis/c5_codex_effort_20261124/results.json",
                  ROOT/"docs/c5_codex_catalog_20261124.json")
    result["check_effort.py"] = (ROOT/"paper/c5/check_effort.py").read_bytes()
    result["codex_effort_design.md"] = result["codex_effort_design.md"].replace(
        b"(C5_CLI_PILOT_20261124.md)", b"(" + CLI_FILENAME.encode() + b")")
    if blind:
        manifest = json.loads(result["provenance.json"])
        result["provenance.json"] = (json.dumps({k:manifest[k] for k in
            ("schema_version","jsonl_sha256","schema_sha256","terminal_cases_sha256","pairs","arms","events","submissions")}, indent=2) + "\n").encode()
        pdf = ROOT / "paper/c5/checker_feedback_anonymous.pdf"
        reader = PdfReader(str(pdf))
        visible = (str(reader.metadata) + "\n".join(p.extract_text() or "" for p in reader.pages)).encode()
        assert not IDENTITY.search(visible) and not SENSITIVE.search(visible)
        result["manuscript.pdf"] = pdf.read_bytes()
        result["README.md"] = (b"# Review copy\n\nThe PDF reports an exploratory paired study. "
            b"Run `python3 check_release.py` in this directory to reproduce Table S4 and the branch counts in Figure S2 from 78 decisions. "
            b"The figure's failing-candidate counts (truthful PASS / false FAIL) at decisions 1, 2 and 3 are 4/1, 8/6 and 5/7. "
            b"Only a candidate submission updates the retained state; inspection, stopping and later prefixes after completion preserve it. "
            b"These are prefixes of the same three-decision workflow, not separately assigned budget interventions. "
            b"Rows are observed decisions in selected historical pairs. Candidate and source text were omitted.\n")
    else:
        for name in ("README.md", "external_controls.json"):
            result[name] = (DATA / name).read_bytes()
        result["README.md"] = result["README.md"].replace(b"(../../analysis/c5_feedback_action_20261104.json)",
            b"(https://github.com/Imranqsl212/AiResearch/blob/3b5679d5b2df0d231a981fdd1419eb37fb0df721/analysis/c5_feedback_action_20261104.json)")
        result["README.md"] = b"---\npretty_name: C5 paired continuation decisions\nconfigs:\n- config_name: default\n  data_files:\n  - split: observation\n    path: trajectories.jsonl\n---\n\n" + result["README.md"]
        result["README.md"] += (b"\nFor a standalone check, run `python3 check_release.py` next to the JSONL. "
            b"It independently reproduces Table S4 and the failing-candidate counts plotted in Figure S2 "
            b"(truthful PASS / false FAIL): 4/1, 8/6 and 5/7 at decisions 1, 2 and 3. "
            b"Only submissions change retained candidate state; an early completed branch keeps its terminal state at later prefixes. "
            b"These prefixes do not estimate separately announced budget interventions. "
            b"The module commands above use the source repository.\n")
        result["CITATION.cff"] = (ROOT/"CITATION.cff").read_bytes()
    result["README.md"] += (b"\n## Separate CLI pilot table\n\n"
        b"Run `python3 check_cli_table.py` in this directory to recount `c5_cli_pilot_20261124.json` "
        b"by requested CLI alias, checker and initial correct/defective state. "
        b"The checker retains all five requested aliases and forty reserved episodes, verifies reported counters, "
        b"and leaves unstarted or incomplete outcomes missing. A model without completed episodes has no measured correctness rate. "
        b"Logged action totals are separate from behavioral outcomes. No expected model performance is built into the check. "
        b"This checks public-table consistency only: raw prompts, CLI responses and private candidate-evaluation receipts are not included, "
        b"so it does not independently authenticate providers or replay the private oracle. "
        b"The authored benign lookup task is an excluded descriptive pilot, separate from the historical continuations and prospective budget experiment. "
        b"The separate `c5_cli_repair_timing_20261124.json` records the post hoc correctness-by-step audit. "
        b"The public action-table checker does not reconstruct candidate correctness or verify that separate timing audit from private responses.\n")
    result["README.md"] += (
        b"\nThe follow-up Codex effort comparison has two separate records. "
        b"`codex_effort_sequential.json` contains the action and usage ledger for the low/high repair episodes. "
        b"`codex_effort_panel.json` contains the six-task assessments and resource use by model and effort. "
        b"`codex_effort_panel_reference.json` checks the twenty finite input answers with separate algorithms. "
        b"`codex_effort_format_audit.json` describes a post-hoc alternative reading of malformed replies. "
        b"See [the design](codex_effort_design.md) for the selection rule and denominators.\n")
    result["README.md"] += (
        b"\nRun `python3 -I check_effort.py` here to reconstruct the paired effort comparisons from the "
        b"[panel task assessments](codex_effort_panel.json) and [episode action ledger](codex_effort_sequential.json). "
        b"The command checks the available correctness denominators, dispatch and action counts, paired terminal "
        b"outcomes, usage and duration. Unavailable measures remain missing.\n")
    for name, item in result.items():
        if name.endswith(".pdf"):
            continue
        if SENSITIVE.search(item) or (blind and IDENTITY.search(item)):
            raise ValueError(f"Unexpected marker in {name}")
    return result


def build(path, blind):
    records = payload(blind)
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {k}\n" for k,b in sorted(records.items()))
    records["SHA256SUMS.txt"] = sums.encode()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
        for name, value in sorted(records.items()):
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, value)
    with ZipFile(path) as z:
        assert z.testzip() is None and set(z.namelist()) == set(records)
        assert all(z.read(name) == data for name, data in records.items())
    print(path, len(records), "files")


def review_repository(archive, target):
    """Start a clean local repository with exactly the anonymous archive's files."""
    target.mkdir(parents=True, exist_ok=False)
    with ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if name != Path(name).name or name.startswith("."):
                raise ValueError(f"Unexpected review package path {name}")
            (target / name).write_bytes(bundle.read(name))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    for role in ("AUTHOR", "COMMITTER"):
        env.update({f"GIT_{role}_NAME": "Anonymous review", f"GIT_{role}_EMAIL": "review@example.invalid",
                    f"GIT_{role}_DATE": "2000-01-01T00:00:00+0000"})
    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgSign=false", "-c", "core.hooksPath=/dev/null", *args],
            cwd=target, env=env, text=True).strip()
    git("init", "--quiet", "--initial-branch=main", "--template=")
    git("add", "--", ".")
    git("commit", "--quiet", "-m", "Add anonymous manuscript and reproducible decision table")
    if git("remote") or git("rev-list", "--count", "HEAD") != "1":
        raise ValueError("Review repository has unexpected remotes or history")
    with ZipFile(archive) as bundle:
        if set(git("ls-files").splitlines()) != set(bundle.namelist()):
            raise ValueError("Review repository and review archive differ")
    verify(target)
    verify_cli(target)
    verify_effort(target/"codex_effort_panel.json", target/"codex_effort_sequential.json",
                  target/"c5_codex_catalog_20261124.json")
    print("Anonymous review repository:", target, git("rev-parse", "--short", "HEAD"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, help="create a new local anonymous Git repository")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    build(out / "c5-data.zip", False)
    build(out / "anonymous-review.zip", True)
    if args.mirror:
        review_repository(out / "anonymous-review.zip", args.mirror)
