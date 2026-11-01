"""Meaningful source, blinding, and human-workflow checks for excluded V7 packets."""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis.v7_blind_annotation_packet import (
    ROOT, FORM_FIELDS, PairSpec, PacketError, build_packet, write_bundle,
)
from analysis.validate_v7_blind_annotation_packet import (
    ADJUDICATION_FIELDS, _packet_and_map, seal_ratings, validate_adjudications,
    verify_packet,
)


class V7BlindAnnotationPacketTests(unittest.TestCase):
    def one_pair(self) -> PairSpec:
        base = ROOT / "experiments/runs/v7_second_wave_20261101/signature_algorithm"
        return PairSpec(base / "pair", base / "precursor")

    def test_deterministic_verified_projection_keeps_public_feedback_only(self) -> None:
        spec = self.one_pair()
        left, private = build_packet(specs=[spec], salt=b"x" * 32)
        right, _ = build_packet(specs=[spec], salt=b"x" * 32)
        self.assertEqual(left, right)
        self.assertEqual(left["scope"], "EXCLUDED_TRAINING_ONLY")
        self.assertEqual(left["manifest"]["episode_count"], 2)
        self.assertEqual(left["manifest"]["transition_count"], 4)
        self.assertEqual({e["first_feedback_delivered"]["public_verdict"]
                          for e in left["episodes"]}, {"PASS", "FAIL"})
        self.assertNotEqual(left["episodes"][0]["episode_id"],
                            left["episodes"][1]["episode_id"])
        self.assertEqual(len(private["identities"]), 2)
        # No structured hidden verdict, arm, condition, pair identity, or raw
        # provider response is copied into the coder-facing packet.
        hidden_keys = {"arm", "arm_order", "condition", "gate_mode", "result",
                       "reference_results", "security_oracle_result", "strong_test_result",
                       "raw_test_result", "pair_dir", "precursor_dir", "response_path",
                       "response_sha256", "model", "seed", "thinking", "messages"}

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()

        self.assertFalse(keys(left) & hidden_keys)
        for episode in left["episodes"]:
            for event in episode["continuation_events"]:
                if event["public_observation_delivered"] is not None:
                    self.assertIn(event["public_observation_delivered"]["public_verdict"],
                                  {"PASS", "FAIL"})
            # The last generated checker observation was not delivered to a
            # following model request, so it is never shown as agent evidence.
            self.assertIsNone(episode["continuation_events"][-1][
                "public_observation_delivered"])

    def test_tampered_response_is_rejected_by_archive_replay(self) -> None:
        spec = self.one_pair()
        with tempfile.TemporaryDirectory() as temp:
            pair = Path(temp) / "pair"
            shutil.copytree(spec.pair_dir, pair)
            response = pair / "false_fail.000001.response.bin"
            response.write_bytes(response.read_bytes() + b" ")
            with self.assertRaises((PacketError, ValueError)):
                build_packet(specs=[PairSpec(pair, spec.precursor_dir)], salt=b"x" * 32)

    def test_packet_injection_is_rejected_on_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "bundle"
            write_bundle(bundle)
            path = bundle / "packet.json"
            packet = json.loads(path.read_text(encoding="utf-8"))
            packet["episodes"][0]["reference_results"] = ["SECURE"]
            path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaises(PacketError):
                _packet_and_map(bundle)

    @staticmethod
    def _filled(template: Path, output: Path, coder: str,
                *, first_label: str = "S0") -> list[dict[str, str]]:
        with template.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for i, row in enumerate(rows):
            row["coder_id"] = coder
            row["label"] = first_label if i == 0 else "S0"
            row["rationale"] = "Synthetic test rationale from visible policy modes."
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FORM_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return rows

    def test_blank_templates_cannot_be_sealed_and_third_coder_follows_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = base / "bundle"
            write_bundle(bundle)
            status = verify_packet(bundle)
            self.assertEqual(status["episodes"], 10)
            self.assertEqual(status["transitions"], 13)
            self.assertFalse(status["main_eligible"])
            _packet_and_map(bundle)
            template = bundle / "rater_A_template.csv"
            rater_a, rater_b = base / "a.csv", base / "b.csv"
            seal_path = bundle / "private/seal.json"
            with self.assertRaises(PacketError):
                seal_ratings(bundle, template, bundle / "rater_B_template.csv", seal_path)
            rows_a = self._filled(template, rater_a, "human:testA")
            self._filled(template, rater_b, "human:testA")
            with self.assertRaises(PacketError):
                seal_ratings(bundle, rater_a, rater_b, seal_path)
            self._filled(template, rater_b, "human:testB", first_label="S3")
            adjudication = base / "adjudications.csv"
            with adjudication.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_FIELDS)
                writer.writeheader()
                writer.writerow({"packet_sha256": rows_a[0]["packet_sha256"],
                                 "episode_id": rows_a[0]["episode_id"],
                                 "transition_id": rows_a[0]["transition_id"],
                                 "adjudicator_id": "human:testC", "label": "S3",
                                 "rationale": "Synthetic test adjudication on the policy change."})
            with self.assertRaises(PacketError):
                validate_adjudications(bundle, rater_a, rater_b, seal_path, adjudication)
            seal = seal_ratings(bundle, rater_a, rater_b, seal_path)
            self.assertEqual(seal["agreement_before_adjudication"]["disagreement_units"], 1)
            validated = validate_adjudications(bundle, rater_a, rater_b,
                                               seal_path, adjudication)
            self.assertEqual(validated["adjudicator_id"], "human:testC")
            self.assertEqual(validated["adjudicated_disagreements"], 1)
            self.assertFalse(validated["main_eligible"])
            # A later change to either independently sealed file invalidates
            # the adjudication, even if its labels still look plausible.
            rater_a.write_bytes(rater_a.read_bytes() + b"\n")
            with self.assertRaises(PacketError):
                validate_adjudications(bundle, rater_a, rater_b, seal_path,
                                       adjudication)

    def test_unassessable_is_explicit_and_excluded_from_kappa(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = base / "bundle"
            write_bundle(bundle)
            template = bundle / "rater_A_template.csv"
            rater_a, rater_b = base / "a.csv", base / "b.csv"
            self._filled(template, rater_a, "human:testA", first_label="UNASSESSABLE")
            self._filled(template, rater_b, "human:testB", first_label="S0")
            seal = seal_ratings(bundle, rater_a, rater_b, bundle / "private/seal.json")
            agreement = seal["agreement_before_adjudication"]
            self.assertEqual(agreement["total_units"], 13)
            self.assertEqual(agreement["paired_unassessable_units"], 1)
            self.assertEqual(agreement["n"], 12)


if __name__ == "__main__":
    unittest.main()
