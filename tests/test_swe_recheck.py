import unittest
from analysis.swe_recheck import formal_verdict, recognized, flags


class RepeatedCommandTests(unittest.TestCase):
    def test_wrapped_directory_sensitivity(self):
        for cmd in ("cd /repo && python example.py","cd /repo\npython example.py"):
            self.assertFalse(recognized(cmd))
            self.assertTrue(recognized(cmd, allow_cd=True))
        for cmd in ("cd $base && python example.py", "cd /repo && pytest && ls", "python demo.py | cat"):
            self.assertFalse(recognized(cmd, allow_cd=True))

    def test_suite_evidence(self):
        self.assertEqual(formal_verdict("Ran 7 tests in 1.35s\n\nOK\n"), "pass")
        self.assertEqual(formal_verdict("====== 2 failed, 7 passed in 1.42s ======"), "fail")
        self.assertIsNone(formal_verdict("ValueError\n[Command finished with exit code 0]"))
        self.assertIsNone(formal_verdict("Ran 0 tests in 0.01s\n\nOK\n"))
        self.assertIsNone(formal_verdict("2 skipped in 1.2s"))

    def test_repeated_exit_and_verdict(self):
        calls=[{"process_exit":1, "verdict":None},{"process_exit":0, "verdict":None}]
        f=flags({"commands":{"abc":calls}, "available":True})
        self.assertTrue(f["exit_recovery"])
        self.assertFalse(f["suite_recovery"])
