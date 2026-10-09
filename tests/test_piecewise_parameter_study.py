"""Nine-case V/A/J sweep tests: offline only, no hardware connection."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from core.config import Config
from core.runner import run_trial
from experiments.helpers import cases_for
from experiments.csv_servo.points import load_points
from experiments.piecewise_parameter_study import MATRIX, parameters, verify
from experiments.polynomial_fixed_time import REFERENCE_START, REFERENCE_END


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Config()

    def test_design_and_case_order(self):
        self.assertEqual(len(MATRIX),9)
        for a,b in ((0,1),(0,2),(1,2)):
            self.assertEqual(len(set((x[a],x[b]) for x in MATRIX)),9)
        for profile in ("trapezoidal","double_s","ruckig"):
            cases=cases_for(profile,self.cfg)
            self.assertEqual(len(cases),9)
            for i,(c,(v,a,j)) in enumerate(zip(cases,MATRIX),1):
                with self.subTest(profile=profile,index=i):
                    self.assertEqual(c["name"],f"{profile}_sweep_{i:02d}")
                    self.assertEqual(c["velocity_limit_mm_s"],v)
                    self.assertEqual(c["acceleration_limit_mm_s2"],a)
                    self.assertEqual(c.get("jerk_limit_mm_s3"),
                                     None if profile=="trapezoidal" else j)
                    self.assertEqual(c["global_speed_factor"],100)
                    self.assertFalse(c["exceeds_movel_fast_speed"])

    def test_all_18_analytic_csvs(self):
        for profile in ("trapezoidal","double_s"):
            for i,(case,(v,a,j)) in enumerate(zip(cases_for(profile,self.cfg),MATRIX),1):
                with self.subTest(profile=profile,index=i):
                    jerk=j if profile=="double_s" else None
                    p=parameters(profile,v,a,jerk)
                    points=load_points(case["csv_path"],"ServoP")
                    self.assertEqual(len(points),p["intervals"]+1)
                    self.assertEqual(points[0].values,list(REFERENCE_START))
                    self.assertEqual(points[-1].values,list(REFERENCE_END))
                    self.assertAlmostEqual(case["duration_s"],(len(points)-1)*.03)
                    self.assertLessEqual(p["peak_v"],v+1e-9)
                    self.assertLessEqual(p["peak_a"],a+1e-9)
                    self.assertGreater(p["cruise_s"],0)
                    if jerk is not None:
                        self.assertLessEqual(p["peak_j"],j+1e-9)
                    verify(profile,case["csv_path"],v,a,jerk)

    def test_ruckig_limits_and_minimum_duration(self):
        for c,(v,a,j) in zip(cases_for("ruckig",self.cfg),MATRIX):
            self.assertEqual(c["mode"],"ruckig")
            self.assertIsNone(c["minimum_duration_s"])
            self.assertEqual(c["max_velocity"],[v]*6)
            self.assertEqual(c["max_acceleration"],[a]*6)
            self.assertEqual(c["max_jerk"],[j]*6)

    def test_matched_references_are_still_available(self):
        for profile in ("trapezoidal","double_s","ruckig"):
            cases=cases_for(profile+"_matched",self.cfg)
            self.assertEqual(len(cases),3)
            self.assertEqual([c["duration_s"] for c in cases],[3.93,2.79,2.31])

    def test_preflight_and_corruption(self):
        with self.assertRaisesRegex(ValueError,"servo_time_s"):
            cases_for("trapezoidal",Config(servo_time_s=.01))
        c=dict(cases_for("trapezoidal",self.cfg)[0])
        c["csv_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"changed after case"):
            run_trial(self.cfg,c,Path("unused"))
        original=Path(cases_for("double_s",self.cfg)[0]["csv_path"])
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.csv"
            lines=original.read_text(encoding="utf-8").splitlines()
            cells=lines[8].split(",")
            cells[2]=str(float(cells[2])+1.0)
            lines[8]=",".join(cells)
            path.write_text("\n".join(lines)+"\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Unexpected pose"):
                verify("double_s",path,*MATRIX[0])

    def test_ruckig_online_planner_offline_if_available(self):
        try:
            from experiments.ruckig.planner import OnlineRuckigPlanner
        except ImportError:
            self.skipTest("Ruckig not installed")
        for case in cases_for("ruckig",self.cfg):
            with self.subTest(case=case["name"]):
                planner=OnlineRuckigPlanner(
                    case["start"],case["target"],.03,case["max_velocity"],
                    case["max_acceleration"],case["max_jerk"])
                for _ in range(250):
                    step=planner.update()
                    if step.finished:
                        break
                self.assertTrue(step.finished)
                self.assertGreater(step.trajectory_duration_s,0)
                for actual,want in zip(step.position,REFERENCE_END):
                    self.assertAlmostEqual(actual,want,places=5)


if __name__=="__main__":
    unittest.main()
