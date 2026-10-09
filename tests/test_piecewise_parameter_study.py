"""Nine-case V/A/J sweep tests: offline only, no hardware connection."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
from core.config import Config
from core.runner import run_trial
from experiments.helpers import cases_for
from experiments.csv_servo.points import load_points
from experiments.piecewise_parameter_study import MATRIX_PATH, load_matrix, parameters, verify
from experiments.polynomial_fixed_time import REFERENCE_START, REFERENCE_END


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Config()
        self.matrix=load_matrix()

    def test_design_and_case_order(self):
        self.assertEqual(len(self.matrix),9)
        for a,b in ((0,1),(0,2),(1,2)):
            self.assertEqual(len(set((x[a],x[b]) for x in self.matrix)),9)
        for profile in ("trapezoidal","double_s","ruckig"):
            cases=cases_for(profile,self.cfg)
            self.assertEqual(len(cases),9)
            for i,(c,(v,a,j)) in enumerate(zip(cases,self.matrix),1):
                with self.subTest(profile=profile,index=i):
                    self.assertEqual(c["name"],f"{profile}_sweep_{i:02d}")
                    self.assertEqual(c["velocity_limit_mm_s"],v)
                    self.assertEqual(c["acceleration_limit_mm_s2"],a)
                    self.assertEqual(c.get("jerk_limit_mm_s3"),
                                     None if profile=="trapezoidal" else j)
                    self.assertEqual(c["global_speed_factor"],100)
                    self.assertEqual(c["exceeds_movel_fast_speed"],v>470.5)
                    self.assertEqual(c["matlab_matrix_path"],str(MATRIX_PATH))
                    self.assertEqual(c["matlab_matrix_sha256"],
                                     hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest())

    def test_editable_matlab_manifest_validation(self):
        with TemporaryDirectory() as tmp:
            manifest=Path(tmp)/"case_matrix.csv"
            original=MATRIX_PATH.read_text(encoding="utf-8")
            self.assertEqual(load_matrix(MATRIX_PATH), self.matrix)
            manifest.write_text(original.replace("case,velocity_mm_s",
                                                 "index,velocity_mm_s",1),
                                encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"header"):
                load_matrix(manifest)
            manifest.write_text(original.replace("1,300,500,6000",
                                                 "1,NaN,500,6000",1),
                                encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Invalid L9"):
                load_matrix(manifest)
            manifest.write_text(original.replace("9,460,1100,10000",
                                                 "9,300,500,6000",1),
                                encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"pairs|levels"):
                load_matrix(manifest)

    def test_all_18_analytic_csvs(self):
        for profile in ("trapezoidal","double_s"):
            for i,(case,(v,a,j)) in enumerate(zip(cases_for(profile,self.cfg),self.matrix),1):
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
        for c,(v,a,j) in zip(cases_for("ruckig",self.cfg),self.matrix):
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

    def test_matlab_csv_reader_preserves_keyword_header(self):
        generator=(Path(__file__).resolve().parents[1]/
                   "experiments"/"piecewise_sweep"/"generate_piecewise_sweep.m")
        source=generator.read_text(encoding="utf-8")
        # MATLAB's default readtable renames 'case' (reserved keyword).
        self.assertIn(
            "savedMatrix=readtable(matrixPath,'VariableNamingRule','preserve');",
            source)
        self.assertIn("savedMatrix{:,1}", source)
        self.assertNotIn("savedMatrix.case", source)
        self.assertIn(
            "imported=readtable(outputPath,'VariableNamingRule','preserve');",
            source)

    def test_study_rigol_configuration(self):
        root=Path(__file__).resolve().parents[1]
        cfg=Config.load(root/"config"/"piecewise_sweep_rigol_1s.json")
        self.assertEqual(cfg.rigol_horizontal_scale_s_per_div,1.0)
        self.assertEqual(cfg.servop_aheadtime,20.0)
        self.assertEqual(cfg.servop_gain,300.0)
        self.assertEqual(cfg.start,list(REFERENCE_START))
        self.assertEqual(cfg.target,list(REFERENCE_END))

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
                verify("double_s",path,*self.matrix[0])

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
