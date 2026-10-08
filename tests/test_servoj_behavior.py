import csv
import math
import tempfile
import unittest
from pathlib import Path

from core.config import Config
from experiments.helpers import cases_for
from experiments.servoj_behavior.experiment import (
    DEFAULT_CSV, START_JOINTS, END_JOINTS, minimum_intervals,
    validate_joint_csv,
)


class ServoJBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_nine_parameter_cases(self):
        cases = cases_for("servoj_behavior", self.config)
        self.assertEqual(len(cases), 9)
        self.assertEqual((cases[0]["aheadtime"], cases[0]["gain"]), (20.0, 500.0))
        self.assertTrue(all(x["global_speed_factor"] == 100 for x in cases))
        self.assertEqual({x["mode"] for x in cases}, {"csv"})
        self.assertEqual(len({x["csv_path"] for x in cases}), 1)

    def test_reference_csv_is_exact_cubic_with_96_samples(self):
        self.assertEqual(minimum_intervals(), 95)
        with DEFAULT_CSV.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 96)
        self.assertEqual({row["mode"] for row in rows}, {"ServoJ"})
        for i, row in enumerate(rows):
            u = i / 95
            s = 3*u*u - 2*u*u*u
            for axis in range(6):
                actual = float(row[f"j{axis+1}"])
                expected = START_JOINTS[axis] + (END_JOINTS[axis]-START_JOINTS[axis])*s
                self.assertAlmostEqual(actual, expected, places=7)
        self.assertAlmostEqual(95*0.03, 2.85)
        self.assertAlmostEqual(1.5*76/2.85, 40.0)

    def test_rejects_wrong_sample_period(self):
        self.config.servo_time_s = 0.020
        with self.assertRaisesRegex(ValueError, "0.030"):
            cases_for("servoj_behavior", self.config)

    def test_wrong_mode_or_deviation_rejected(self):
        with DEFAULT_CSV.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "points.csv"
            rows[2]["mode"] = "ServoP"
            self.write(path, rows)
            with self.assertRaisesRegex(ValueError, "ServoJ"):
                validate_joint_csv(path, self.config)
            rows[2]["mode"] = "ServoJ"
            rows[2]["j1"] = "25"
            self.write(path, rows)
            with self.assertRaisesRegex(ValueError, "cubic"):
                validate_joint_csv(path, self.config)

    @staticmethod
    def write(path, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
