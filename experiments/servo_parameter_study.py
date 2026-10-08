"""Fixed-path parameter matrices for DOBOT ServoJ and ServoP.

The SDK has no ServoL command: its Cartesian servo counterpart is ServoP.
All cases within one matrix replay the same input CSV at a fixed 30 ms period.
"""
from __future__ import annotations

import csv
import hashlib
import math
from itertools import product
from pathlib import Path

AHEADTIME_LEVELS = (20.0, 50.0, 80.0)
GAIN_LEVELS = (300.0, 500.0, 800.0)
SERVO_MODES = {"servoj_params": "ServoJ", "servop_params": "ServoP"}


def validate_servo_csv(path: str | Path, required_mode: str) -> dict:
    """Reject missing/mixed/mislabeled trajectory samples before robot connection."""
    if required_mode not in SERVO_MODES.values():
        raise ValueError(f"Unsupported servo mode: {required_mode!r}")
    file_path = Path(path).expanduser().resolve(strict=True)
    if not file_path.is_file():
        raise ValueError(f"Not a trajectory CSV file: {file_path}")
    from experiments.csv_servo.points import load_points

    with file_path.open(newline="", encoding="utf-8-sig") as handle:
        header = csv.DictReader(handle).fieldnames
    if not header or "mode" not in {x.strip().lower() for x in header}:
        raise ValueError(
            "Servo parameter studies require an explicit 'mode' column "
            "with ServoJ or ServoP on every row."
        )
    points = load_points(file_path, required_mode)
    if len(points) < 5:
        raise ValueError("At least five trajectory points are required")
    for index, point in enumerate(points, 1):
        if point.mode != required_mode:
            raise ValueError(
                f"CSV row {index + 1} has mode {point.mode!r}; "
                f"expected {required_mode}. Do not mix joint and Cartesian commands."
            )
        if len(point.values) != 6 or not all(math.isfinite(v) for v in point.values):
            raise ValueError(f"CSV row {index + 1} has invalid coordinates")
    if all(math.isclose(a, b, abs_tol=1e-8)
           for a, b in zip(points[0].values, points[-1].values)):
        raise ValueError("Start and target points are identical")
    return {
        "csv_path": str(file_path),
        "csv_sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
        "point_count": len(points),
        "first_point": list(points[0].values),
        "last_point": list(points[-1].values),
    }


def servo_parameter_cases(name: str, cfg, csv_path: str | None) -> list[dict]:
    """Build nine parameter combinations using one *validated* trajectory."""
    if name not in SERVO_MODES:
        raise ValueError(f"Unknown servo study {name!r}")
    if not csv_path:
        raise ValueError(
            f"{name} requires --csv with an explicitly labeled "
            f"{SERVO_MODES[name]} trajectory (6 axes, one row every "
            f"{cfg.servo_time_s:g} seconds)"
        )
    profile = validate_servo_csv(csv_path, SERVO_MODES[name])
    period = float(cfg.servo_time_s)
    if not 0.004 <= period <= 3600.0:
        raise ValueError("Servo command t must satisfy SDK limits")
    planned_duration_s = period * profile["point_count"]
    scope_scale = cfg.rigol_horizontal_scale_s_per_div
    if cfg.rigol_resource and scope_scale is not None:
        available = 12.0 * scope_scale
        required = (
            cfg.rigol_pre_delay_s + planned_duration_s
            + cfg.robot_logger_post_delay_s + cfg.rigol_stop_delay_s + 0.1
        )
        if required > available:
            raise ValueError(
                f"Servo CSV duration {planned_duration_s:.2f}s plus acquisition "
                f"lead/tail needs at least {required:.2f}s, but Rigol window "
                f"is {available:.2f}s. Increase the Rigol timebase; do not "
                "truncate the waveform."
            )
    return [
        {
            "name": name,
            "mode": "csv",
            "servo_mode": SERVO_MODES[name],
            "csv_path": profile["csv_path"],
            "csv_sha256": profile["csv_sha256"],
            "point_count": profile["point_count"],
            "first_point": profile["first_point"],
            "last_point": profile["last_point"],
            "servo_time_s": period,
            "aheadtime": aheadtime,
            "gain": gain,
        }
        for aheadtime, gain in product(AHEADTIME_LEVELS, GAIN_LEVELS)
    ]
