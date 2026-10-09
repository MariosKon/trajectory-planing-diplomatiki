import csv
import tempfile
import unittest
from pathlib import Path

from core.config import Config
from experiments.helpers import cases_for
from experiments.servoP_confirmation.experiment import (
    DEFAULT_CSV, validate_quintic_csv,
)


class QuinticConfirmationTests(unittest.TestCase):
    def test_three_cases_share_identical_reference(self):
        cases = cases_for("servoP_confirmation", Config())
        self.assertEqual(len(cases), 3)
        self.assertEqual(
            [(c["aheadtime"], c["gain"]) for c in cases],
            [(20.0, 300.0), (20.0, 500.0), (50.0, 300.0)],
        )
        self.assertEqual(len({c["csv_path"] for c in cases}), 1)
        self.assertEqual(len({c["csv_sha256"] for c in cases}), 1)
        self.assertTrue(all(c["global_speed_factor"] == 100 for c in cases))

    def test_quintic_shape_and_sample_count(self):
        self.assertEqual(validate_quintic_csv(DEFAULT_CSV, Config()), DEFAULT_CSV.resolve())
        with DEFAULT_CSV.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 68)
        self.assertTrue(all(r["mode"] == "ServoP" for r in rows))
        self.assertAlmostEqual(67 * 0.03, 2.01)

    def test_reject_wrong_sampling_period(self):
        with self.assertRaisesRegex(ValueError, "0.030"):
            validate_quintic_csv(DEFAULT_CSV, Config(servo_time_s=0.02))

    def test_reject_modified_quintic(self):
        with DEFAULT_CSV.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[12]["x2"] = "123.0"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "changed.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "quintic|Quintic"):
                validate_quintic_csv(path, Config())


if __name__ == "__main__":
    unittest.main()
