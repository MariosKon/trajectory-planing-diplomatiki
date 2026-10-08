import unittest

from main import select_cases
from core.config import Config
from experiments.helpers import cases_for


class CaseSelectionTests(unittest.TestCase):
    def setUp(self):
        self.cases = cases_for("movel", Config())

    def test_movel_has_nine_cases(self):
        self.assertEqual(len(self.cases), 9)

    def test_selects_first_case(self):
        selected = select_cases(self.cases, 1)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["speed"], 50)
        self.assertEqual(selected[0]["acceleration"], 50)
        self.assertEqual(selected[0]["matrix_case_index"], 1)
        self.assertEqual(selected[0]["matrix_case_count"], 9)

    def test_selects_last_case(self):
        selected = select_cases(self.cases, 9)
        self.assertEqual(selected[0]["speed"], 100)
        self.assertEqual(selected[0]["acceleration"], 100)
        self.assertEqual(selected[0]["matrix_case_index"], 9)
        self.assertEqual(selected[0]["matrix_case_count"], 9)

    def test_none_keeps_all_cases(self):
        self.assertEqual(select_cases(self.cases, None), self.cases)

    def test_out_of_range_rejected(self):
        for index in (-1, 0, 10):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    select_cases(self.cases, index)


if __name__ == "__main__":
    unittest.main()
