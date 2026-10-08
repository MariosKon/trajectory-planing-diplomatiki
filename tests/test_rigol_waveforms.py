"""Offline tests for Rigol acquisition arithmetic and calibration."""
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import numpy as np
from loggers.rigol_logger import RigolScopeLogger


class RigolTests(unittest.TestCase):
    def make_logger(self, root, **kw):
        logger = RigolScopeLogger("FAKE", root, max_output_points=3, **kw)
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
