"""Cubic ServoJ tracking study on explicitly specified joint-space endpoints."""

import csv
import math
from itertools import product
from pathlib import Path

from experiments.csv_servo.points import load_points

START_JOINTS = (26.0, 53.8, 55.2, 71.0, 116.0, -180.2)
END_JOINTS = (-50.0, 54.0, 54.9, 71.4, 40.0, -180.2)
SAMPLE_PERIOD_S = 0.030
REQUESTED_DURATION_S = 2.0
AHEADTIMES = (20.0, 50.0, 80.0)
GAINS = (500.0, 300.0, 700.0)
DEFAULT_CSV = Path(__file__).with_name("points_servoj_cubic.csv")
TOL_DEG = 1e-4


def minimum_intervals():
    """Fixed 30 ms intervals for requested T; 2.0 s becomes 2.01 s."""
    return max(2, math.ceil(REQUESTED_DURATION_S / SAMPLE_PERIOD_S - 1e-12))


def validate_joint_csv(path, config):
    """Check ServoJ format, endpoints, cubic interpolation and duration."""
    if abs(config.servo_time_s - SAMPLE_PERIOD_S) > 1e-9:
        raise ValueError("ServoJ cubic CSV requires servo_time_s = 0.030")

    path = Path(path).expanduser().resolve()
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        names = csv.DictReader(handle).fieldnames or []
    columns = {name.strip().lower() for name in names}
    required = {"mode"} | {f"j{i}" for i in range(1, 7)}
    if not required.issubset(columns) or any(f"x{i}" in columns for i in range(1, 7)):
        raise ValueError("ServoJ CSV requires unambiguous mode,j1,j2,j3,j4,j5,j6 columns")

    points = load_points(path, "ServoJ")
    n = len(points)
    if n != minimum_intervals() + 1:
        raise ValueError(
            f"ServoJ cubic CSV requires exactly {minimum_intervals()+1} samples "
            f"at {SAMPLE_PERIOD_S:.3f}s for the requested T"
        )
    if any(point.mode != "ServoJ" for point in points):
        raise ValueError("ServoJ experiment accepts only mode=ServoJ rows")

    delta = [b - a for a, b in zip(START_JOINTS, END_JOINTS)]
    for index, point in enumerate(points):
        u = index / (n - 1)
        scale = 3 * u * u - 2 * u * u * u
        reference = [a + scale * d for a, d in zip(START_JOINTS, delta)]
        if len(point.values) != 6 or any(
            not math.isfinite(actual) or abs(actual - desired) > TOL_DEG
            for actual, desired in zip(point.values, reference)
        ):
            raise ValueError(
                f"ServoJ CSV row {index+2} does not match the specified "
                "joint-space cubic trajectory"
            )
    return path


def build_cases(config, csv_path=None):
    path = validate_joint_csv(csv_path or DEFAULT_CSV, config)
    return [
        {
            "name": "servoj_behavior",
            "mode": "csv",
            "csv_path": str(path),
            "aheadtime": aheadtime,
            "gain": gain,
            "global_speed_factor": 100,
        }
        for aheadtime, gain in product(AHEADTIMES, GAINS)
    ]
