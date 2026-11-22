"""Scanner accuracy on the sample app corpus in tests/corpus.py: every planted problem is caught,
and the safe twin of each app raises nothing at medium or worse."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus  # noqa: E402


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = corpus.measure()

    def test_every_planted_problem_is_caught(self):
        for name, found, missed, alarms, fg, fb in self.rows:
            with self.subTest(app=name):
                self.assertEqual(missed, [])

    def test_safe_twins_raise_no_false_alarms(self):
        for name, found, missed, alarms, fg, fb in self.rows:
            with self.subTest(app=name):
                self.assertEqual([(a["check"], a["severity"], a["file"]) for a in alarms], [])


if __name__ == "__main__":
    unittest.main()
