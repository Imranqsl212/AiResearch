"""Offline integrity checks for the private excluded-pilot bundle format."""

from __future__ import annotations

import gzip
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from analysis.build_private_excluded_pilot_bundle import (
    INVENTORY_NAME,
    _inventory,
    _load_archive,
    _write_archive,
)


class PrivateExcludedPilotBundleTests(unittest.TestCase):
    def test_archive_bytes_are_deterministic_and_inventory_checks_payload(self) -> None:
        payload = {"raw/experiments/runs/example/a.json": b"{\"x\":1}\n",
                   "support/analysis/replay.py": b"print('ok')\n"}
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first, second, damaged = (base / name for name in
                                      ("first.tar.gz", "second.tar.gz", "damaged.tar.gz"))
            _write_archive(first, payload)
            _write_archive(second, payload)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            members, _, _ = _load_archive(first)
            self.assertEqual(members, payload)

            with damaged.open("xb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                    with tarfile.open(fileobj=compressed, mode="w|",
                                      format=tarfile.PAX_FORMAT) as archive:
                        for name, data in [(INVENTORY_NAME, _inventory(payload)),
                                           ("raw/experiments/runs/example/a.json", b"changed"),
                                           ("support/analysis/replay.py", payload["support/analysis/replay.py"])]:
                            header = tarfile.TarInfo(name)
                            header.size = len(data)
                            header.mtime = header.uid = header.gid = 0
                            header.uname = header.gname = ""
                            header.mode = 0o600
                            archive.addfile(header, io.BytesIO(data))
            with self.assertRaisesRegex(ValueError, "inventory hash or size mismatch"):
                _load_archive(damaged)


if __name__ == "__main__":
    unittest.main()
