"""Offline tests for Rigol acquisition arithmetic and calibration."""
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import numpy as np
from loggers.rigol_logger import RigolScopeLogger


class RigolTests(unittest.TestCase):
    def make_logger(self, root, **kw):
        max_output_points = kw.pop("max_output_points", 3)
        logger = RigolScopeLogger("FAKE", root, max_output_points=max_output_points, **kw)
        logger.metadata["channels"] = {
            "CHAN1": {"unit": "V"},
            "CHAN2": {"unit": "V"},
        }
        return logger

    def test_downsample_preserves_power_averaged_before_reduction(self):
        with TemporaryDirectory() as root:
            log = self.make_logger(root)
            t = np.arange(6, dtype=float)
            current = np.array([1., 3., 1., 3., 1., 3.])
            voltage = np.array([3., 1., 3., 1., 3., 1.])
            _, c, v, p = log._downsample(t, current, voltage, current * voltage)
            self.assertTrue(np.allclose(p, [3., 3., 3.]))
            self.assertFalse(np.allclose(p, c * v))

    def test_roll_mode_rejected_before_run(self):
        with TemporaryDirectory() as root:
            logger = self.make_logger(root)
            scope = MagicMock()
            scope.query.side_effect = lambda cmd: "ROLL" if cmd == ":TIM:MODE?" else "1"
            rm = MagicMock()
            rm.open_resource.return_value = scope
            with patch("loggers.rigol_logger.pyvisa") as visa:
                visa.ResourceManager.return_value = rm
                with self.assertRaises(RuntimeError):
                    logger.start()
            self.assertNotIn(":RUN", [x.args[0] for x in scope.write.call_args_list])

    def test_scope_display_current_is_used_when_raw_has_wrong_polarity(self):
        with TemporaryDirectory() as root:
            # Keep all 101 display samples so peak power is not averaged into 3 bins.
            logger = self.make_logger(
                root, horizontal_scale_s_per_div=None, max_output_points=200
            )
            logger.metadata["host_start_perf_s"] = 100.0
            logger.metadata["channels"]["CHAN1"]["unit"] = "AMP"
            logger.scope = MagicMock()
            logger.scope.query.side_effect = lambda cmd: (
                "MAIN" if cmd == ":TIM:MODE?" else "STOP"
                if cmd == ":TRIG:STAT?" else "1"
            )
            t = np.linspace(-1.0, 1.0, 101)
            displayed_current = 0.2 + np.exp(-((t + 0.3) / 0.2) ** 2)
            displayed_voltage = np.full_like(t, 48.0)
            def read_display(channel):
                return (t, displayed_current) if channel == "CHAN1" else (t, displayed_voltage)
            def read_raw(channel):
                return (t, -displayed_current) if channel == "CHAN1" else (t, displayed_voltage)
            logger._download_display_waveform = read_display
            logger._download_waveform = read_raw
            logger._save_channel = lambda *args: None
            logger._capture_screen_image = lambda: None
            logger._confirm_stopped = lambda: None
            with patch("loggers.rigol_logger.time.perf_counter", return_value=102.0):
                result = logger.stop()
            self.assertIsNone(result["error"])
            self.assertEqual(result["power_trace_source"], "NORM_DISPLAY")
            self.assertTrue(result["power_data_valid"])
            self.assertLess(
                logger.metadata["raw_display_comparison"]["CHAN1"]["correlation"], -0.99
            )
            from pathlib import Path
            import csv
            with (Path(root) / "rigol_scope.csv").open(newline="") as fh:
                points = list(csv.DictReader(fh))
            self.assertEqual(len(points), 101)
            self.assertAlmostEqual(max(float(row["power_W"]) for row in points), 57.6, places=5)

    def test_current_without_calibration_is_unverified(self):
        self.assertIsNone(RigolScopeLogger._current_factor("V", None))
        self.assertEqual(RigolScopeLogger._current_factor("A", None), 1.0)
        self.assertEqual(RigolScopeLogger._current_factor("V", 2.5), 2.5)

    def test_configured_timebase_before_run(self):
        with TemporaryDirectory() as root:
            logger = self.make_logger(root, horizontal_scale_s_per_div=5.0)
            scope = MagicMock()
            scope.query.side_effect = lambda command: {
                "*IDN?": "RIGOL,MOCK,123,1",
                "*OPC?": "1",
                ":TIM:MODE?": "MAIN",
                ":ACQ:MDEP?": "60000",
            }.get(command, "1")
            rm = MagicMock()
            rm.open_resource.return_value = scope
            with patch("loggers.rigol_logger.pyvisa") as visa:
                visa.ResourceManager.return_value = rm
                logger.start()
            cmds = [x.args[0] for x in scope.write.call_args_list]
            self.assertLess(cmds.index(":TIM:MODE MAIN"), cmds.index(":RUN"))
            self.assertLess(cmds.index(":TIM:SCAL 5.0"), cmds.index(":RUN"))
            self.assertLess(cmds.index(":ACQ:MDEP 60000"), cmds.index(":RUN"))
            logger.close()


if __name__ == "__main__":
    unittest.main()
