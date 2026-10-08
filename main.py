import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SDK = ROOT/"TCP-IP-Python-V4"
if SDK.exists():
    sys.path.insert(0, str(SDK))

from core.config import Config
from core.runner import batch
from experiments.helpers import cases_for

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment", required=True,
        choices=[
            "movel","movej","cubic","quintic","trapezoidal",
            "double_s","csv_servo","ruckig","payload"
        ],
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--config", default="config/common.json")
    parser.add_argument(
        "--execute", action="store_true",
        help="Send real commands to the robot. Without this flag, dry-run."
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("Repetitions must be >= 1")
    cfg = Config.load(ROOT/args.config)
    cases = cases_for(args.experiment, cfg, args.csv)
    if args.execute:
        print("WARNING: REAL ROBOT MOTION ENABLED")
    else:
        print("Dry run: no robot motion will be commanded")
    result = batch(
        cfg, args.experiment, cases,
        args.repetitions, execute=args.execute
    )
    print("Results:", result)

if __name__ == "__main__":
    main()
