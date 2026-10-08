import csv
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import Config
from core.runner import configure_motion_speed, execute_motion


class ServoPParameterDispatchTests(unittest.TestCase):
    def test_per_case_gain_and_aheadtime_are_passed_to_sdk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "minimal.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["mode"] + [f"x{i}" for i in range(1,7)])
                writer.writerow(["ServoP", -600, -400, 250, -90, 0, 90])
                writer.writerow(["ServoP", -600, 400, 250, -90, 0, 90])

            sent = []
            class Motion:
                def ServoP(self, values, period, aheadtime, gain):
                    sent.append((values, period, aheadtime, gain))
                    return "0,{},ServoP();"

            control = types.SimpleNamespace(SpeedFactor=lambda x: "0,{},SpeedFactor();")
            robot = types.SimpleNamespace(motion=Motion(), robot_control=control)
            manager = types.SimpleNamespace(
                robot=types.SimpleNamespace(t0=time.perf_counter(), set_commanded_point=lambda x: None),
                event=lambda *args: None,
            )
            sdk = types.ModuleType("dobot_sdk")
            sdk.CoordinateType = types.SimpleNamespace(CARTESIAN=1, JOINT=0)
            with patch.dict(sys.modules, {"dobot_sdk": sdk}):
                with patch("core.runner.wait_for_motion"):
                    result = execute_motion(
                        robot, Config(servo_time_s=0.004),
                        {"mode": "csv", "csv_path": str(path), "aheadtime": 80, "gain": 700},
                        manager, Path(folder),
                    )

            self.assertEqual(result["command_count"], 2)
            self.assertEqual(len(sent), 2)
            self.assertTrue(all((x[1], x[2], x[3]) == (0.004, 80, 700) for x in sent))
            with (Path(folder) / "commands.csv").open(newline="", encoding="utf-8") as handle:
                commands = list(csv.DictReader(handle))
            self.assertEqual(commands[0]["aheadtime"], "80.0")
            self.assertEqual(commands[0]["gain"], "700.0")

    def test_explicit_global_speed_factor(self):
        calls = []
        robot = types.SimpleNamespace(
            robot_control=types.SimpleNamespace(
                SpeedFactor=lambda factor: calls.append(factor) or "0,{},SpeedFactor();"
            )
        )
        configure_motion_speed(robot, {"mode": "csv", "global_speed_factor": 100})
        self.assertEqual(calls, [100])


if __name__ == "__main__":
    unittest.main()
