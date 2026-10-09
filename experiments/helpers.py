from itertools import product
from pathlib import Path

def cases_for(name, cfg, csv_path=None):
    if name == "servoP_confirmation":
        from experiments.servoP_confirmation.experiment import build_cases
        return build_cases(cfg, csv_path)

    if name == "servoj_behavior":
        from experiments.servoj_behavior.experiment import build_cases
        return build_cases(cfg, csv_path)

    if name == "servop_behavior":
        from experiments.servop_behavior.experiment import build_cases
        return build_cases(cfg, csv_path)

    if name in ("trapezoidal_matched", "double_s_matched", "ruckig_matched"):
        if csv_path is not None:
            raise ValueError("Matched-time experiment does not accept --csv")
        from experiments.piecewise_fixed_time import piecewise_cases
        return piecewise_cases(name.removesuffix("_matched"), cfg)

    if name in ("trapezoidal", "double_s", "ruckig") and csv_path is None:
        from experiments.piecewise_parameter_study import sweep_cases
        return sweep_cases(name, cfg)

    if name == "ruckig" and csv_path is not None:
        raise ValueError("Ruckig is online and does not accept --csv")

    if name in ("cubic", "quintic") and csv_path is None:
        from experiments.polynomial_fixed_time import fixed_time_polynomial_cases
        return fixed_time_polynomial_cases(name, cfg)

    if name in ("cubic", "quintic", "trapezoidal", "double_s", "csv_servo"):
        # Supplying --csv explicitly preserves the one-file-per-run workflow.
        filename = csv_path or (
            Path(__file__).parent/name/f"points_{name}.csv"
        )
        return [{
            "name": name,
            "mode": "csv",
            "csv_path": str(Path(filename).resolve()),
        }]

    if name in ("movel", "movej"):
        if name == "movej":
            raise ValueError(
                "MoveJ requires explicitly configured joint-space start "
                "and target values; Cartesian MoveL poses cannot be reused."
            )
        return [
            {
                "name": name,
                "mode": name,
                "start": cfg.start,
                "target": cfg.target,
                "speed": speed,
                "acceleration": acceleration,
            }
            for speed, acceleration in product(
                [50,75,100], [50,75,100]
            )
        ]

    if name == "payload":
        return [{
            "name": name,
            "mode": "movel",
            "start": cfg.start,
            "target": cfg.target,
            "speed": 50,
            "acceleration": 50,
            "payload_kg": mass,
        } for mass in [0.5]]

    raise ValueError(f"Unknown experiment: {name}")
