import unittest
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory

from core.config import Config
from loggers.manager import LoggingManager


class LoggingShutdownOrderTests(unittest.TestCase):
    def test_rigol_download_finishes_before_camera_stops(self):
        with TemporaryDirectory() as tmp:
            cfg = Config(
                camera_url="rtsp://example.invalid/stream",
                rigol_resource="FAKE_VISA",
                camera_stop_delay_s=2.0,
                rigol_stop_delay_s=0.0,
                robot_logger_post_delay_s=0.0,
            )
            with patch("loggers.manager.RTSPVideoRecorder"), patch(
                "loggers.manager.RigolScopeLogger"
            ):
                manager = LoggingManager(cfg, tmp)
            order = []
            manager.robot = MagicMock()
            manager.robot.stop.side_effect = lambda: order.append("robot") or {}
            manager.robot_started = True
            manager.rigol.stop.side_effect = lambda: order.append("rigol") or {
                "error": None,
            }
            manager.rigol_started = True
            manager.camera.stop.side_effect = lambda: order.append("camera") or {
                "error": None,
            }
            manager.camera_started = True
            with patch("loggers.manager.time.sleep") as sleep:
                result = manager.stop()
            self.assertEqual(order, ["robot", "rigol", "camera"])
            sleep.assert_called_once_with(2.0)
            self.assertIn("camera", result)

    def test_robot_feedback_starts_after_scope_and_before_motion(self):
        with TemporaryDirectory() as tmp:
            cfg = Config(
                camera_url=None, rigol_resource="FAKE_VISA",
                rigol_pre_delay_s=1.5, robot_logger_pre_delay_s=0.5,
            )
            with patch("loggers.manager.RigolScopeLogger"):
                manager = LoggingManager(cfg, tmp)
            timeline = []
            manager.robot = MagicMock()
            manager.robot.first_packet.wait.return_value = True
            manager.robot.start.side_effect = lambda: timeline.append("robot")
            manager.robot.t0 = 100.0
            manager.rigol.start.side_effect = lambda *_: timeline.append("rigol")
            manager.rigol.metadata = {"host_start_perf_s": 100.0}
            def fake_sleep(duration):
                timeline.append(("sleep", duration))
            with patch("loggers.manager.time.perf_counter",
                       side_effect=[100.2, 101.0, 101.0, 101.5, 101.5]):
                with patch("loggers.manager.time.sleep", side_effect=fake_sleep):
                    manager.start()
            self.assertEqual(timeline[0], "rigol")
            self.assertEqual(timeline[1][0], "sleep")
            self.assertAlmostEqual(timeline[1][1], 0.8)
            self.assertEqual(timeline[2], "robot")
            self.assertAlmostEqual(timeline[3][1], 0.5)
            self.assertTrue(manager.robot_started)

    def test_robot_feedback_postroll_precedes_rigol_download(self):
        with TemporaryDirectory() as tmp:
            cfg = Config(
                rigol_resource="FAKE_VISA", camera_url=None,
                robot_logger_post_delay_s=1.0, rigol_stop_delay_s=0,
            )
            with patch("loggers.manager.RigolScopeLogger"):
                manager = LoggingManager(cfg, tmp)
            order = []
            manager.robot = MagicMock()
            manager.robot.stop.side_effect = lambda: order.append("robot")
            manager.robot_started = True
            manager.rigol.stop.side_effect = lambda: order.append("rigol")
            manager.rigol_started = True
            with patch("loggers.manager.time.sleep") as sleep:
                manager.stop()
            sleep.assert_called_once_with(1.0)
            self.assertEqual(order, ["robot", "rigol"])

    def test_camera_stops_even_when_rigol_raises(self):
        with TemporaryDirectory() as tmp:
            cfg = Config(
                camera_url="rtsp://example.invalid/stream",
                rigol_resource="FAKE_VISA",
                camera_stop_delay_s=0.0,
                rigol_stop_delay_s=0.0,
            )
            with patch("loggers.manager.RTSPVideoRecorder"), patch(
                "loggers.manager.RigolScopeLogger"
            ):
                manager = LoggingManager(cfg, tmp)
            manager.rigol.stop.side_effect = RuntimeError("VISA error")
            manager.rigol_started = True
            manager.camera.stop.return_value = {"error": None}
            manager.camera_started = True
            result = manager.stop()
            self.assertIn("VISA error", result["rigol_error"])
            manager.camera.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
