"""Synthetic checks for the private, blank privacy-review register."""

from __future__ import annotations

import copy
import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path

from paper import build_private_privacy_register as register
from paper import build_sanitized_privacy_packet as packet


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _packet() -> dict:
    a = b"/usr/bin/tool\npassword=example\n"
    b = b"/usr/bin/tool\npassword=another\n"
    files = {"a.txt": a, "b.txt": b}
    paths = packet._residual_paths(files)
    lexical = [row for row in packet._rule_hits(files) if row["kind"] == "credential_label"]
    return {
        "schema": packet.SCHEMA,
        "status": "PRIVATE_HUMAN_PRIVACY_INSPECTION_REQUIRED",
        "public_release_approved": False,
        "human_privacy_review_complete": False,
        "sanitized_archive_sha256": _sha(b"synthetic sanitized archive"),
        "residual_path_candidates": paths,
        "residual_path_count": len(paths),
        "scanner_candidates": lexical,
        "scanner_rule_counts": {"credential_label": len(lexical)},
    }


class PrivatePrivacyRegisterTests(unittest.TestCase):
    def test_all_leads_preserved_and_duplicates_grouped_without_snippets(self) -> None:
        source = _packet()
        result = register.make_register(source, _sha(b"packet"),
                                        expected_counts={"lexical": 2, "residual_path": 2})
        self.assertEqual(result["counts"], {"lexical": 2, "residual_path": 2,
                                             "total": 4, "distinct_match_hash_groups": 2})
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(sorted(group["lead_count"] for group in result["groups"]), [2, 2])
        self.assertEqual({row["row_id"] for row in result["rows"]},
                         {"P0001", "P0002", "L0001", "L0002"})
        text = json.dumps(result)
        self.assertNotIn("/usr/bin/tool", text)
        self.assertNotIn("password=", text)
        self.assertTrue(all(row["reviewer_disposition"] is None for row in result["rows"]))
        self.assertFalse(result["public_release_approved"])

    def test_tampered_location_and_self_approval_rejected(self) -> None:
        original = register.make_register(_packet(), _sha(b"packet"),
                                          expected_counts={"lexical": 2, "residual_path": 2})
        tampered = copy.deepcopy(original)
        tampered["rows"][0]["byte_offset"] += 1
        with self.assertRaisesRegex(ValueError, "location/hash differs"):
            register.validate(tampered, original)
        tampered = copy.deepcopy(original)
        tampered["public_release_approved"] = True
        with self.assertRaisesRegex(ValueError, "public_release_approved=false"):
            register.validate(tampered, original)
        tampered = copy.deepcopy(original)
        tampered["rows"][0]["reviewer_disposition"] = "requires_redaction"
        with self.assertRaisesRegex(ValueError, "lacks identity"):
            register.validate(tampered, original)

    def test_private_write_once_and_verify_reviewed_copy(self) -> None:
        source = _packet()
        source_bytes = register._canonical(source)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = root / "PRIVATE_INSPECTION_REPORT.json"
            receipt_path = root / "inspection.receipt.json"
            output = root / "register"
            report_path.write_bytes(source_bytes)
            receipt_path.write_bytes(register._canonical({
                "private_report_sha256": _sha(source_bytes),
                "sanitized_archive_sha256": source["sanitized_archive_sha256"],
            }))
            kwargs = {"source": report_path, "receipt": receipt_path,
                      "output": output, "expected_sha256": _sha(source_bytes),
                      "expected_counts": {"lexical": 2, "residual_path": 2}}
            first = register.build(**kwargs)
            self.assertEqual(first, register.build(**kwargs))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            for filename in (register.REGISTER_NAME, register.RECEIPT_NAME):
                self.assertEqual(stat.S_IMODE((output / filename).stat().st_mode), 0o600)
            saved = json.loads((output / register.REGISTER_NAME).read_bytes())
            self.assertEqual(register.validate(saved, saved)["lead_count"], 4)
            saved["rows"][0].update({
                "reviewer_disposition": "requires_redaction",
                "reviewer_identity": "Human reviewer",
                "reviewed_at": "2026-10-08",
                "reviewer_rationale": "synthetic test reason",
            })
            edited = root / "edited.json"
            edited.write_bytes(register._canonical(saved))
            verified = register.verify(source=report_path, receipt=receipt_path,
                                       register_path=edited, expected_sha256=_sha(source_bytes),
                                       expected_counts={"lexical": 2, "residual_path": 2})
            self.assertEqual(verified["reviewer_dispositions_recorded"], 1)
            self.assertFalse(verified["public_release_approved"])
            with self.assertRaises(FileExistsError):
                register.build(**{**kwargs, "output": edited})


if __name__ == "__main__":
    unittest.main()
