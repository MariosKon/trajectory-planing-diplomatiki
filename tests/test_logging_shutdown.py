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
