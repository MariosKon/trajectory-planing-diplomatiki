"""Regenerate all 18 sweep CSVs: python -m experiments.piecewise_sweep.generate"""
import csv
from pathlib import Path
from experiments.piecewise_parameter_study import MATRIX,expected_rows,parameters,verify

ROOT=Path(__file__).resolve().parents[1]
def main():
    for profile in ("trapezoidal","double_s"):
        for i,(V,A,J) in enumerate(MATRIX,1):
            jerk=J if profile=="double_s" else None
            rows=expected_rows(profile,V,A,jerk)
            path=ROOT/profile/f"points_{profile}_sweep_{i:02d}.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.writer(handle,lineterminator="\n")
                writer.writerow(("mode","x1","x2","x3","x4","x5","x6"))
                for row in rows:
                    writer.writerow(["ServoP"]+[f"{x:.12f}" for x in row])
            verify(profile,path,V,A,jerk)
            print(f"{profile} {i}: {len(rows)} samples, T={parameters(profile,V,A,jerk)['duration_s']:.2f}s, PASS")
if __name__=="__main__":
    main()
