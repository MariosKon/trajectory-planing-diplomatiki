"""Matched-time, Cartesian piecewise trajectory references.

The three profiles share the published 800 mm reference path and 30 ms grid.
Trapezoidal and Double-S are precomputed CSV commands; Ruckig is generated
online with a minimum requested duration (which is not a hard fixed time).
This module checks the committed CSV samples analytically before execution.
"""
import hashlib
import math
from pathlib import Path

from experiments.csv_servo.points import load_points
from experiments.polynomial_fixed_time import (
    DURATION_CASES, MOVEL_FAST_PLATEAU_MM_S, REFERENCE_END,
    REFERENCE_START, SAMPLE_PERIOD_S,
)

# Each target duration uses an explicitly prescribed peak scalar speed [mm/s].
# Keep the peak below the measured ~470.5 mm/s MoveL plateau (not a safety limit).
PEAK_SPEEDS_MM_S = (300.0, 400.0, 460.0)
JERK_RAMP_FRACTION = 0.25  # each jerk-ramp is 1/4 of acceleration-phase time


def phase_parameters(duration_s, peak_speed_mm_s):
    distance = math.dist(REFERENCE_START[:3], REFERENCE_END[:3])
    if not (math.isfinite(duration_s) and math.isfinite(peak_speed_mm_s)):
        raise ValueError("Duration and speed must be finite")
    if duration_s <= 0 or peak_speed_mm_s <= 0:
        raise ValueError("Duration and speed must be positive")
    ramp_s = duration_s - distance / peak_speed_mm_s
    if not 0 < 2 * ramp_s < duration_s:
        raise ValueError("Profile needs positive acceleration and cruise phases")
    jerk_ramp_s = JERK_RAMP_FRACTION * ramp_s
    trap_accel = peak_speed_mm_s / ramp_s
    s_accel = peak_speed_mm_s / (ramp_s - jerk_ramp_s)
    s_jerk = s_accel / jerk_ramp_s
    return ramp_s, jerk_ramp_s, trap_accel, s_accel, s_jerk


def _double_s_accel_distance(t, speed, ramp, jerk_ramp, acceleration, jerk):
    """Exact position through the first (+jerk, 0, -jerk) acceleration phase."""
    if t <= jerk_ramp:
        return jerk * t**3 / 6
    x1 = jerk * jerk_ramp**3 / 6
    v1 = acceleration * jerk_ramp / 2
    if t <= ramp - jerk_ramp:
        dt = t - jerk_ramp
        return x1 + v1 * dt + acceleration * dt**2 / 2
    duration_flat = ramp - 2 * jerk_ramp
    x2 = x1 + v1 * duration_flat + acceleration * duration_flat**2 / 2
    v2 = v1 + acceleration * duration_flat
    dt = t - (ramp - jerk_ramp)
    return x2 + v2 * dt + acceleration * dt**2 / 2 - jerk * dt**3 / 6


def scalar_position(profile, time_s, duration_s, peak_speed_mm_s):
    """Return distance [mm] from the path start at a sampled time."""
    distance = math.dist(REFERENCE_START[:3], REFERENCE_END[:3])
    ramp, jerk_ramp, trap_accel, s_accel, s_jerk = phase_parameters(
        duration_s, peak_speed_mm_s
    )
    t = min(max(time_s, 0.0), duration_s)
    if profile == "trapezoidal":
        accel_position = lambda dt: trap_accel * dt**2 / 2
    elif profile == "double_s":
        accel_position = lambda dt: _double_s_accel_distance(
            dt, peak_speed_mm_s, ramp, jerk_ramp, s_accel, s_jerk
        )
    else:
        raise ValueError(f"Unsupported piecewise profile: {profile}")
    if t <= ramp:
        return accel_position(t)
    if t >= duration_s - ramp:
        return distance - accel_position(duration_s - t)
    return (peak_speed_mm_s * ramp / 2
            + peak_speed_mm_s * (t - ramp))


def expected_positions(profile, duration_s, peak_speed_mm_s):
    intervals = round(duration_s / SAMPLE_PERIOD_S)
    if abs(intervals * SAMPLE_PERIOD_S - duration_s) > 1e-9:
        raise ValueError("Duration must be an exact 30 ms multiple")
    distance = math.dist(REFERENCE_START[:3], REFERENCE_END[:3])
    delta = [b - a for a, b in zip(REFERENCE_START, REFERENCE_END)]
    rows = []
    for i in range(intervals + 1):
        progress = scalar_position(
            profile, i * SAMPLE_PERIOD_S, duration_s, peak_speed_mm_s
        ) / distance
        row = [a + progress * d for a, d in zip(REFERENCE_START, delta)]
        if i == 0:
            row = list(REFERENCE_START)
        if i == intervals:
            row = list(REFERENCE_END)
        rows.append(row)
    return rows


def verify_reference(profile, path, duration_s, peak_speed_mm_s):
    expected = expected_positions(profile, duration_s, peak_speed_mm_s)
    points = load_points(path, "ServoP")
    if len(points) != len(expected):
        raise ValueError(f"Incorrect sample count in {path}")
    previous_y = -math.inf
    for index, (point, row) in enumerate(zip(points, expected), 1):
        if point.mode != "ServoP":
            raise ValueError(f"Non-ServoP command in {path} row {index}")
        if len(point.values) != 6 or not all(map(math.isfinite, point.values)):
            raise ValueError(f"Nonfinite/invalid pose in {path} row {index}")
        if any(abs(a - b) > 2e-6 for a, b in zip(point.values, row)):
            raise ValueError(f"Unexpected pose in {path} row {index}")
        if point.values[1] + 1e-7 < previous_y:
            raise ValueError(f"Nonmonotonic Y in {path} row {index}")
        previous_y = point.values[1]


def _verify_config(cfg):
    if not math.isclose(cfg.servo_time_s, SAMPLE_PERIOD_S, abs_tol=1e-12):
        raise ValueError("Piecewise references require servo_time_s = 0.030")
    for name, expected in (("start", REFERENCE_START), ("target", REFERENCE_END)):
        actual = getattr(cfg, name)
        if len(actual) != 6 or any(
            not math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
            for a, b in zip(actual, expected)
        ):
            raise ValueError(f"Config {name} differs from the reference pose")


def piecewise_cases(profile, cfg):
    """Build three documented, ordered, analytically checked cases."""
    if profile not in ("trapezoidal", "double_s", "ruckig"):
        raise ValueError(f"Unsupported piecewise profile: {profile}")
    _verify_config(cfg)
    cases = []
    for (label, duration), speed in zip(DURATION_CASES, PEAK_SPEEDS_MM_S):
        _, _, trap_accel, s_accel, s_jerk = phase_parameters(duration, speed)
        case = {
            "name": f"{profile}_T{label}",
            "duration_s": duration,
            "expected_peak_speed_mm_s": speed,
            "exceeds_movel_fast_speed": speed > MOVEL_FAST_PLATEAU_MM_S,
            "global_speed_factor": 100,
        }
        if profile == "ruckig":
            # The online optimizer observes the same velocity and Double-S
            # acceleration/jerk ceilings, but its actual peak speed and time
            # must be measured rather than assumed equal to the CSV profiles.
            case.update({
                "mode": "ruckig",
                "start": list(REFERENCE_START),
                "target": list(REFERENCE_END),
                "max_velocity": [speed] * 6,
                "max_acceleration": [s_accel] * 6,
                "max_jerk": [s_jerk] * 6,
                "minimum_duration_s": duration,
            })
        else:
            path = Path(__file__).resolve().parent / profile / (
                f"points_{profile}_T{label}.csv"
            )
            verify_reference(profile, path, duration, speed)
            case.update({
                "mode": "csv",
                "csv_path": str(path),
                "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "expected_points": round(duration / SAMPLE_PERIOD_S) + 1,
                "expected_peak_acceleration_mm_s2": (
                    trap_accel if profile == "trapezoidal" else s_accel
                ),
            })
            if profile == "double_s":
                case["expected_peak_jerk_mm_s3"] = s_jerk
            else:
                case["unbounded_transition_jerk"] = True
        cases.append(case)
    return cases
