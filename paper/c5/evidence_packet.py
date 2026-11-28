"""Build the portable, offline reviewer supplement for the feedback comparisons."""
import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
STUDIES = ("checker_timing_20261126", "pprint_postedit_20261127", "pprint_display_20261128",
           "reference_example_20261128", "cross_project_display_20261128")
FOLLOWUPS = {
    "feedback_factorial_20261128": (),
    "free_patch_20261128": ("sources.json", "upstream_check.json"),
    "production_patch_20261128": ("sources.json", "upstream_check.json", "component_scores.json", "components.md", "maintainer_examples.json", "order_types.json"),
    "replicate_display_20261128": ("permutation.json", "permutation_plan.json"),
    "output_provenance_20261128": (),
    "quix_contract_reversal_20261128": ("matched_pairs.json", "matched_pairs.md"),
    "quix_rule_omission_20261128": (),
    "selection_disclosure_20261128": (),
    "matplotlib_replication_20261128": (),
}
FOLLOWUP_FILES = (
    "analysis/matplotlib_axis_integration_20261128/replay.py",
    "analysis/matplotlib_axis_integration_20261128/results.json",
    "analysis/matplotlib_axis_integration_20261128/comparison.md",
    "analysis/selection_disclosure_report.py", "analysis/replicate_display_permutation.py", "docs/CPYTHON_DUPLICATE_PERMUTATION_20261128.md",
    "paper/c5/interval_figure.py", "paper/c5/figures/probe_reversal.png",
    "analysis/quix_contract_matched_pairs.py", "analysis/quix_rule_omission_report.py", "analysis/quix_upstream_tests.py", "analysis/quix_upstream_tests_20261128/cases.json",
    "analysis/quix_upstream_tests_20261128/design.md", "analysis/quix_upstream_tests_20261128/results.json",
    "analysis/quix_upstream_tests_20261128/comparison.md",
    "paper/c5/contract_figure.py", "paper/c5/figures/contract_reversal.png",
    "analysis/quix_syntax_controls.py", "analysis/free_patch_20261128/syntax_controls.json",
    "analysis/quix_expanded_domain.py", "docs/QUIX_EXPANDED_DOMAIN_20261128.md",
    "analysis/quix_expanded_domain_20261128/plan.json", "analysis/quix_expanded_domain_20261128/results.json",
    "analysis/quix_expanded_domain_20261128/comparison.md",
    "analysis/quix_contract_reversal_report.py", "analysis/feedback_resources.py",
    "analysis/feedback_resource_ledger_20261128/collection_status.json",
    "analysis/feedback_resource_ledger_20261128/results.json", "analysis/feedback_resource_ledger_20261128/comparison.md",
    "paper/c5/followup_results.py", "analysis/feedback_factorial_report.py", "analysis/free_patch_report.py",
    "analysis/production_patch_report.py", "analysis/production_patch_components.py", "analysis/production_patch_examples.py",
    "analysis/matplotlib_order_types.py", "docs/MATPLOTLIB_ORDER_TYPES_20261128.md",
    "analysis/replicate_display_report.py", "analysis/output_provenance_report.py",
    "analysis/swe_recheck.py", "docs/SWE_RECHECK_20261128.md", "docs/SWE_RECHECK_WRAPPER_SENSITIVITY_20261128.md",
    "external_audit_20261122/selection.json", "external_audit_20261122/episodes.csv",
    "analysis/historical_protocol_stop_recount_20261104.json",
)
CONTENTS = (
    "paper/c5/manuscript.md", "paper/c5/checker_feedback.pdf",
    "paper/c5/figures/feedback_example.png", "paper/c5/feedback_example.py",
    "paper/c5/figures/effort_panel.png", "paper/c5/figures/observed_horizon.png",
    "paper/c5/check_effort.py", "paper/c5/verify_feedback.py",
    "data/c5/check_release.py", "data/c5/event.schema.json", "data/c5/provenance.json",
    "data/c5/trajectories.jsonl", "data/c5/terminal_boolean_cases.json",
    "analysis/__init__.py", "analysis/c5_horizon_sensitivity_20261128.py", "analysis/c5_horizon_sensitivity_20261128/comparison.md",
    "analysis/c5_horizon_sensitivity_20261128/results.json", "analysis/checker_timing_pilot_20261126.py",
    "analysis/cross_project_display_report.py", "analysis/pprint_postedit_report.py", "analysis/pprint_display_report.py", "analysis/reference_example_report.py",
    "analysis/c5_effort_panel_20261124.json", "analysis/c5_codex_effort_20261124/results.json",
    "docs/c5_codex_catalog_20261124.json", "docs/CHECKER_TIMING_PILOT_20261126.md",
    "docs/CROSS_PROJECT_DISPLAY_20261128.md", "docs/PPRINT_POSTEDIT_20261127.md", "docs/PPRINT_DISPLAY_20261128.md",
    "docs/REFERENCE_EXAMPLE_CONTROL_20261128.md", "external_checker_audit_20261124/sources.json",
    "experiments/c5_cli_pilot.py", "experiments/c5_codex_effort.py", "experiments/c5_evidence_challenge.py",
    "experiments/checker_timing_dateutil.py", "experiments/checker_timing_pprint.py",
    "experiments/checker_timing_pilot.py", "experiments/pprint_postedit_fork.py",
    "experiments/pprint_postedit_probes.py", "experiments/pprint_display_fork.py",
    "experiments/reference_example_control.py", "experiments/cross_project_display.py",
)
README = """# Checking the code-repair experiments

Open paper/c5/checker_feedback.pdf for the identified article. From the extracted directory, run:

    python3 -B -m paper.c5.verify_feedback

Python 3.10 or later and the standard library suffice. The verifier checks every listed file digest, all seven main tables, the nine-study roster, historical transitions, returned expressions, functional outcomes and resource counters. The following commands isolate individual findings.

| Question | Offline command |
| --- | --- |
| Does the selected program follow both opposing QuixBugs requirements? | python3 -B -m analysis.quix_contract_reversal_report --check |
| What do the maintainers' original QuixBugs tests report? | python3 -B -m analysis.quix_upstream_tests |
| Which source choices still pass on disjoint expanded inputs? | python3 -B -m analysis.quix_expanded_domain check |
| What happens if the names and definitions of both contracts are omitted? | python3 -B -m analysis.quix_rule_omission_report --check |
| Does changing the caption on an identical value alter choices? | python3 -B -m analysis.output_provenance_report --check |
| What does naming the required convention add? | python3 -B -m analysis.feedback_factorial_report --check |
| Which edits passed the Matplotlib and tqdm maintenance checks? | python3 -B -m analysis.production_patch_report --check |
| Which interval results hold for all scalar endpoint orderings? | python3 -B -m analysis.matplotlib_order_types |
| Which Matplotlib outcomes recur on identical prompts? | python3 -B -m analysis.matplotlib_replication_report --check |
| What happened when these edits ran inside Matplotlib on a real axis? | python3 -B -m analysis.matplotlib_axis_integration_20261128.replay --check |
| How much do CPython replies differ within and between prompts? | python3 -B -m analysis.replicate_display_report --check |
| What exact command repeats appear in the SWE-bench records? | python3 -B -m analysis.swe_recheck --recount |

Add --allow-cd to the SWE-bench command for the documented directory-prefix sensitivity check. Use --fetch instead of --recount to obtain and verify the original public trace bytes over the network. The default packet works offline with the public per-command records. The maintenance study and the SWE-bench trace use different Matplotlib issues. The verification command also checks the 38 controller labels and their 13 explicit requests against the 40 historical episode records, and the stop classes of the 20 public SWE-bench slots.

Each native assignment stays in its original roster. Some identical prompts have one response graded against two possible target contracts. The CPython checkpoints repeat a single sorting defect. The archive preserves the earlier dateutil and CPython timing pilots and contains separate calibration records, target conventions, edited expressions, exclusions and unstarted slots. Each results file binds the corresponding local plan digest. Raw private session streams remain local. Public grades can be reconstructed, while native token extraction and provider identity require other evidence.

Independent human review and the prospective verdict-by-budget experiment remain pending.
"""

def build(path, anonymous=False):
    names = list(CONTENTS)
    for study in STUDIES:
        names.extend(f"analysis/{study}/{part}" for part in ("plan.json", "calibration.json", "results.json", "comparison.md"))
    names.extend(FOLLOWUP_FILES)
    names.extend("analysis/swe_recheck_20261128/" + name for name in
                 ("sources.json","results.json","comparison.md","wrapper_results.json","wrapper_comparison.md","matplotlib_case.md"))
    for study, extras in FOLLOWUPS.items():
        directory = Path("analysis") / study
        parts = ["plan.json", "results.json", "comparison.md", *extras]
        if study not in {"replicate_display_20261128", "quix_rule_omission_20261128", "matplotlib_replication_20261128"}:
            parts.append("calibration.json")
        names.extend(str(directory / part) for part in parts)
        plan = json.loads((ROOT / directory / "plan.json").read_bytes())
        key = "workflow_sha256" if study == "matplotlib_replication_20261128" else "source_sha256"
        for source in plan[key]:
            dependency = Path(source)
            if dependency.is_absolute() or ".." in dependency.parts or dependency.parts[0] not in {"analysis","experiments","docs","external_checker_audit_20261124"}:
                raise ValueError(f"Unexpected frozen source path {source}")
            names.append(source)
    contents = {name: (ROOT / name).read_bytes() for name in sorted(set(names))}
    instructions = README
    if anonymous:
        from pypdf import PdfReader
        from paper.build_submission import review_manuscript
        author_id = re.compile(rb"Imranqsl212|Zakirov|Iosifova|Kramich", re.IGNORECASE)
        source = "paper/c5/manuscript.md"
        contents[source] = review_manuscript(contents[source].decode()).encode()
        pdf = ROOT / "paper/c5/checker_feedback_anonymous.pdf"
        reader = PdfReader(str(pdf))
        pdf_strings = [str(reader.metadata)]
        for page in reader.pages:
            pdf_strings.append(page.extract_text() or "")
            pdf_strings.extend(str(a.get_object().get("/A", {})) for a in page.get("/Annots", []))
        visible = "\n".join(pdf_strings).encode()
        for name, raw in contents.items():
            if name.endswith((".pdf", ".png")):
                continue
            if author_id.search(name.encode()) or author_id.search(raw):
                raise ValueError(f"Author identifier in blinded packet file {name}")
        if author_id.search(visible):
            raise ValueError("Author identifier in blinded PDF")
        contents["paper/c5/checker_feedback.pdf"] = pdf.read_bytes()
        instructions = instructions.replace("identified article", "author-blinded article")
    contents["README.md"] = instructions.encode()
    contents["SHA256SUMS"] = "".join(f"{sha256(b).hexdigest()}  {name}\n" for name, b in sorted(contents.items())).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as scratch:
        candidate = Path(scratch) / path.name
        with ZipFile(candidate, "w") as archive:
            for name, value in sorted(contents.items()):
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, value)
        with ZipFile(candidate) as archive:
            if archive.testzip() or set(archive.namelist()) != set(contents):
                raise ValueError("Invalid evidence packet")
        candidate.replace(path)
    print(path, len(contents), "files")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anonymous", action="store_true", help="Use the blinded PDF and matching Markdown")
    args = parser.parse_args()
    build(args.output, args.anonymous)
