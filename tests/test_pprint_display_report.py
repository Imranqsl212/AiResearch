import copy
import unittest

from analysis.pprint_display_report import ARMS, index_study, policy_baselines, render


def sample():
    variants = {key: {"correct": good, "checks": [{"probe": str(i), "passed": good or i > 0,
                     "bindings_preserved": True, "comparable_keys_sorted": good or i > 0} for i in range(10)]}
                for key, good in (("faulty", False), ("working", True), ("other", True))}
    calibration = {"inputs": {"shared": "3,7", "revealing": "3,20"}, "variants": variants}
    plan, rows = {"blocks": []}, []
    for parent, before, choices in (("a", "faulty", ["keep", "v1", None]),
                                     ("b", "working", ["keep", "v2", "v3"])):
        spec = {"parent_id": parent, "model": "model", "history_sha256": parent,
                "before_variant": before, "before_correct": variants[before]["correct"]}
        prompts = {arm: parent + arm for arm in ARMS}
        options = {"v1": "working", "v2": "other", "v3": "faulty"}
        plan["blocks"].append(dict(spec, order=list(ARMS), options=options, prompt_sha256=prompts))
        for arm, choice in zip(ARMS, choices):
            after = before if choice == "keep" else options.get(choice)
            rows.append(dict(spec, arm=arm, choice=choice, prompt_sha256=prompts[arm],
                             status="OK" if choice else "UNSTARTED", after_variant=after,
                             after_correct=variants[after]["correct"] if after else None))
    return plan, calibration, {"rows": rows}


class DisplayReportTest(unittest.TestCase):
    def test_repairs_preservation_selection_and_missing_pair(self):
        report = render(*sample())
        self.assertIn("| All | No new output | 2/2 | 0/1 | 1/1 | 0/1 | 0/1 |", report)
        self.assertIn("| All | Shared output | 2/2 | 1/1 | 1/1 | 0/1 | 1/1 |", report)
        self.assertIn("| All | Revealing output | 1/2 | — | 0/1 | 1/1 | 0/1 |", report)
        self.assertIn("| No new output vs Shared output | Faulty | 1/1 | 0 | 1 | 0 | 0 | 1/1 |", report)
        self.assertIn("| No new output vs Revealing output | Faulty | 0/1 | 0 | 0 | 0 | 0 | — |", report)
        self.assertIn("| No new output vs Revealing output | Working | 1/1 | 0 | 0 | 1 | 0 | 1/1 |", report)

    def test_study_rejects_overwritten_duplicate_or_misattributed_decisions(self):
        plan, cal, data = sample()
        for field, changed in (("model", "other-model"), ("history_sha256", "other-history"),
                               ("prompt_sha256", "wrong"), ("after_correct", True), ("choice", "v3")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                bad = copy.deepcopy(data)
                bad["rows"][0][field] = changed
                index_study(plan, cal, bad)
        with self.assertRaises(ValueError):
            index_study(plan, cal, {"rows": data["rows"] + data["rows"][:1]})
        with self.assertRaises(ValueError):
            index_study(plan, cal, {"rows": data["rows"][:-1]})

    def test_grade_replayed_from_per_input_results(self):
        plan, cal, data = sample()
        cal["variants"]["faulty"]["checks"][0]["passed"] = True
        with self.assertRaises(ValueError):
            index_study(plan, cal, data)

    def test_rollback_recovers_new_fault_and_reintroduces_old_fault(self):
        plan, calibration, _ = sample()
        variants = calibration["variants"]
        variants["old-bug"] = dict(variants["faulty"])
        assignments, recordings = [], []
        for block, original in zip(plan["blocks"], ["working", "old-bug"]):
            block["options"]["v4"] = "old-bug"
            block["first_response_sha256"] = "d1-" + block["parent_id"]
            assignments.append(dict(case="cpython", episode_id=block["parent_id"], model="model",
                                    start_variant=original, options=block["options"]))
            step = dict(status="OK", before_variant=original, after_variant=block["before_variant"],
                        native_response_sha256=block["first_response_sha256"])
            recordings.append(dict(case="cpython", episode_id=block["parent_id"], steps=[step]))
        inputs = (plan["blocks"], variants, {"episodes": assignments}, {"episodes": recordings})
        summary = policy_baselines(*inputs)
        self.assertIn("| Restore the source before the first edit | 1/1 | 0/1 |", summary)
        self.assertIn("| Keep the post-edit source | 0/1 | 1/1 |", summary)
        self.assertIn("| Choose a passing variant using the held-out grades | 1/1 | 1/1 |", summary)
        recordings[0]["steps"][0]["native_response_sha256"] = "unbound"
        with self.assertRaises(ValueError):
            policy_baselines(*inputs)
