"""Offline regressions for the three-condition fastest-tested payload suite."""
import contextlib
import io
import sys
import unittest
from unittest.mock import patch

import main
from core.config import Config
from experiments.helpers import cases_for
from experiments.payload.experiment import FASTEST_TESTED_CASES, PHASES


class PayloadCasesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = Config()
        cls.baseline = cases_for(
            "payload", cls.config, payload_phase="baseline",
            physical_payload_mass_kg=0.5,
        )
        cls.full = cases_for(
            "payload", cls.config, payload_phase="full",
            physical_payload_mass_kg=0.9,
        )
        cls.empty = cases_for(
            "payload", cls.config, payload_phase="empty",
            physical_payload_mass_kg=0.2,
        )

    def test_exactly_six_fastest_tested_cases_in_order(self):
        self.assertEqual(len(self.baseline), 6)
        self.assertEqual(
            [(case["trajectory_profile"], case["source_case_index"])
             for case in self.baseline],
            list(FASTEST_TESTED_CASES),
        )
        self.assertEqual(
            [case["mode"] for case in self.baseline],
            ["movel", "csv", "csv", "csv", "ruckig", "csv"],
        )

    def test_move_l_and_csv_durations(self):
        move_l, cubic, quintic, double_s, ruckig, trapezoidal = self.baseline
        self.assertEqual((move_l["speed"], move_l["acceleration"]), (100, 100))
        self.assertAlmostEqual(cubic["duration_s"], 2.31)
        self.assertAlmostEqual(quintic["duration_s"], 2.31)
        self.assertAlmostEqual(double_s["duration_s"], 2.28)
        self.assertAlmostEqual(trapezoidal["duration_s"], 2.16)
        for case in (double_s, ruckig, trapezoidal):
            self.assertEqual(case["velocity_limit_mm_s"], 460)
            self.assertEqual(case["acceleration_limit_mm_s2"], 1100)
        self.assertEqual(double_s["jerk_limit_mm_s3"], 10000)
        self.assertEqual(ruckig["jerk_limit_mm_s3"], 10000)

    def test_source_cases_remain_identical_across_phases(self):
        self.assertEqual(PHASES, ("baseline", "full", "empty"))
        for idx, ((profile, original_idx), before, full, empty) in enumerate(
            zip(FASTEST_TESTED_CASES, self.baseline, self.full, self.empty), 1
        ):
            original = cases_for(profile, self.config)[original_idx - 1]
            self.assertEqual(
                {key: before[key] for key in original},
                original,
                f"Payload case {idx} changed original motion arguments",
            )
            for candidate in (full, empty):
                for key in before:
                    if key not in ("payload_phase", "physical_payload_mass_kg"):
                        self.assertEqual(before[key], candidate[key])
                self.assertNotIn("payload_kg", candidate)
            self.assertEqual(before["payload_phase"], "baseline")
            self.assertEqual(full["payload_phase"], "full")
            self.assertEqual(empty["payload_phase"], "empty")
            self.assertEqual(before["matrix_case_index"], idx)
            self.assertEqual(before["matrix_case_count"], 6)
            self.assertEqual(before["physical_payload_mass_kg"], 0.5)
            self.assertEqual(full["physical_payload_mass_kg"], 0.9)
            self.assertEqual(empty["physical_payload_mass_kg"], 0.2)
            self.assertNotIn("payload_kg", before)

    def test_reject_invalid_phase_and_mass_or_csv(self):
        for phase in ("other", "", None):
            with self.subTest(phase=phase):
                with self.assertRaises(ValueError):
                    cases_for("payload", self.config, payload_phase=phase)
        for mass in (-1, float("nan"), float("inf")):
            with self.subTest(mass=mass):
                with self.assertRaises(ValueError):
                    cases_for("payload", self.config,
                              physical_payload_mass_kg=mass)
        with self.assertRaises(ValueError):
            cases_for("payload", self.config, "custom.csv")


class PayloadCLITests(unittest.TestCase):
    def _invoke(self, *args):
        stream = io.StringIO()
        with patch.object(sys, "argv", ["main.py", *args]), \
             patch.object(main, "batch", return_value="fake-results") as fake_batch, \
             contextlib.redirect_stdout(stream):
            main.main()
        return fake_batch, stream.getvalue()

    def test_no_motion_baseline_dry_run_is_one_repetition(self):
        mock_batch, output = self._invoke("--experiment", "payload")
        args, kwargs = mock_batch.call_args
        self.assertEqual(args[1], "payload/baseline")
        self.assertEqual(len(args[2]), 6)
        self.assertEqual(args[3], 1)
        self.assertFalse(kwargs["execute"])
        self.assertIn("STOP AFTER BASELINE", output)

    def test_full_phase_is_separate_and_metadata_only(self):
        mock_batch, _ = self._invoke(
            "--experiment", "payload", "--payload-phase", "full",
            "--payload-mass-kg", "0.9", "--execute",
        )
        args, kwargs = mock_batch.call_args
        self.assertEqual(args[1], "payload/full")
        self.assertEqual(args[3], 1)
        self.assertTrue(kwargs["execute"])
        self.assertTrue(all(
            c["physical_payload_mass_kg"] == 0.9 and c["payload_phase"] == "full"
            and "payload_kg" not in c
            for c in args[2]
        ))

    def test_empty_phase_stays_separate(self):
        mock_batch, _ = self._invoke(
            "--experiment", "payload", "--payload-phase", "empty",
            "--payload-mass-kg", "0.2", "--execute",
        )
        args, kwargs = mock_batch.call_args
        self.assertEqual(args[1], "payload/empty")
        self.assertEqual(len(args[2]), 6)
        self.assertEqual(args[3], 1)
        self.assertTrue(kwargs["execute"])
        self.assertTrue(all(c["payload_phase"] == "empty"
                            and c["physical_payload_mass_kg"] == 0.2 for c in args[2]))

    def test_execute_requires_explicit_phase(self):
        with patch.object(sys, "argv", [
                "main.py", "--experiment", "payload", "--execute",
            ]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                main.main()
        self.assertEqual(e.exception.code, 2)

    def test_reject_multiple_payload_repetitions(self):
        with patch.object(sys, "argv", [
                "main.py", "--experiment", "payload", "--repetitions", "2",
            ]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                main.main()
        self.assertEqual(e.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
