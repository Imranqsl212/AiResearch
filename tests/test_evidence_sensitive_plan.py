"""Allocation/provenance tests; these do not admit a main study or call a model."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from collections import Counter
from unittest.mock import patch

from benchmark import evidence_sensitive as benchmark
from experiments import evidence_sensitive_plan as planner


class EvidenceSensitivePlanTests(unittest.TestCase):
    MODEL = {"name": "fixture-model:1", "digest": "a" * 64}

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = planner.build_plan(model=cls.MODEL, repeats=2)

    def test_deterministic_complete_balance_and_shared_sources(self) -> None:
        self.assertEqual(self.plan, planner.build_plan(model=self.MODEL, repeats=2))
        planner.validate_plan(json.loads(json.dumps(self.plan)))
        families = benchmark.family_names()
        self.assertEqual(len(self.plan["blocks"]), len(families) * 4 * 2)
        by_source = {}
        counts = Counter()
        for block in self.plan["blocks"]:
            counts[(block["family"], block["stratum"])] += 1
            self.assertEqual(Counter(b["arm"] for b in block["branches"]),
                             dict.fromkeys(planner.ARMS, 1))
            self.assertEqual(block["initial_source"],
                             benchmark.control_source(block["family"], block["stratum"]))
            self.assertEqual(block["initial_source_sha256"], hashlib.sha256(
                block["initial_source"].encode("utf-8")).hexdigest())
            key = (block["family"], block["stratum"])
            prior = by_source.setdefault(key, block["initial_source"])
            self.assertEqual(prior, block["initial_source"])
            self.assertEqual(block["model_digest"], self.MODEL["digest"])
            for branch in block["branches"]:
                self.assertNotIn("initial_source", branch)
                self.assertNotIn("model", branch)
        self.assertTrue(all(count == 2 for count in counts.values()))

    def test_reserved_seed_slots_are_unique_and_dispatch_is_a_permutation(self) -> None:
        branches = [b for block in self.plan["blocks"] for b in block["branches"]]
        self.assertEqual(len({b["seed"] for b in branches}), len(branches))
        self.assertEqual(len({b["branch_id"] for b in branches}), len(branches))
        self.assertEqual(Counter(self.plan["dispatch_order"]),
                         Counter(b["branch_id"] for b in branches))
        for block in self.plan["blocks"]:
            self.assertEqual([b["seed"] for b in block["branches"]], block["seed_slots"])
            self.assertEqual([b["seed_slot"] for b in block["branches"]], list(range(4)))
        for branch in branches:
            self.assertEqual(self.plan["dispatch_order"][branch["execution_order"]], branch["branch_id"])
            self.assertRegex(branch["branch_id"], r"^r_[a-f0-9]{24}$")
        for block in self.plan["blocks"]:
            self.assertRegex(block["block_id"], r"^b_[a-f0-9]{24}$")

    def test_randomization_domains_separate_assignment_seed_and_order(self) -> None:
        original_key = planner._key

        def changed_assignment(domain, value):
            return original_key(domain + "-test-change" if domain == "arm-assignment" else domain, value)

        with patch.object(planner, "_key", side_effect=changed_assignment):
            changed = planner.build_plan(model=self.MODEL, repeats=2)
        self.assertEqual(changed["dispatch_order"], self.plan["dispatch_order"])
        self.assertEqual([b["seed_slots"] for b in changed["blocks"]],
                         [b["seed_slots"] for b in self.plan["blocks"]])
        self.assertNotEqual([[b["arm"] for b in block["branches"]] for block in changed["blocks"]],
                            [[b["arm"] for b in block["branches"]] for block in self.plan["blocks"]])

        def changed_order(domain, value):
            return original_key(domain + "-test-change" if domain == "dispatch-order" else domain, value)

        with patch.object(planner, "_key", side_effect=changed_order):
            changed = planner.build_plan(model=self.MODEL, repeats=2)
        self.assertNotEqual(changed["dispatch_order"], self.plan["dispatch_order"])
        for expected, actual in zip(self.plan["blocks"], changed["blocks"]):
            self.assertEqual(expected["seed_slots"], actual["seed_slots"])
            self.assertEqual([b["arm"] for b in expected["branches"]],
                             [b["arm"] for b in actual["branches"]])

    def test_no_admission_or_replacement_can_be_added(self) -> None:
        self.assertEqual(self.plan["phase"], "excluded_feasibility")
        self.assertFalse(self.plan["eligible_for_main_analysis"])
        self.assertFalse(self.plan["main_dispatch_allowed"])
        self.assertFalse(self.plan["independently_reviewed"])
        self.assertFalse(self.plan["agent_generated_onset"])
        self.assertTrue(self.plan["no_replacement"])
        for field, value in (("phase", "main"), ("eligible_for_main_analysis", True),
                             ("main_dispatch_allowed", True), ("independently_reviewed", True),
                             ("agent_generated_onset", True), ("no_replacement", False)):
            altered = copy.deepcopy(self.plan)
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(planner.EvidenceSensitivePlanError):
                planner.validate_plan(altered)
        for operation in ("remove", "duplicate"):
            altered = copy.deepcopy(self.plan)
            if operation == "remove":
                altered["blocks"][0]["branches"].pop()
            else:
                altered["blocks"][0]["branches"].append(copy.deepcopy(altered["blocks"][0]["branches"][0]))
            with self.subTest(operation=operation), self.assertRaises(planner.EvidenceSensitivePlanError):
                planner.validate_plan(altered)

    def test_sources_evaluations_hashes_and_assignments_cannot_be_tampered(self) -> None:
        mutations = [
            lambda p: p["blocks"][0].__setitem__("initial_source", "def allow(request): return True\n"),
            lambda p: p["blocks"][0].__setitem__("initial_source_sha256", "0" * 64),
            lambda p: p["blocks"][0].__setitem__("public_task", "changed task"),
            lambda p: p["blocks"][0].__setitem__("initial_state_sha256", "0" * 64),
            lambda p: p["blocks"][0]["initial"].__setitem__("security_pass", False),
            lambda p: p["blocks"][0]["branches"][0].__setitem__("seed", 1),
            lambda p: p["blocks"][0]["branches"][0].__setitem__("arm", "FAKE"),
            lambda p: p["blocks"][0]["branches"][0].__setitem__("execution_order", -1),
            lambda p: p["dispatch_order"].reverse(),
            lambda p: p["source_file_sha256s"].__setitem__("benchmark/evidence_sensitive.py", "0" * 64),
            lambda p: p["inference_config"].__setitem__("temperature", 0.8),
            lambda p: p.__setitem__("unplanned_field", "replacement"),
            lambda p: p.__setitem__("eligible_for_main_analysis", 0),
        ]
        for index, mutate in enumerate(mutations):
            altered = copy.deepcopy(self.plan)
            mutate(altered)
            with self.subTest(index=index), self.assertRaises(planner.EvidenceSensitivePlanError):
                planner.validate_plan(altered)

    def test_cross_model_blocks_cannot_be_mixed_even_with_matching_controls(self) -> None:
        other = planner.build_plan(model={"name": "other-model:1", "digest": "b" * 64}, repeats=2)
        self.assertEqual([b["initial_source"] for b in self.plan["blocks"]],
                         [b["initial_source"] for b in other["blocks"]])
        self.assertTrue(set(self.plan["dispatch_order"]).isdisjoint(other["dispatch_order"]))
        changed = copy.deepcopy(self.plan)
        changed["blocks"][0] = other["blocks"][0]
        with self.assertRaises(planner.EvidenceSensitivePlanError):
            planner.validate_plan(changed)

    def test_feedback_protocol_has_matching_auxiliary_visibility(self) -> None:
        protocol = self.plan["feedback_protocol"]
        self.assertEqual(protocol["first_verdict"]["TRUTHFUL"], "ACTUAL_JOINT_RESULT")
        for arm in ("FLIPPED", "EVIDENCE", "NEUTRAL"):
            self.assertEqual(protocol["first_verdict"][arm], "OPPOSITE_JOINT_RESULT")
        self.assertEqual(protocol["subsequent_ordinary_verdicts"], "ACTUAL_JOINT_RESULT")
        self.assertEqual(protocol["auxiliary_tool_available"],
                         {"TRUTHFUL": False, "FLIPPED": False, "EVIDENCE": True, "NEUTRAL": True})
        self.assertEqual(protocol["auxiliary_visible_tool"], "IDENTICAL_BETWEEN_EVIDENCE_AND_NEUTRAL")

    def test_inputs_are_validated_and_copied(self) -> None:
        family = benchmark.family_names()[0]
        families, strata, model = [family], ["CORRECT"], dict(self.MODEL)
        result = planner.build_plan(families=families, strata=strata, model=model)
        families.clear()
        strata.clear()
        model["digest"] = "b" * 64
        planner.validate_plan(result)
        invalid = [
            {"families": []}, {"families": [family, family]}, {"families": ["unknown"]},
            {"strata": []}, {"strata": ["CORRECT", "CORRECT"]}, {"strata": ["INVALID"]},
            {"repeats": 0}, {"repeats": True}, {"seed": -1}, {"seed": False},
            {"decision_cap": 0}, {"decision_cap": 1.5}, {"temperature": float("nan")},
            {"temperature": float("inf")}, {"temperature": True}, {"num_predict": 0},
            {"request_timeout_seconds": 0}, {"request_timeout_seconds": float("nan")},
            {"backend": "unrestricted"}, {"model": {"name": "x", "digest": "short"}},
            {"model": {"name": "x", "digest": "sha256:" + "a" * 64}},
            {"model": {"name": "x", "digest": "a" * 64, "extra": True}},
        ]
        for arguments in invalid:
            options = {"model": self.MODEL, **arguments}
            with self.subTest(arguments=arguments), self.assertRaises(planner.EvidenceSensitivePlanError):
                planner.build_plan(**options)

    def test_incorrect_control_profile_fails_before_any_allocation(self) -> None:
        original = benchmark.evaluate

        def changed(family, source):
            result = original(family, source)
            result["security_pass"] = not result["security_pass"]
            return result

        with patch.object(benchmark, "evaluate", side_effect=changed):
            with self.assertRaises(planner.EvidenceSensitivePlanError):
                planner.build_plan(model=self.MODEL)


if __name__ == "__main__":
    unittest.main()
