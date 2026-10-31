"""A moved checkout must validate archived requests against its local schedule."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from analysis.v1_pipeline import (
    V1ValidationError, canonical_bytes, load_episode, recorded_checkout_root,
    sha256_bytes,
)
from experiments.run_c5_remaining_onset_feasibility import PILOT, ROOT


class V1RequestArchiveRelocationTests(unittest.TestCase):
    def test_historical_absolute_schedule_is_relocated_and_hashed(self) -> None:
        relative_manifest = (
            PILOT / "slot-000006/live-000006.manifest.json"
        ).relative_to(ROOT)
        original = json.loads((ROOT / relative_manifest).read_text(encoding="utf-8"))
        relative_prompt = relative_manifest.with_name("live-000006.prompt.json")
        old_root = recorded_checkout_root(
            original["prompt_path"], relative_prompt, name="pilot prompt",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source_root = temporary / "relocated"
            fictional_old_root = temporary / "historical-not-present"
            manifest = deepcopy(original)
            stems = ("task", "prompt", "schedule", "oracle_proof", "log")
            path_rows = [(manifest, f"{stem}_path") for stem in stems]
            path_rows.extend((row, "path") for row in manifest["provider_request_archive"])
            for row, key in path_rows:
                relative = Path(row[key]).relative_to(old_root)
                local = source_root / relative
                local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, local)
                row[key] = str(fictional_old_root / relative)
            self.assertFalse(fictional_old_root.exists())
            manifest["manifest_sha256"] = sha256_bytes(canonical_bytes({
                key: value for key, value in manifest.items() if key != "manifest_sha256"
            }))
            local_manifest = source_root / relative_manifest
            local_manifest.parent.mkdir(parents=True, exist_ok=True)
            local_manifest.write_text(json.dumps(manifest), encoding="utf-8")

            episode = load_episode(local_manifest, source_root=source_root)
            self.assertTrue(episode["candidate_replay_verified"])
            self.assertEqual(len(episode["manifest"]["provider_request_archive"]), 4)

            local_schedule = source_root / Path(original["schedule_path"]).relative_to(old_root)
            local_schedule.write_bytes(local_schedule.read_bytes() + b"\n")
            with self.assertRaisesRegex(V1ValidationError, "schedule: file SHA-256 mismatch"):
                load_episode(local_manifest, source_root=source_root)


if __name__ == "__main__":
    unittest.main()
