import csv
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import Config
from core.runner import execute_motion


class ServoJDispatchTests(unittest.TestCase):
    def test_joint_coordinates_and_custom_parameters_reach_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "points.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["mode"] + [f"j{i}" for i in range(1,7)])
                writer.writerow(["ServoJ",26,53.8,55.2,71,116,-180.2])
                writer.writerow(["ServoJ",-50,54,54.9,71.4,40,-180.2])

            sent = []
            class Motion:
                def ServoJ(self, values, t, aheadtime, gain):
                    sent.append((values, t, aheadtime, gain))
                    return "0,{},ServoJ();"

            robot = types.SimpleNamespace(motion=Motion())
            manager = types.SimpleNamespace(
                robot=types.SimpleNamespace(
                    t0=time.perf_counter(),
                    set_commanded_point=lambda x: None),
                event=lambda *args: None)
            sdk = types.ModuleType("dobot_sdk")
            sdk.CoordinateType = types.SimpleNamespace(JOINT=0, CARTESIAN=1)
            with patch.dict(sys.modules, {"dobot_sdk": sdk}), patch("core.runner.wait_for_motion"):
                result = execute_motion(robot, Config(servo_time_s=0.004),
                    {"mode":"csv","csv_path":str(path),"aheadtime":80,"gain":700},
                    manager, folder)
            self.assertEqual(result["command_count"],2)
            self.assertEqual(sent[0][0],[26,53.8,55.2,71,116,-180.2])
            self.assertEqual(sent[1][0],[-50,54,54.9,71.4,40,-180.2])
            self.assertTrue(all(x[1:] == (0.004,80.0,700.0) for x in sent))
            with (folder/"commands.csv").open(encoding="utf-8",newline="") as stream:
                commands = list(csv.DictReader(stream))
            self.assertTrue(all(x["mode"]=="ServoJ" for x in commands))


if __name__=="__main__":
    unittest.main()
