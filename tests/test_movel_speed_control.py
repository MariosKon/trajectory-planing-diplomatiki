import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import Config
from core.robot import slow_move
from core.runner import batch, configure_motion_speed


class RecordingRobotControl:
    def __init__(self):
        self.speed_factors = []

    def SpeedFactor(self, factor):
        self.speed_factors.append(factor)
        return f"SpeedFactor({factor})"


class ConfigureMotionSpeedTests(unittest.TestCase):
    def test_movel_case_keeps_global_speed_at_100(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {"mode": "movel", "speed": 75})

        self.assertEqual(control.speed_factors, [100])

    def test_non_movel_cases_do_not_change_global_speed(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {"mode": "ruckig", "speed": 50})

        self.assertEqual(control.speed_factors, [])

    def test_default_acquisition_delays_are_disabled(self):
        cfg = Config()

        self.assertEqual(cfg.settle_s, 0.0)
        self.assertEqual(cfg.camera_pre_delay_s, 0.0)
        self.assertEqual(cfg.camera_stop_delay_s, 0.0)
        self.assertEqual(cfg.rigol_pre_delay_s, 0.0)
        self.assertEqual(cfg.rigol_stop_delay_s, 0.0)

    def test_slow_move_does_not_add_a_fixed_settle_delay(self):
        robot = type("Robot", (), {
            "motion": type("Motion", (), {
                "MovJ": lambda self, target, coordinate_type, a, v: "ok"
            })(),
        })()
        cfg = Config(settle_s=3.0)

        with patch("core.robot.wait_for_motion"):
            with patch("core.robot.time.sleep") as sleep:
                slow_move(robot, [0] * 6, "joint", cfg)

        sleep.assert_not_called()

    def test_batch_robot_lifecycle_is_shared_across_trials(self):
        class RecordingControl:
            def __init__(self):
                self.request_control_count = 0
                self.clear_error_count = 0
                self.enable_count = 0
                self.disable_count = 0

            def RequestControl(self):
                self.request_control_count += 1

            def ClearError(self):
                self.clear_error_count += 1

            def EnableRobot(self):
                self.enable_count += 1

            def DisableRobot(self):
                self.disable_count += 1

        class RecordingRobot:
            def __init__(self):
                self.connect_count = 0
                self.disconnect_count = 0
                self.robot_control = RecordingControl()

            def Connect(self):
                self.connect_count += 1

            def Disconnect(self):
                self.disconnect_count += 1

        robot = RecordingRobot()
        dobote_sdk = types.ModuleType("dobot_sdk")
        dobote_sdk.DobotRobot = lambda _ip: robot
        previous_sdk = sys.modules.get("dobot_sdk")
        sys.modules["dobot_sdk"] = dobote_sdk
        try:
            with patch("core.runner.run_trial") as run_trial:
                run_trial.return_value = {"status": "completed"}
                with patch("core.runner.analyze_trial", return_value={}):
                    with patch("core.runner.aggregate"):
                        result = batch(
                            Config(robot_ip="test"),
                            "test",
                            [{"mode": "movel", "speed": 50}],
                            repetitions=2,
                            execute=True,
                        )

            self.assertEqual(robot.connect_count, 1)
            self.assertEqual(robot.disconnect_count, 1)
            self.assertEqual(
                robot.robot_control.enable_count,
                1,
            )
            self.assertEqual(
                robot.robot_control.disable_count,
                1,
            )
            self.assertEqual(run_trial.call_count, 2)
            self.assertTrue(all(
                call.kwargs["robot"] is robot
                for call in run_trial.call_args_list
            ))
            self.assertTrue(result.exists())
        finally:
            if previous_sdk is None:
                sys.modules.pop("dobot_sdk", None)
            else:
                sys.modules["dobot_sdk"] = previous_sdk


if __name__ == "__main__":
    unittest.main()
