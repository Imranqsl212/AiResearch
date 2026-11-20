import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("EMBEDDING_REVISION", "0" * 40)
from rag_experiment import evaluate, pilot
from rag_experiment.corpus import load_corpus


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
            result = json.loads((Path(directory) / "sample--semantic.json").read_text(encoding="utf-8"))
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
            self.assertEqual(json.loads((Path(directory) / "summary.json").read_text())["completed"], 2)
            self.assertEqual(len(list(Path(directory).glob("*--*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
