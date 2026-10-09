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

def select_cases(cases, case_number):
    """Return the selected 1-based experiment case, or all cases."""
    if case_number is None:
        return cases
    if not 1 <= case_number <= len(cases):
        raise ValueError(
            f"--case must be between 1 and {len(cases)} "
            f"(received {case_number})"
        )
    # Preserve the original matrix number through the entire batch,
    # even though only one case will be executed.
    case = dict(cases[case_number - 1])
    case["matrix_case_index"] = case_number
    case["matrix_case_count"] = len(cases)
    return [case]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment", required=True,
        choices=[
            "movel","movej","cubic","quintic","trapezoidal",
            "double_s","csv_servo","ruckig",
            "trapezoidal_matched","double_s_matched","ruckig_matched","payload","servop_behavior","servoj_behavior","servoP_confirmation"
        ],
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--case", type=int, default=None,
                        help="Run only one 1-based parameter combination (e.g. --case 1)")
    parser.add_argument("--list-cases", action="store_true",
                        help="Print available case numbers and parameters; no motion")
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
    all_cases = cases_for(args.experiment, cfg, args.csv)
    if args.list_cases:
        for index, case in enumerate(all_cases, 1):
            print(f"Case {index}/{len(all_cases)}: {case}")
        return
    try:
        cases = select_cases(all_cases, args.case)
    except ValueError as exc:
        parser.error(str(exc))
    if args.case is not None:
        print(f"Selected case {args.case}/{len(all_cases)}: {cases[0]}")
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
