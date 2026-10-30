"""Family-level sensitivity of the historical hidden-veto result.

Compute outcomes only from terminal receipts in the transformed review archive.
All archive members are hashed; no candidate source is executed or classified.
No prospective or population inference is made.
"""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from paper import independent_discordance_check as archive_reader


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = archive_reader.DEFAULT_ARCHIVE
REPORT = ROOT / "analysis/family_discordance_sensitivity_20261030.json"
FIGURE = ROOT / "analysis/figures/family_discordance_sensitivity_20261030.svg"
FAMILY_ORDER = ("key-derivation", "nonce", "weak-randomness", "sqli", "xss")


class FamilySensitivityError(ValueError):
    """The archived receipts do not support a complete family recount."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise FamilySensitivityError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recount_files(files: dict[str, bytes], archive_digest: str) -> dict:
    """Recount the balanced main cohort after checking transformed member hashes."""
    mapping, review = archive_reader._verify_review_manifest(files)
    manifest_name, index_name = archive_reader.MAIN_MANIFEST, archive_reader.MAIN_INDEX
    require(manifest_name in files and index_name in files, "main manifest or index missing")
    study = archive_reader._json_object(files[manifest_name], manifest_name)
    rows = archive_reader._jsonl_objects(files[index_name], index_name)
    require(study.get("experiment_id") == archive_reader.MAIN_ID and
            study.get("runs_per_task") == 1 and
            len(rows) == study.get("task_count") == 40 and
            len({r.get("run_id") for r in rows}) == 40 and
            len({r.get("slot_id") for r in rows}) == 40 and
            len(set(study.get("task_ids", []))) == 40 and
            len({r.get("task_id") for r in rows}) == 40 and
            set(study.get("task_ids", [])) == {r.get("task_id") for r in rows},
            "main inventory differs from the 40 scheduled episodes")
    families: dict[str, Counter[str]] = {}
    cells: Counter[tuple[str, str]] = Counter()
    for row in rows:
        require(row.get("experiment_id") == archive_reader.MAIN_ID,
                "another experiment appears in the main index")
        receipt_name = archive_reader._linked_path(row.get("receipt_path"), "experiments/runs/")
        log_name = archive_reader._linked_path(row.get("log_path"), "experiments/runs/")
        require(receipt_name in files and log_name in files and
                row.get("log_sha256") == mapping[log_name].get("original_sha256"),
                f"archive receipt/log link differs: {row.get('run_id')}")
        receipt = archive_reader._json_object(files[receipt_name], receipt_name)
        outcome = archive_reader._classify_terminal(row, receipt)
        family, condition = row.get("task_family"), row.get("condition")
        require(isinstance(family, str) and family and condition in {"RD", "RW", "UD", "UW"},
                "unknown family or condition")
        arm = condition[0]
        cells[(family, condition)] += 1
        count = families.setdefault(family, Counter())
        count[f"{arm}_episodes"] += 1
        count[f"{arm}_raw_pass"] += outcome["raw_pass"]
        count[f"{arm}_accepted"] += outcome["accepted"]
        count[f"{arm}_discordant"] += outcome["discordant"]
    require(set(families) == set(FAMILY_ORDER) and
            all(cells[(family, condition)] == 2 for family in families
                for condition in ("RD", "RW", "UD", "UW")),
            "five-family factorial cells are incomplete")
    by_family = []
    for family in FAMILY_ORDER:
        count = families[family]
        require(count["R_episodes"] == count["U_episodes"] == 4 and
                count["U_accepted"] == count["R_discordant"] == 0 and
                count["U_raw_pass"] == count["U_discordant"],
                f"test/gate accounting differs in {family}")
        by_family.append({
            "family": family,
            "u_episodes": count["U_episodes"],
            "u_raw_finite_passes": count["U_raw_pass"],
            "u_final_acceptances": count["U_accepted"],
            "u_hidden_veto_disagreements": count["U_discordant"],
            "r_episodes": count["R_episodes"],
            "r_raw_finite_passes": count["R_raw_pass"],
            "r_final_acceptances": count["R_accepted"],
        })
    n = sum(row["u_episodes"] for row in by_family)
    d = sum(row["u_hidden_veto_disagreements"] for row in by_family)
    require((n, d, sum(row["r_final_acceptances"] for row in by_family)) == (20, 9, 16),
            "terminal anchors differ from the historical paper")
    loo = [{"omitted_family": row["family"],
            "u_disagreements": d - row["u_hidden_veto_disagreements"],
            "u_episodes": n - row["u_episodes"],
            "exact_fraction": f"{d-row['u_hidden_veto_disagreements']}/{n-row['u_episodes']}"}
           for row in by_family]
    ranked = sorted(by_family, key=lambda row: (-row["u_hidden_veto_disagreements"], row["family"]))
    ratios = [Fraction(row["u_disagreements"], row["u_episodes"]) for row in loo]
    return {
        "status": "EXPLORATORY_FAMILY_DISCORDANCE_SENSITIVITY",
        "archive_sha256": archive_digest,
        "sanitization_manifest_sha256": sha(files[archive_reader.REVIEW_MANIFEST]),
        "main_index_sha256": sha(files[index_name]),
        "main_episodes": len(rows),
        "selected_family_count": len(by_family),
        "u_episodes": n,
        "u_hidden_veto_disagreements": d,
        "u_disagreement_fraction": f"{d}/{n}",
        "by_family": by_family,
        "leave_one_family_out": loo,
        "leave_one_family_out_min": loo[ratios.index(min(ratios))]["exact_fraction"],
        "leave_one_family_out_max": loo[ratios.index(max(ratios))]["exact_fraction"],
        "largest_two_families": {
            "families": [row["family"] for row in ranked[:2]],
            "disagreements": sum(row["u_hidden_veto_disagreements"] for row in ranked[:2]),
            "all_disagreements": d,
        },
        "transformed_members_hashed": review["mapping_count"] - 1,
        "source": "transformed review archive terminal receipts; no candidate source executed",
        "limitation": "Post-collection description of five purposively selected families with one run per cell. Guidance blocks were not fully time balanced; no population interval, p value, causal effect, or general security claim is supported.",
        "original_byte_provenance_verified_from_transformed_archive": False,
        "public_release_approved": False,
    }


def recount(path: Path = ARCHIVE) -> dict:
    data = Path(path).read_bytes()
    return recount_files(archive_reader._load_archive(Path(path)), sha(data))


def render_svg(report: dict) -> bytes:
    """Deterministic supplemental SVG of U-arm disagreements by family."""
    display_names = {
        "key-derivation": "Key derivation", "nonce": "Nonce handling",
        "weak-randomness": "Weak randomness", "sqli": "SQL injection",
        "xss": "Cross-site scripting",
    }
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="540" viewBox="0 0 920 540" role="img" aria-label="Historical U-arm hidden-veto disagreements by family">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="36" y="52" font-family="Arial,sans-serif" font-size="27" font-weight="700" fill="#172b40">Hidden-veto disagreement by family</text>',
        '<text x="36" y="80" font-family="Arial,sans-serif" font-size="16" fill="#526779">Historical U arm · four final candidates per selected family</text>',
    ]
    for i, row in enumerate(report["by_family"]):
        y, value = 130 + i * 70, row["u_hidden_veto_disagreements"]
        parts.extend([
            f'<text x="235" y="{y+22}" text-anchor="end" font-family="Arial,sans-serif" font-size="17" fill="#172b40">{escape(display_names[row["family"]])}</text>',
            f'<rect x="295" y="{y}" width="470" height="32" fill="#edf1f4"/>',
        ])
        if value:
            parts.append(f'<rect x="295" y="{y}" width="{470*value//4}" height="32" fill="#c56d38"/>')
        parts.append(f'<text x="782" y="{y+24}" font-family="Arial,sans-serif" font-size="19" font-weight="700" fill="#172b40">{value}/4</text>')
    parts.extend([
        '<text x="295" y="496" font-family="Arial,sans-serif" font-size="16" fill="#526779">Raw finite test PASS followed by hidden-gate FAIL</text>',
        '<text x="36" y="524" font-family="Arial,sans-serif" font-size="14" fill="#526779">Selected families; descriptive only. Finite test pass does not establish general security.</text>',
        '</svg>',
    ])
    return ('\n'.join(parts) + '\n').encode('utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ARCHIVE)
    parser.add_argument('--check', action='store_true', help='Compare against tracked JSON and SVG')
    args = parser.parse_args()
    try:
        report = recount(args.archive)
        data = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()
        figure = render_svg(report)
        if args.check:
            require(REPORT.read_bytes() == data, 'tracked family report differs')
            require(FIGURE.read_bytes() == figure, 'tracked family figure differs')
            status = 'VERIFIED_EXPLORATORY_FAMILY_SENSITIVITY'
        else:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            FIGURE.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_bytes(data)
            FIGURE.write_bytes(figure)
            status = 'BUILT_EXPLORATORY_FAMILY_SENSITIVITY'
        print(json.dumps({'status': status, 'u_disagreement_fraction': report['u_disagreement_fraction'],
                          'leave_one_family_out_range': [report['leave_one_family_out_min'],
                                                         report['leave_one_family_out_max']]}, sort_keys=True))
    except (OSError, KeyError, TypeError, ValueError, archive_reader.DiscordanceAuditError) as error:
        print(f'FAMILY_SENSITIVITY_FAILED: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
