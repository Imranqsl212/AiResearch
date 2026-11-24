import unittest

from analysis.c5_effort_format_audit import response_format
from experiments.c5_effort_panel import TASKS, canonical


class FormatAuditTests(unittest.TestCase):
    def test_literal_keep_matches_indices_without_flattening_or_coercion(self):
        obj = dict.fromkeys(TASKS,"keep")
        obj["A"] = [["keep"],16,17]
        obj["C"] = [8,7,"keep"]
        obj["E"] = ["keep",4,"keep",2,4]
        obj["F"] = ["keep",4,0]
        row = response_format(canonical(obj))
        self.assertEqual(row["literal_keep_new_task_correctness"],{"C":True,"E":True,"F":False})
        self.assertEqual((row["literal_keep_added_scorable"],row["literal_keep_added_wrong"]),(3,1))
        for invalid in (["keep",True,2,2,4],["keep"],["keep","2",2,2,4]):
            obj["E"] = invalid
            self.assertNotIn("E",response_format(canonical(obj))["literal_keep_new_task_correctness"])

    def test_fence_scored_separately(self):
        obj=dict.fromkeys(TASKS,"keep")
        valid=canonical(obj)
        row=response_format(b"```json\n"+valid+b"\n```")
        self.assertEqual((row["primary_valid"],row["fence_only_added_scorable"],row["fence_only_added_correct"]),
                         (0,6,3))
        obj["E"]=["keep",4,"keep",2,4]
        row=response_format(b"```json\n"+canonical(obj)+b"\n```")
        self.assertEqual(row["fence_only_added_scorable"],5)
        self.assertEqual(row["literal_keep_added_scorable"],0)

    def test_malformed_json_categories(self):
        for raw,category in ((b"", "EMPTY_MESSAGE"),(b"I cannot help.", "REFUSAL_LIKE_PREFIX"),
                             (b"Here is your response: {}", "TEXT_PREFIX_BEFORE_JSON_OBJECT"),
                             (b"[]", "JSON_NON_OBJECT"),(b'{"A":1,"A":2}',"INVALID_STRICT_JSON_OBJECT")):
            row=response_format(raw)
            self.assertEqual(row["class"],category)
            self.assertEqual(row["literal_keep_added_scorable"],0)
            self.assertEqual(row["fence_only_added_scorable"],0)


if __name__=="__main__":
    unittest.main()
