"""Prevalidated 30 ms, fixed-duration Cartesian ServoP polynomial cases.

Unlike a speed-limit-based generator, these cases prescribe the time first.
The faster quintic references exceed the measured MoveL TCP speed plateau:
they must not be interpreted as identical-speed tests.
"""

import hashlib
import math
from pathlib import Path

from experiments.csv_servo.points import load_points


SAMPLE_PERIOD_S = 0.030
# Grid-aligned approximations of measured MoveL times 3.93, 2.80, 2.30 s.
DURATION_CASES = (
    ("3p93", 3.93),
    ("2p79", 2.79),
    ("2p31", 2.31),
)
REFERENCE_START = (-600.0, -400.0, 250.0, -90.0, 0.0, 90.0)
REFERENCE_END = (-600.0, 400.0, 250.0, -90.0, 0.0, 90.0)
# Empirical MoveL plateau at global speed factor 100%, not a robot safety limit.
MOVEL_FAST_PLATEAU_MM_S = 470.5


def _progress(profile, u):
    if profile == "cubic":
        return 3 * u * u - 2 * u * u * u
    if profile == "quintic":
        return 10 * u**3 - 15 * u**4 + 6 * u**5
    raise ValueError(f"Unsupported fixed-time polynomial: {profile}")


def _expected_peaks(profile, duration_s):
    # Analytic Cartesian translation peaks, excluding start/end transition impulses.
    distance_mm = math.dist(REFERENCE_START[:3], REFERENCE_END[:3])
    if profile == "cubic":
        v_coeff, a_coeff, j_coeff = 1.5, 6.0, 12.0
    elif profile == "quintic":
        v_coeff, a_coeff, j_coeff = 15/8, 10*math.sqrt(3)/3, 60.0
    else:
        raise ValueError(f"Unsupported fixed-time polynomial: {profile}")
    return (
        v_coeff * distance_mm / duration_s,
        a_coeff * distance_mm / duration_s**2,
        j_coeff * distance_mm / duration_s**3,
    )


def _verify_reference(profile, csv_path, duration_s):
    points = load_points(csv_path, "ServoP")
    intervals = round(duration_s / SAMPLE_PERIOD_S)
    if abs(intervals * SAMPLE_PERIOD_S - duration_s) > 1e-9:
        raise ValueError("Polynomial duration is not aligned to 30 ms")
    if len(points) != intervals + 1:
        raise ValueError(
            f"Expected {intervals + 1} rows in {csv_path}, got {len(points)}"
        )

    delta = [b - a for a, b in zip(REFERENCE_START, REFERENCE_END)]
    previous_y = -math.inf
    for index, point in enumerate(points):
        if point.mode != "ServoP":
            raise ValueError(f"Non-ServoP row {index + 1} in {csv_path}")
        if len(point.values) != 6 or not all(map(math.isfinite, point.values)):
            raise ValueError(f"Invalid pose at row {index + 1} in {csv_path}")
        u = index / intervals
        s = _progress(profile, u)
        expected = [a + s * d for a, d in zip(REFERENCE_START, delta)]
        if any(abs(actual - ref) > 2e-6 for actual, ref in
               zip(point.values, expected)):
            raise ValueError(f"Unexpected pose at row {index + 1} in {csv_path}")
        if point.values[1] + 1e-7 < previous_y:
            raise ValueError(f"Non-monotonic Y at row {index + 1} in {csv_path}")
        previous_y = point.values[1]


def fixed_time_polynomial_cases(profile, cfg):
    if not math.isclose(cfg.servo_time_s, SAMPLE_PERIOD_S, abs_tol=1e-12):
        raise ValueError("Fixed-time polynomial CSVs require servo_time_s = 0.030")
    for name, actual, expected in (
        ("start", cfg.start, REFERENCE_START),
        ("target", cfg.target, REFERENCE_END),
    ):
        if len(actual) != 6 or any(
            not math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
            for a, b in zip(actual, expected)
        ):
            raise ValueError(
                f"Config {name} does not match the reference Cartesian pose"
            )

    cases = []
    for label, duration_s in DURATION_CASES:
        csv_path = Path(__file__).resolve().parent / profile / (
            f"points_{profile}_T{label}.csv"
        )
        _verify_reference(profile, csv_path, duration_s)
        sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        velocity, acceleration, jerk = _expected_peaks(profile, duration_s)
        cases.append({
            "name": f"{profile}_T{label}",
            "mode": "csv",
            "csv_path": str(csv_path),
            "csv_sha256": sha256,
            "duration_s": duration_s,
            "expected_points": round(duration_s / SAMPLE_PERIOD_S) + 1,
            "expected_peak_speed_mm_s": velocity,
            "expected_peak_acceleration_mm_s2": acceleration,
            "expected_peak_jerk_mm_s3": jerk,
            "exceeds_movel_fast_speed": velocity > MOVEL_FAST_PLATEAU_MM_S,
            # MoveL used SpeedFactor(50/75/100). ServoP uses 100% to avoid
            # silently throttling an externally imposed reference trajectory.
            "global_speed_factor": 100,
        })
    return cases
