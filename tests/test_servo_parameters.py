import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.config import Config
from experiments.helpers import cases_for
from experiments.servo_parameter_study import validate_servo_csv


def make_csv(folder, mode, samples=50):
    path = Path(folder) / "trajectory.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", "x1", "x2", "x3", "x4", "x5", "x6"])
        for index in range(samples):
            writer.writerow([mode, index / (samples - 1) * 10, 0, 0, 0, 0, 0])
    return path


class ServoParameterStudyTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(rigol_resource=None)

    def test_nine_servoj_cases_share_identical_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoJ")
            cases = cases_for("servoj_params", self.config, str(path))
            self.assertEqual(len(cases), 9)
            self.assertEqual([c["aheadtime"] for c in cases], [20] * 3 + [50] * 3 + [80] * 3)
            self.assertEqual([c["gain"] for c in cases], [300, 500, 800] * 3)
            self.assertEqual(len({c["csv_sha256"] for c in cases}), 1)
            self.assertEqual({c["servo_mode"] for c in cases}, {"ServoJ"})

    def test_nine_servop_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP")
            cases = cases_for("servop_params", self.config, str(path))
            self.assertEqual(len(cases), 9)
            self.assertEqual({c["servo_mode"] for c in cases}, {"ServoP"})
            self.assertEqual(cases[0]["servo_time_s"], 0.03)

    def test_wrong_mode_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP")
            with self.assertRaisesRegex(ValueError, "expected ServoJ"):
                cases_for("servoj_params", self.config, str(path))

    def test_missing_csv_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires --csv"):
            cases_for("servoj_params", self.config)

    def test_nan_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP")
            text = path.read_text()
            path.write_text(text.replace(",0,0,0,0,0", ",nan,0,0,0,0", 1))
            with self.assertRaisesRegex(ValueError, "invalid coordinates"):
                validate_servo_csv(path, "ServoP")

    def test_short_scope_window_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP", samples=200)
            cfg = Config(rigol_resource="FAKE", rigol_horizontal_scale_s_per_div=0.5)
            with self.assertRaisesRegex(ValueError, "Rigol window"):
                cases_for("servop_params", cfg, str(path))

    def test_servo_commands_receive_case_parameters(self):
        from core.runner import execute_motion
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoJ", samples=5)
            case = cases_for("servoj_params", self.config, str(path))[2]
            robot = MagicMock()
            manager = MagicMock()
            manager.robot.t0 = 0.0
            from types import ModuleType
            import sys
            fake_sdk = ModuleType("dobot_sdk")
            fake_sdk.CoordinateType = MagicMock()
            original = sys.modules.get("dobot_sdk")
            sys.modules["dobot_sdk"] = fake_sdk
            try:
                with patch("core.runner.time.sleep"), patch("core.runner.wait_for_motion"), patch("core.runner.check_response"):
                    result = execute_motion(robot, self.config, case, manager, Path(tmp))
            finally:
                if original is None:
                    sys.modules.pop("dobot_sdk", None)
                else:
                    sys.modules["dobot_sdk"] = original
            self.assertEqual(robot.motion.ServoJ.call_count, 5)
            for call in robot.motion.ServoJ.call_args_list:
                self.assertEqual(call.args[1:], (0.03, 20.0, 800.0))
            self.assertEqual(result["command_count"], 5)
            self.assertEqual(result["gain"], 800.0)
            with (Path(tmp) / "commands.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[0]["gain"], "800.0")

    def test_servop_commands_receive_case_parameters(self):
        from core.runner import execute_motion
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP", samples=5)
            case = cases_for("servop_params", self.config, str(path))[6]
            robot = MagicMock()
            manager = MagicMock()
            manager.robot.t0 = 0.0
            from types import ModuleType
            import sys
            sdk = ModuleType("dobot_sdk")
            sdk.CoordinateType = MagicMock()
            old = sys.modules.get("dobot_sdk")
            sys.modules["dobot_sdk"] = sdk
            try:
                with patch("core.runner.time.sleep"), patch("core.runner.wait_for_motion"), patch("core.runner.check_response"):
                    result = execute_motion(robot, self.config, case, manager, Path(tmp))
            finally:
                if old is None:
                    sys.modules.pop("dobot_sdk", None)
                else:
                    sys.modules["dobot_sdk"] = old
            self.assertEqual(robot.motion.ServoP.call_count, 5)
            for call in robot.motion.ServoP.call_args_list:
                self.assertEqual(call.args[1:], (0.03, 80.0, 300.0))
            self.assertEqual(result["aheadtime"], 80.0)

    def test_changed_csv_is_rejected_before_command(self):
        from core.runner import execute_motion
        with tempfile.TemporaryDirectory() as tmp:
            path = make_csv(tmp, "ServoP")
            case = cases_for("servop_params", self.config, str(path))[0]
            path.write_text(path.read_text() + "ServoP,11,0,0,0,0,0\n")
            robot = MagicMock()
            from types import ModuleType
            import sys
            fake_sdk = ModuleType("dobot_sdk")
            fake_sdk.CoordinateType = MagicMock()
            original = sys.modules.get("dobot_sdk")
            sys.modules["dobot_sdk"] = fake_sdk
            try:
                with self.assertRaisesRegex(RuntimeError, "changed"):
                    execute_motion(robot, self.config, case, MagicMock(), Path(tmp))
            finally:
                if original is None:
                    sys.modules.pop("dobot_sdk", None)
                else:
                    sys.modules["dobot_sdk"] = original
            robot.motion.ServoP.assert_not_called()


if __name__ == "__main__":
    unittest.main()
