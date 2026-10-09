import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.config import Config
from core.robot import slow_move
from core.runner import batch, configure_motion_speed, execute_motion


class RecordingRobotControl:
    def __init__(self):
        self.speed_factors = []

    def SpeedFactor(self, factor):
        self.speed_factors.append(factor)
        return f"SpeedFactor({factor})"


class ConfigureMotionSpeedTests(unittest.TestCase):
    def test_movel_matrix_uses_case_speed_as_global_factor(self):
        for speed in (50, 75, 100):
            with self.subTest(speed=speed):
                control = RecordingRobotControl()
                robot = type("Robot", (), {"robot_control": control})()

                configure_motion_speed(robot, {"mode": "movel", "speed": speed})

                self.assertEqual(control.speed_factors, [speed])

    def test_movej_uses_same_speed_control(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {"mode": "movej", "speed": 75})

        self.assertEqual(control.speed_factors, [75])

    def test_explicit_global_factor_still_overrides_case_speed(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {
            "mode": "movel", "speed": 75, "global_speed_factor": 60,
        })

        self.assertEqual(control.speed_factors, [60])

    def test_explicit_global_factor_for_servo_is_unchanged(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {"mode": "csv", "global_speed_factor": 100})

        self.assertEqual(control.speed_factors, [100])

    def test_movel_local_velocity_is_fixed_at_100(self):
        target = [-600, 400, 250, -90, 0, 90]
        motion = MagicMock()
        motion.MovL.return_value = "0,{},MovL(...)"
        robot = type("Robot", (), {"motion": motion})()
        manager = MagicMock()
        fake_sdk = types.ModuleType("dobot_sdk")
        fake_sdk.CoordinateType = types.SimpleNamespace(
            CARTESIAN="cartesian", JOINT="joint",
        )

        with patch.dict(sys.modules, {"dobot_sdk": fake_sdk}):
            with patch("core.runner.wait_for_motion"):
                result = execute_motion(
                    robot, Config(),
                    {
                        "mode": "movel", "target": target,
                        "speed": 50, "acceleration": 75,
                    },
                    manager, None,
                )

        motion.MovL.assert_called_once_with(
            target, "cartesian", a=75, v=100,
        )
        manager.robot.set_commanded_point.assert_called_once_with(target)
        event = manager.event.call_args.args
        self.assertEqual(event[0], "MOTION_PARAMETERS")
        self.assertIn("global_speed=50", event[1])
        self.assertIn("v=100", event[1])
        self.assertEqual(result["speed_percent"], 50)
        self.assertEqual(result["global_speed_factor"], 50)
        self.assertEqual(result["command_v_percent"], 100)

    def test_non_movel_cases_do_not_change_global_speed(self):
        control = RecordingRobotControl()
        robot = type("Robot", (), {"robot_control": control})()

        configure_motion_speed(robot, {"mode": "ruckig", "speed": 50})

        self.assertEqual(control.speed_factors, [])

    def test_default_acquisition_delays_match_configuration(self):
        cfg = Config()

        self.assertEqual(cfg.settle_s, 3.0)
        self.assertEqual(cfg.camera_pre_delay_s, 2.0)
        self.assertEqual(cfg.camera_stop_delay_s, 2.0)
        self.assertEqual(cfg.rigol_pre_delay_s, 1.5)
        self.assertEqual(cfg.robot_logger_pre_delay_s, 0.5)
        self.assertEqual(cfg.robot_logger_post_delay_s, 1.0)
        self.assertEqual(cfg.rigol_stop_delay_s, 1.0)

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
