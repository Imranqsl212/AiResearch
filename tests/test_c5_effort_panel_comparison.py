import unittest
from analysis import c5_effort_panel_comparison as report


def row(effort, outcomes, seconds=2.5, output=12):
    tasks = [{"task": key, "starting_correct": key in report.CORRECT_START, "valid": value is not None,
              "final_correct": value, "unnecessary_rewrite": False if value is not None else None}
             for key,value in zip(report.TASKS, outcomes)]
    observed = [t for t in tasks if t["valid"]]
    def rate(state):
        group = [t for t in observed if t["starting_correct"] == state]
        return [sum(t["final_correct"] for t in group),len(group)]
    return {"model":"gpt-fixture","effort":effort,"tasks":tasks,
            "status":"RETURNED" if all(t["valid"] for t in tasks) else "RETURNED_WITH_FORMAT_ERROR",
            "correct":sum(t["final_correct"] for t in observed),"valid_tasks":len(observed),
            "unnecessary_rewrites":0,"preserved":rate(True),"repaired":rate(False),"elapsed_seconds":seconds,
            "usage":{"input_tokens":20,"cached_input_tokens":4,"output_tokens":output,"reasoning_output_tokens":3}}


class ComparisonTests(unittest.TestCase):
    def test_equal_scores_can_swap_tasks(self):
        low = row("low", [True,True,True,True,False,False])
        high = row("high",[False,True,True,True,True,False],4.5,9)
        item = report.compare(low,high)
        self.assertEqual(item,{"net":0,"gains":["E"],"losses":["A"],"output":-3,"seconds":2})
        contents = report.render({"schema":"c5-codex-effort-panel-v1","rows":[high,low]},"a"*64)
        self.assertIn("| gpt-fixture | high | +0 | E | A | +2 | -3 |", contents)
        self.assertIn("| high | 1 | 0 / 1 / 0 | 1 / 1 | +2 (1) | -3 (1) |",contents)

    def test_partial_and_missing_rows(self):
        low=row("low",[True]*6)
        medium=row("medium",[True,False,None,None,None,None])
        high=row("high",[],None,None)
        high["status"]="UNSTARTED"
        self.assertIsNone(report.compare(low,medium))
        self.assertEqual(report.task_cells(medium),"✓×····")
        out=report.render({"schema":"c5-codex-effort-panel-v1","rows":[medium,high,low]},"b"*64)
        self.assertIn("| gpt-fixture | 6/6 | 1/2 | Н/Д | — | — | — |",out)
        self.assertIn("Всего оценено 8 из 18",out)
        self.assertIn("| high | 0 |",out)

    def test_missing_usage_is_excluded_from_medians(self):
        high = row("high",[True]*6,None,None)
        low = row("low",[True]*6)
        delta = report.compare(low,high)
        self.assertIsNone(delta["seconds"])
        self.assertEqual(report.metric([None,3,5]),"+4 (2)")
        self.assertEqual(report.metric([None]),"—")

    def test_reject_duplicate_cell_and_broken_totals(self):
        data = row("low",[True]*6)
        with self.assertRaises(ValueError): report.validate([data,data])
        data["preserved"] = [2,3]
        with self.assertRaises(ValueError): report.validate([data])


if __name__ == "__main__":
    unittest.main()
