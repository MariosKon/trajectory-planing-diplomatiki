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

    if name in ("cubic", "quintic", "trapezoidal", "double_s", "csv_servo"):
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

    if name == "ruckig":
        return [{
            "name": name,
            "mode": "ruckig",
            "start": cfg.start,
            "target": cfg.target,
            "max_velocity": [500.0]*6,
            "max_acceleration": [1500.0]*6,
            "max_jerk": [16000.0]*6,
            "minimum_duration_s": None,
        }]

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
