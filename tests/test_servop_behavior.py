import csv
import math
import tempfile
import unittest
from pathlib import Path

from core.config import Config
from experiments.helpers import cases_for
from experiments.servop_behavior.experiment import DEFAULT_CSV, validate_cartesian_csv


class ServoPBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_nine_cases_and_baseline(self):
        cases = cases_for("servop_behavior", self.cfg)
        self.assertEqual(len(cases), 9)
        self.assertEqual((cases[0]["aheadtime"], cases[0]["gain"]), (20.0, 500.0))
        self.assertTrue(all(c["mode"] == "csv" for c in cases))
        self.assertTrue(all(c["global_speed_factor"] == 100 for c in cases))
        self.assertEqual(len({c["csv_path"] for c in cases}), 1)

    def test_reference_matches_30ms_cubic(self):
        with DEFAULT_CSV.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 68)
        self.assertEqual([float(rows[0][f"x{i}"]) for i in range(1,7)], self.cfg.start)
        self.assertEqual([float(rows[-1][f"x{i}"]) for i in range(1,7)], self.cfg.target)
        for k, row in enumerate(rows):
            u = k / 67.0
            self.assertEqual(row["mode"], "ServoP")
            self.assertAlmostEqual(float(row["x2"]), -400 + 800*(3*u*u-2*u*u*u), places=5)
        self.assertAlmostEqual(67*0.030, 2.01)

    def test_rejects_wrong_sample_period(self):
        self.cfg.servo_time_s = 0.020
        with self.assertRaisesRegex(ValueError, "0.030"):
            cases_for("servop_behavior", self.cfg)

    def test_rejects_joint_mode_and_wrong_path(self):
        with DEFAULT_CSV.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        fields = list(rows[0])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "points.csv"
            rows[1]["mode"] = "ServoJ"
            self._write(out, fields, rows)
            with self.assertRaisesRegex(ValueError, "ServoP"):
                validate_cartesian_csv(out, self.cfg)
            rows[1]["mode"] = "ServoP"
            rows[1]["x1"] = "-599"
            self._write(out, fields, rows)
            with self.assertRaisesRegex(ValueError, "straight line"):
                validate_cartesian_csv(out, self.cfg)

    @staticmethod
    def _write(path, fields, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
