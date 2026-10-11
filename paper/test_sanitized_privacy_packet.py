"""Synthetic checks for a private, bounded privacy inspection packet."""

from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper import build_sanitized_privacy_packet as packet


class SanitizedPrivacyPacketTests(unittest.TestCase):
    def test_residual_paths_exclude_research_root_placeholder(self) -> None:
        member = "synthetic.txt"
        data = b"<RESEARCH_ROOT>/example/fixture\n/usr/bin/tool\n"
        hits = packet._residual_paths({member: data})
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["match"], "/usr/bin/tool")
        self.assertEqual((hits[0]["member"], hits[0]["line"]), (member, 2))

    def test_sensitive_scan_and_private_write_once_packet(self) -> None:
        content = (b"/usr/bin/tool\n" * 8 +
                   b"person@example.test hostname=fixture password=example 192.0.2.1\n")
        files = {"synthetic.txt": content,
                 packet.sanitized.MANIFEST_NAME: b"{}\n"}
        hits = packet._rule_hits(files)
        counts = {kind: sum(row["kind"] == kind for row in hits)
                  for kind in ("email_address", "host_identifier_label",
                               "credential_label", "ipv4_address")}
        self.assertEqual(counts, {"email_address": 1, "host_identifier_label": 1,
                                  "credential_label": 1, "ipv4_address": 1})
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "candidate.tar.gz"
            archive.write_bytes(b"synthetic archive stub")
            output = base / "private"
            with patch.object(packet, "_verified_review_members", return_value=(files, {}, 0)):
                first = packet.build(archive=archive, output=output)
                second = packet.build(archive=archive, output=output)
            self.assertEqual(first, second)
            report = json.loads((output / packet.REPORT_NAME).read_bytes())
            self.assertEqual(report["residual_path_count"], 8)
            self.assertFalse(report["public_release_approved"])
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((output / packet.REPORT_NAME).stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((output / packet.RECEIPT_NAME).stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
