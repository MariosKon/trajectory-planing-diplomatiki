"""Three fixed-trajectory ServoP quintic confirmation cases (five runs each).

Only SDK ServoP aheadtime and gain vary; hardware/acquisition settings
are inherited unchanged from the supplied configuration.
"""
import csv
import hashlib
import math
from pathlib import Path

from experiments.csv_servo.points import load_points

SAMPLE_PERIOD_S = 0.030
EXPECTED_SAMPLES = 68
PARAMETER_CASES = ((20.0, 300.0), (20.0, 500.0), (50.0, 300.0))
DEFAULT_CSV = Path(__file__).resolve().parents[1] / "quintic" / "points_quintic.csv"
POSE_TOL = 1e-5


def validate_quintic_csv(csv_path, config):
    """Validate the 30 ms, 2.01 s reference before any robot connection."""
    if abs(config.servo_time_s - SAMPLE_PERIOD_S) > 1e-9:
        raise ValueError("Quintic confirmation requires servo_time_s=0.030")
    path = Path(csv_path).expanduser().resolve()
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    if [field.strip().lower() for field in fieldnames] != [
        "mode", "x1", "x2", "x3", "x4", "x5", "x6"
    ]:
        raise ValueError("Quintic confirmation requires mode,x1,x2,x3,x4,x5,x6 columns")
    points = load_points(path, "ServoP")
    if len(points) != EXPECTED_SAMPLES:
        raise ValueError(
            f"Quintic confirmation requires exactly {EXPECTED_SAMPLES} samples "
            "over 2.01 s at 30 ms"
        )
    start, target = config.start, config.target
    if len(start) != 6 or len(target) != 6:
        raise ValueError("Expected six Cartesian pose coordinates")
    if sum((b-a)**2 for a, b in zip(start, target)) <= 0:
        raise ValueError("Quintic start and end cannot match")
    delta = [b-a for a, b in zip(start, target)]
    for k, point in enumerate(points):
        if point.mode != "ServoP":
            raise ValueError(f"Quintic row {k+2} is not ServoP")
        u = k / (EXPECTED_SAMPLES-1)
        s = 10*u**3 - 15*u**4 + 6*u**5
        expected = [a + s*d for a, d in zip(start, delta)]
        if any(not math.isfinite(actual) or abs(actual-ref) > POSE_TOL
               for actual, ref in zip(point.values, expected)):
            raise ValueError(f"Quintic CSV row {k+2} does not match the fixed reference")
    return path


def build_cases(config, csv_path=None):
    path = validate_quintic_csv(csv_path or DEFAULT_CSV, config)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return [
        {
            "name": "quintic_confirmation",
            "mode": "csv",
            "csv_path": str(path),
            "csv_sha256": digest,
            "aheadtime": aheadtime,
            "gain": gain,
            "global_speed_factor": 100,
        }
        for aheadtime, gain in PARAMETER_CASES
    ]
