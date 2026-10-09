"""Pure offline matched-duration piecewise trajectory checks."""
import csv
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import Config
from core.runner import run_trial
from experiments.helpers import cases_for
from experiments.csv_servo.points import load_points
from experiments.piecewise_fixed_time import (
    PEAK_SPEEDS_MM_S, expected_positions, phase_parameters, verify_reference,
)
from experiments.polynomial_fixed_time import DURATION_CASES, REFERENCE_END, REFERENCE_START


class PiecewiseTimeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_cases_match_polynomial_reference_times(self):
        for profile in ("trapezoidal", "double_s", "ruckig"):
            with self.subTest(profile=profile):
                cases = cases_for(f"{profile}_matched", self.cfg)
                self.assertEqual(len(cases), 3)
                self.assertEqual([c["duration_s"] for c in cases], [3.93, 2.79, 2.31])
                self.assertEqual([c["expected_peak_speed_mm_s"] for c in cases],
                                 list(PEAK_SPEEDS_MM_S))
                self.assertTrue(all(c["global_speed_factor"] == 100 for c in cases))
                self.assertFalse(any(c["exceeds_movel_fast_speed"] for c in cases))

    def test_csv_endpoints_modes_counts_and_analytic_samples(self):
        for profile in ("trapezoidal", "double_s"):
            for (label, duration), speed in zip(DURATION_CASES, PEAK_SPEEDS_MM_S):
                with self.subTest(profile=profile, duration=duration):
                    case = next(c for c in cases_for(f"{profile}_matched", self.cfg)
                                if c["duration_s"] == duration)
                    self.assertEqual(case["expected_points"],
                                     round(duration / .03) + 1)
                    self.assertEqual(Path(case["csv_path"]).name,
                                     f"points_{profile}_T{label}.csv")
                    points = load_points(case["csv_path"], "ServoP")
                    self.assertEqual(points[0].values, list(REFERENCE_START))
                    self.assertEqual(points[-1].values, list(REFERENCE_END))
                    self.assertTrue(all(p.mode == "ServoP" for p in points))
                    verify_reference(profile, case["csv_path"], duration, speed)

    def test_phase_limits_and_progress(self):
        for (label, duration), speed in zip(DURATION_CASES, PEAK_SPEEDS_MM_S):
            ramp, jtime, a_trap, a_s, jerk_s = phase_parameters(duration, speed)
            self.assertGreater(duration - 2 * ramp, 0)
            self.assertGreater(jtime, 0)
            self.assertGreater(a_s, a_trap)
            self.assertGreater(jerk_s, 0)
            for profile in ("trapezoidal", "double_s"):
                rows = expected_positions(profile, duration, speed)
                self.assertEqual(rows[0], list(REFERENCE_START))
                self.assertEqual(rows[-1], list(REFERENCE_END))
                ys = [row[1] for row in rows]
                self.assertTrue(all(a <= b for a, b in zip(ys, ys[1:])))
                self.assertTrue(all(math.isclose(row[0], -600, abs_tol=1e-10)
                                    for row in rows))

    def test_external_csv_still_single_case(self):
        for profile in ("trapezoidal", "double_s"):
            cases = cases_for(profile, self.cfg, csv_path="custom.csv")
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["mode"], "csv")

    def test_invalid_config_and_corrupted_samples_rejected(self):
        with self.assertRaisesRegex(ValueError, "servo_time_s"):
            cases_for("trapezoidal_matched", Config(servo_time_s=0.02))
        with self.assertRaisesRegex(ValueError, "target"):
            cases_for("ruckig_matched", Config(target=[-600, 350, 250, -90, 0, 90]))
        original = cases_for("double_s_matched", self.cfg)[0]["csv_path"]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.csv"
            rows = Path(original).read_text(encoding="utf-8").splitlines()
            columns = rows[20].split(",")
            columns[2] = str(float(columns[2]) + 1)
            rows[20] = ",".join(columns)
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected pose"):
                verify_reference("double_s", path, 3.93, 300)

    def test_sha_preflight_prevents_changed_data(self):
        case = dict(cases_for("trapezoidal_matched", self.cfg)[0])
        case["csv_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "changed after case"):
            run_trial(self.cfg, case, Path("unused"))

    def test_ruckig_limits_and_min_duration_are_recorded(self):
        for case in cases_for("ruckig", self.cfg):
            self.assertEqual(case["mode"], "ruckig")
            self.assertEqual(case["minimum_duration_s"], case["duration_s"])
            self.assertEqual(case["start"], list(REFERENCE_START))
            self.assertEqual(case["target"], list(REFERENCE_END))
            self.assertEqual(len(case["max_velocity"]), 6)
            _, _, _, a_s, j_s = phase_parameters(
                case["duration_s"], case["expected_peak_speed_mm_s"])
            self.assertAlmostEqual(case["max_acceleration"][1], a_s)
            self.assertAlmostEqual(case["max_jerk"][1], j_s)

    def test_optional_ruckig_planner_offline(self):
        try:
            from experiments.ruckig.planner import OnlineRuckigPlanner
        except ImportError:
            self.skipTest("Ruckig package not installed")
        for case in cases_for("ruckig", self.cfg):
            with self.subTest(duration=case["duration_s"]):
                planner = OnlineRuckigPlanner(
                    start=case["start"], target=case["target"], period_s=0.03,
                    max_velocity=case["max_velocity"],
                    max_acceleration=case["max_acceleration"],
                    max_jerk=case["max_jerk"],
                    minimum_duration_s=case["minimum_duration_s"],
                )
                last = None
                for _ in range(1000):
                    last = planner.update()
                    if last.finished:
                        break
                self.assertTrue(last.finished)
                self.assertGreaterEqual(last.trajectory_duration_s + 1e-8,
                                        case["minimum_duration_s"])
                for value, target in zip(last.position, REFERENCE_END):
                    self.assertAlmostEqual(value, target, places=5)
                self.assertLess(max(abs(v) for v in last.velocity), 1e-4)


if __name__ == "__main__":
    unittest.main()
