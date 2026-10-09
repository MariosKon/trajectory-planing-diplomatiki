"""Fixed-time polynomial timing, acquisition coverage, and summary regression tests."""

import csv
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.analysis import aggregate, analyze_trial
from core.config import Config
from core.runner import capture_config_for_case, execute_motion


class PolynomialTimingTests(unittest.TestCase):
    def test_fixed_time_scope_uses_same_12_second_window_for_all_cases(self):
        cfg = Config(
            rigol_resource="FAKE",
            rigol_horizontal_scale_s_per_div=0.5,
        )
        for duration in (3.93, 2.79, 2.31):
            with self.subTest(duration=duration):
                trial = capture_config_for_case(
                    cfg, {"mode": "csv", "duration_s": duration}
                )
                self.assertEqual(trial.rigol_horizontal_scale_s_per_div, 1.0)
                self.assertEqual(cfg.rigol_horizontal_scale_s_per_div, 0.5)
                self.assertEqual(trial.servop_gain, cfg.servop_gain)

    def test_custom_long_scope_or_unrelated_experiment_not_overridden(self):
        cfg = Config(rigol_resource="FAKE", rigol_horizontal_scale_s_per_div=2.0)
        self.assertIs(capture_config_for_case(
            cfg, {"mode": "csv", "duration_s": 2.31}
        ), cfg)
        cfg.rigol_horizontal_scale_s_per_div = 0.5
        self.assertIs(capture_config_for_case(cfg, {"mode": "movel"}), cfg)
        self.assertIs(capture_config_for_case(
            cfg, {"mode": "csv", "csv_path": "manual.csv"}
        ), cfg)

    def test_servo_stream_events_and_idle_wait_are_separately_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "simple.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["mode", "x1", "x2", "x3", "x4", "x5", "x6"])
                writer.writerow(["ServoP", -600, -400, 250, -90, 0, 90])
                writer.writerow(["ServoP", -600, 400, 250, -90, 0, 90])
            events = []
            class Motion:
                def ServoP(self, *_args):
                    return "0,{},ServoP();"
            robot = types.SimpleNamespace(motion=Motion())
            manager = types.SimpleNamespace(
                robot=types.SimpleNamespace(
                    t0=time.perf_counter(), set_commanded_point=lambda _: None
                ),
                event=lambda name, details="": events.append(name),
            )
            fake_sdk = types.ModuleType("dobot_sdk")
            fake_sdk.CoordinateType = types.SimpleNamespace(CARTESIAN=1, JOINT=0)
            with patch.dict(sys.modules, {"dobot_sdk": fake_sdk}):
                with patch("core.runner.wait_for_motion"):
                    result = execute_motion(
                        robot, Config(servo_time_s=0.004),
                        {"mode": "csv", "csv_path": str(path)},
                        manager, Path(tmp),
                    )
            self.assertEqual(result["command_count"], 2)
            self.assertAlmostEqual(result["planned_trajectory_duration_s"], 0.004)
            self.assertAlmostEqual(result["expected_stream_period_s"], 0.008)
            self.assertGreaterEqual(result["first_to_last_command_s"], 0)
            self.assertGreaterEqual(result["wait_for_robot_idle_s"], 0)
            self.assertLess(result["first_to_last_command_s"], 0.25)
            for name in (
                "SERVO_FIRST_COMMAND_SENT", "SERVO_LAST_COMMAND_SENT",
                "SERVO_STREAM_PERIOD_END", "SERVO_ROBOT_IDLE"
            ):
                self.assertEqual(events.count(name), 1)

    def test_physical_tcp_travel_is_separate_from_command_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (root / "events.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["host_time_s", "event"]
                )
                writer.writeheader()
                for t, event in [
                    (1, "MOTION_START"),
                    (1.10, "SERVO_FIRST_COMMAND_SENT"),
                    (4.03, "SERVO_LAST_COMMAND_SENT"),
                    (4.06, "SERVO_STREAM_PERIOD_END"),
                    (4.8, "SERVO_ROBOT_IDLE"),
                    (4.8, "MOTION_END"),
                ]:
                    writer.writerow({"host_time_s": t, "event": event})
            with (root / "commands.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "mode", "position_1", "position_2", "position_3",
                ])
                writer.writeheader()
                writer.writerow({
                    "mode": "ServoP", "position_1": -600,
                    "position_2": -400, "position_3": 250,
                })
                writer.writerow({
                    "mode": "ServoP", "position_1": -600,
                    "position_2": 400, "position_3": 250,
                })
            with (root / "feedback.csv").open("w", newline="") as handle:
                fields = ["host_time_s"] + [
                    f"ToolVectorActual[{i}]" for i in range(1, 4)
                ]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for t, y in [(1.15, -400), (1.45, -388), (4.15, 397),
                             (4.6, 400)]:
                    writer.writerow({
                        "host_time_s": t, "ToolVectorActual[1]": -600,
                        "ToolVectorActual[2]": y,
                        "ToolVectorActual[3]": 250,
                    })
            metrics = analyze_trial(root)
            self.assertAlmostEqual(metrics["motion_duration_s"], 3.8)
            self.assertAlmostEqual(
                metrics["command_stream_first_to_last_s"], 2.93
            )
            self.assertAlmostEqual(
                metrics["post_stream_idle_wait_s"], 0.74
            )
            self.assertAlmostEqual(
                metrics["tcp_travel_1pct_99pct_s"], 2.70
            )

    def test_partial_recording_does_not_count_as_failed_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "trial_summary.csv"
            result = aggregate([
                {"status": "completed", "tcp_speed_max": 90},
                {"status": "partial", "tcp_speed_max": 95},
                {"status": "failed", "tcp_speed_max": None},
            ], target)
            self.assertEqual(result["trials"], 3)
            self.assertEqual(result["completed"], 1)
            self.assertEqual(result["partial"], 1)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["metrics"]["tcp_speed_max"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
