"""ServoP tracking-parameter sweep using the exact MoveL Cartesian endpoints."""

import csv
import math
from itertools import product
from pathlib import Path

from experiments.csv_servo.points import load_points

DEFAULT_CSV = Path(__file__).with_name("points_servop_cubic.csv")
AHEADTIMES = (20.0, 50.0, 80.0)
GAINS = (500.0, 300.0, 700.0)  # first case is the existing 20 / 500 baseline
TOL = 1e-3


def validate_cartesian_csv(path, config):
    """Reject joint/unsafe/nonlinear CSVs before any robot connection."""
    path = Path(path).expanduser().resolve()
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    fields = {name.strip().lower() for name in fieldnames}
    expected = {"mode"} | {f"x{i}" for i in range(1, 7)}
    if not expected.issubset(fields):
        raise ValueError("ServoP experiment CSV requires mode,x1,x2,x3,x4,x5,x6")

    points = load_points(path, "ServoP")
    if len(points) < 3:
        raise ValueError("ServoP experiment requires at least 3 CSV samples")
    if any(point.mode != "ServoP" for point in points):
        raise ValueError("Only ServoP rows are allowed in this experiment")

    start = config.start
    target = config.target
    delta = [b-a for a, b in zip(start, target)]
    squared = sum(d*d for d in delta)
    if squared == 0:
        raise ValueError("MoveL start and target are identical")

    for label, point, reference in (
        ("start", points[0].values, start),
        ("target", points[-1].values, target),
    ):
        if any(not math.isfinite(x) or abs(x-y) > TOL
               for x, y in zip(point, reference)):
            raise ValueError(f"CSV {label} does not match configured MoveL {label}")

    last_s = -TOL
    for i, point in enumerate(points, 1):
        values = point.values
        if len(values) != 6 or any(not math.isfinite(x) for x in values):
            raise ValueError(f"Non-finite or invalid ServoP pose at row {i + 1}")
        s = sum((v-a)*d for v, a, d in zip(values, start, delta)) / squared
        if s < last_s - TOL or s < -TOL or s > 1 + TOL:
            raise ValueError(f"ServoP CSV is not monotonic at row {i + 1}")
        if any(abs(v-(a+s*d)) > TOL
               for v, a, d in zip(values, start, delta)):
            raise ValueError(f"ServoP CSV leaves MoveL straight line at row {i + 1}")
        last_s = s
    return path


def build_cases(config, csv_path=None):
    # CSV has no timestamps: sample period is determined exclusively by config.
    if abs(config.servo_time_s - 0.030) > 1e-9:
        raise ValueError("This MATLAB ServoP CSV requires servo_time_s = 0.030")
    path = validate_cartesian_csv(csv_path or DEFAULT_CSV, config)
    return [
        {
            "name": "servop_behavior",
            "mode": "csv",
            "csv_path": str(path),
            "aheadtime": aheadtime,
            "gain": gain,
            "global_speed_factor": 100,
        }
        for aheadtime, gain in product(AHEADTIMES, GAINS)
    ]
