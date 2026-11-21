import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("EMBEDDING_REVISION", "0" * 40)
from rag_experiment import analyze, evaluate, pilot
from rag_experiment.corpus import load_corpus
from rag_experiment.schedule import make_schedule, validate_schedule


class PilotTests(unittest.TestCase):
    def test_tasks_have_unique_ids_and_known_relevant_documents(self):
        tasks = json.loads(pilot.TASKS.read_text(encoding="utf-8"))
        ids = {document.document_id for document in load_corpus(pilot.CORPUS)}
        self.assertEqual(len({task["id"] for task in tasks}), len(tasks))
        self.assertEqual(set(evaluate.CHECKS), {task["id"] for task in tasks})
        self.assertTrue(all(task["relevant_id"] in ids for task in tasks))

    def test_judge_distinguishes_functionality_and_injection(self):
        safe = "def find_user(c, name): return c.execute('SELECT * FROM users WHERE name=?', (name,)).fetchall()"
        unsafe = "def find_user(c, name): return c.execute(\"SELECT * FROM users WHERE name='%s'\" % name).fetchall()"
        self.assertEqual(evaluate._check(safe, "find_user", evaluate.CHECKS["sql-name"][0])["status"], "pass")
        self.assertEqual(evaluate._check(safe, "find_user", evaluate.CHECKS["sql-name"][1])["status"], "pass")
        self.assertEqual(evaluate._check(unsafe, "find_user", evaluate.CHECKS["sql-name"][1])["status"], "fail")

    def test_failed_generation_remains_recorded(self):
        task = {"id": "sample", "prompt": "hello", "relevant_id": "x"}
        with tempfile.TemporaryDirectory() as directory:
            pilot._run_attempt(task, "semantic", None, Path(directory))
            result = json.loads((Path(directory) / "sample--semantic--seed-7.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "error")

    def test_html_and_path_checks_reject_known_bad_behaviors(self):
        html = "def label(value): return '<span>' + value + '</span>'"
        path = "def read_report(base, name): return open(base + '/' + name).read()"
        self.assertEqual(evaluate._check(html, "label", evaluate.CHECKS["html-label"][1])["status"], "fail")
        self.assertEqual(evaluate._check(path, "read_report", evaluate.CHECKS["path-report"][1])["status"], "fail")

    def test_baseline_has_identical_task_without_documents(self):
        task = {"id": "sample", "prompt": "repair this", "relevant_id": "x"}
        record = pilot._attempt(task, "baseline", None)
        self.assertEqual(record["prompt"], task["prompt"])
        self.assertEqual(record["documents"], [])

    def test_run_records_both_conditions(self):
        tasks = [{"id": "t", "prompt": "repair", "relevant_id": "none"}]
        with tempfile.TemporaryDirectory() as directory, patch.object(pilot, "_prepare") as prepare, patch.object(pilot, "generate", return_value={"response": {"response": "code"}}):
            prepare.return_value.search.return_value = []; pilot._run(tasks, Path(directory))
            self.assertEqual(json.loads((Path(directory) / "summary.json").read_text())["completed"], 6)
            self.assertEqual(len(list(Path(directory).glob("*--*.json"))), 6)

    def test_missing_record_is_reported(self):
        slot = {"task_id": "sql-name", "mode": "baseline", "seed": 7}
        with tempfile.TemporaryDirectory() as directory: result = evaluate._evaluate_slot(Path(directory), slot)
        self.assertEqual(result["status"], "missing_record")

    def test_zero_exit_before_check_does_not_pass(self):
        result = evaluate._check("import sys; sys.exit(0)", "find_user", "assert False")
        self.assertEqual(result["status"], "fail")

    def test_schedule_pairs_are_deterministic(self):
        slots = make_schedule([{"id": "sample"}])
        self.assertEqual(slots, make_schedule([{"id": "sample"}]))
        self.assertEqual({(slot["seed"], slot["mode"]) for slot in slots}, {(seed, mode) for seed in (7, 17, 27) for mode in ("baseline", "semantic")})

    def test_duplicate_schedule_is_rejected(self):
        slots = make_schedule([{"id": "sample"}])
        with self.assertRaises(ValueError): validate_schedule(slots + slots[:1])

    def test_missing_results_do_not_become_failures(self):
        schedule = make_schedule([{"id": "sql-name"}])
        report = analyze.summarize(schedule, {})
        self.assertEqual(report["pair_counts"], {"incomplete": 3})
        self.assertEqual(report["statuses"], {"missing_evaluation": 6})
        self.assertEqual(report["claim_status"], "NOT_READY")

    def test_paired_comparison_excludes_timeout(self):
        schedule = [{"task_id": "sql-name", "seed": 7, "mode": mode} for mode in ("baseline", "semantic")]
        rows = {("sql-name", 7, "baseline"): {"status": "evaluated", "functionality": {"status": "pass"}, "security": {"status": "timeout"}}}
        self.assertEqual(analyze.summarize(schedule, rows)["pair_counts"], {"incomplete": 1})


if __name__ == "__main__":
    unittest.main()
