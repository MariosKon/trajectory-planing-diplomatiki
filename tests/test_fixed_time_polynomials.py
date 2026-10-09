"""Offline regression checks; never connect to physical robot hardware."""

import hashlib
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import Config
from core.runner import run_trial
from experiments.csv_servo.points import load_points
from experiments.helpers import cases_for
from experiments.polynomial_fixed_time import (
    DURATION_CASES,
    REFERENCE_END,
    REFERENCE_START,
    SAMPLE_PERIOD_S,
    _verify_reference,
    fixed_time_polynomial_cases,
)


class FixedTimePolynomialTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_three_cases_per_polynomial(self):
        for profile in ("cubic", "quintic"):
            with self.subTest(profile=profile):
                cases = cases_for(profile, self.cfg)
                self.assertEqual(len(cases), 3)
                self.assertEqual(
                    [c["duration_s"] for c in cases],
                    [3.93, 2.79, 2.31],
                )
                self.assertEqual(
                    [c["expected_points"] for c in cases],
                    [132, 94, 78],
                )
                self.assertEqual([c["mode"] for c in cases], ["csv"] * 3)
                self.assertTrue(all(c["global_speed_factor"] == 100
                                    for c in cases))

    def test_csv_references_are_analytic_and_valid(self):
        for profile in ("cubic", "quintic"):
            for label, duration in DURATION_CASES:
                with self.subTest(profile=profile, duration=duration):
                    case = next(
                        x for x in cases_for(profile, self.cfg)
                        if x["duration_s"] == duration
                    )
                    path = Path(case["csv_path"])
                    self.assertEqual(
                        path.name, f"points_{profile}_T{label}.csv",
                    )
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        case["csv_sha256"],
                    )
                    points = load_points(path, "ServoP")
                    self.assertEqual(points[0].values, list(REFERENCE_START))
                    self.assertEqual(points[-1].values, list(REFERENCE_END))
                    self.assertEqual(len(points) - 1,
                                     round(duration / SAMPLE_PERIOD_S))
                    _verify_reference(profile, path, duration)

    def test_speed_tradeoff_is_explicit(self):
        cubic = cases_for("cubic", self.cfg)
        quintic = cases_for("quintic", self.cfg)
        self.assertEqual(
            [x["exceeds_movel_fast_speed"] for x in cubic],
            [False, False, True],
        )
        self.assertEqual(
            [x["exceeds_movel_fast_speed"] for x in quintic],
            [False, True, True],
        )
        self.assertAlmostEqual(cubic[-1]["expected_peak_speed_mm_s"],
                               1200 / 2.31, places=6)
        self.assertAlmostEqual(quintic[-1]["expected_peak_speed_mm_s"],
                               1500 / 2.31, places=6)

    def test_config_period_and_poses_must_match_references(self):
        with self.assertRaisesRegex(ValueError, "servo_time_s"):
            fixed_time_polynomial_cases(
                "cubic", Config(servo_time_s=0.01),
            )
        with self.assertRaisesRegex(ValueError, "start"):
            fixed_time_polynomial_cases(
                "quintic", Config(start=[-600, -350, 250, -90, 0, 90]),
            )
        with self.assertRaisesRegex(ValueError, "target"):
            fixed_time_polynomial_cases(
                "quintic", Config(target=[-600, 350, 250, -90, 0, 90]),
            )

    def test_csv_corruption_is_rejected(self):
        original = Path(cases_for("cubic", self.cfg)[0]["csv_path"])
        with TemporaryDirectory() as temp:
            corrupt = Path(temp) / "corrupt.csv"
            rows = original.read_text(encoding="utf-8").splitlines()
            cells = rows[20].split(",")
            cells[2] = str(float(cells[2]) + 0.5)
            rows[20] = ",".join(cells)
            corrupt.write_text("\n".join(rows) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected pose"):
                _verify_reference("cubic", corrupt, 3.93)

    def test_post_selection_mutation_rejected_before_robot_connection(self):
        case = dict(cases_for("quintic", self.cfg)[0])
        case["csv_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "changed after case"):
            run_trial(self.cfg, case, Path("not-used"))

    def test_explicit_csv_preserves_single_case_workflow(self):
        cases = cases_for("cubic", self.cfg, csv_path="custom.csv")
        self.assertEqual(len(cases), 1)
        self.assertTrue(cases[0]["csv_path"].endswith("custom.csv"))
        self.assertNotIn("duration_s", cases[0])

    def test_matlab_export_diagnostics_remain_enabled(self):
        root = Path(__file__).resolve().parents[1]
        generator = (root / "experiments" / "polynomial_fixed_time"
                     / "generate_fixed_time_polynomial.m").read_text(
                         encoding="utf-8")
        self.assertIn("exported = readtable(path);", generator)
        self.assertIn("CSV read-back: PASS", generator)
        self.assertIn("maxPositionError > 2e-6", generator)
        self.assertIn("plot(t, stored(:,2)", generator)
        self.assertIn("FINAL SUMMARY (all CSV files verified)", generator)
        for profile in ("cubic", "quintic"):
            with self.subTest(profile=profile):
                wrapper = (root / "experiments" / profile
                           / f"make_{profile}_csv.m").read_text(
                               encoding="utf-8")
                self.assertIn("makePlot = true;", wrapper)


if __name__ == "__main__":
    unittest.main()
