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
    parser.add_argument("--repetitions", type=int, default=None,
                        help="Repetitions per case (default: 3; payload: 1)")
    parser.add_argument("--case", type=int, default=None,
                        help="Run only one 1-based parameter combination (e.g. --case 1)")
    parser.add_argument("--list-cases", action="store_true",
                        help="Print available case numbers and parameters; no motion")
    parser.add_argument("--csv", default=None)
    parser.add_argument(
        "--payload-phase", choices=["baseline", "full", "empty"],
        help="Physical payload condition; required for real payload experiments",
    )
    parser.add_argument(
        "--payload-mass-kg", type=float, default=None,
        help="Measured physical load in kg, recorded as metadata only. "
             "Does not program the controller SetPayload value.",
    )
    parser.add_argument("--config", default="config/common.json")
    parser.add_argument(
        "--execute", action="store_true",
        help="Send real commands to the robot. Without this flag, dry-run."
    )
    args = parser.parse_args()
    is_payload = args.experiment == "payload"
    if is_payload:
        if args.execute and args.payload_phase is None:
            parser.error("Real payload execution requires --payload-phase baseline|full|empty")
        repetitions = 1 if args.repetitions is None else args.repetitions
        phase = args.payload_phase or "baseline"
    else:
        if args.payload_phase is not None or args.payload_mass_kg is not None:
            parser.error("--payload-phase and --payload-mass-kg require --experiment payload")
        repetitions = 3 if args.repetitions is None else args.repetitions
        phase = None
    if repetitions < 1:
        parser.error("Repetitions must be >= 1")
    cfg = Config.load(ROOT/args.config)
    try:
        all_cases = cases_for(
            args.experiment, cfg, args.csv,
            payload_phase=phase or "baseline",
            physical_payload_mass_kg=args.payload_mass_kg,
        )
    except ValueError as exc:
        parser.error(str(exc))
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
    if is_payload:
        print(f"Payload comparison phase: {phase.upper()} — {len(cases)} selected trajectories")
        print("Physical payload mass is recording metadata only. "
              "Verify real attachment, clearance, load limits and the "
              "controller tool_index/payload_kg configuration before executing.")
        if args.execute:
            print("IMPORTANT: This invocation runs ONLY the selected phase. "
                  "Changing the physical payload requires a NEW invocation.")
    result = batch(
        cfg,
        f"payload/{phase}" if is_payload else args.experiment,
        cases, repetitions, execute=args.execute
    )
    print("Results:", result)
    if is_payload and phase == "baseline":
        print("STOP AFTER BASELINE. Inspect the recordings and safely change "
              "the physical payload and controller configuration. "
              "Start full or empty as a separate run only after verification.")

if __name__ == "__main__":
    main()
