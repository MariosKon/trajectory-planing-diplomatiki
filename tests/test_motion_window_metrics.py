import csv
import json
import tempfile
import unittest
from pathlib import Path

from core.analysis import analyze_trial


class MotionWindowMetricTests(unittest.TestCase):
    def test_tracking_error_excludes_preparation_and_download_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (folder / "events.csv").open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["host_time_s", "event"])
                writer.writeheader()
                writer.writerows([
                    {"host_time_s": 2, "event": "MOTION_START"},
                    {"host_time_s": 4, "event": "MOTION_END"},
                ])
            fields = ["host_time_s"] + [
                f"{prefix}[{i}]"
                for prefix in ("QTarget", "QActual", "ToolVectorTarget",
                               "ToolVectorActual", "QDActual", "TCPSpeedActual")
                for i in range(1, 7)
            ]
            with (folder / "feedback.csv").open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for t, actual in [(1, 100), (2.5, 1), (3.5, 1), (5, 200)]:
                    row = {"host_time_s": t}
                    for i in range(1, 7):
                        row[f"QTarget[{i}]"] = 0
                        row[f"QActual[{i}]"] = actual if i == 1 else 0
                        row[f"ToolVectorTarget[{i}]"] = 0
                        row[f"ToolVectorActual[{i}]"] = actual if i == 1 else 0
                        row[f"QDActual[{i}]"] = 1 if t < 4 else 999
                        row[f"TCPSpeedActual[{i}]"] = 1 if t < 4 else 999
                    writer.writerow(row)
            result = analyze_trial(folder)
            self.assertEqual(result["robot_samples"], 4)
            self.assertEqual(result["robot_motion_samples"], 2)
            self.assertEqual(result["motion_duration_s"], 2)
            self.assertEqual(result["joint_tracking_rmse"], 1)
            self.assertEqual(result["tcp_position_tracking_rmse_mm"], 1)
            self.assertTrue(result["robot_motion_window_valid"])

    def test_missing_motion_events_do_not_produce_tracking_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (folder / "feedback.csv").open("w", newline="") as fh:
                fh.write("host_time_s\n1\n")
            result = analyze_trial(folder)
            self.assertFalse(result["robot_motion_window_valid"])
            self.assertIsNone(result["joint_tracking_rmse"])
            self.assertIsNone(result["motion_duration_s"])


if __name__ == "__main__":
    unittest.main()
