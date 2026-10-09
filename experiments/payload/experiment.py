"""Fastest previously hardware-tested trajectories for a three-condition payload comparison.

This experiment never changes the physical payload or programs SetPayload
implicitly. Each phase is a *separate* invocation; the operator must change
and verify the load and robot payload configuration between invocations.
"""
import math

from experiments.helpers import cases_for


# Original 1-based case indices, as committed and tested on 2026-10-09.
# MoveL: SpeedFactor(100), acceleration 100%.
# Cubic/Quintic: 2.31 s Cartesian ServoP reference.
# L9 piecewise sweeps: V=460 mm/s, A=1100 mm/s2, J=10000 mm/s3
# (trapezoidal does not constrain jerk).
FASTEST_TESTED_CASES = (
    ("movel", 9),
    ("cubic", 3),
    ("quintic", 3),
    ("double_s", 9),
    ("ruckig", 9),
    ("trapezoidal", 9),
)
PHASES = ("baseline", "full", "empty")


def build_cases(config, phase="baseline", physical_payload_mass_kg=None):
    """Re-use verified experiment cases; add physical-condition provenance.

    physical_payload_mass_kg is *metadata only*. It must not be confused with
    the controller SetPayload setting (config.payload_kg with a tool_index).
    """
    if phase not in PHASES:
        raise ValueError(f"Invalid payload phase: {phase!r}")
    if physical_payload_mass_kg is not None and (
        not math.isfinite(physical_payload_mass_kg)
        or physical_payload_mass_kg < 0
    ):
        raise ValueError("Physical payload mass must be finite and non-negative")

    cases = []
    for sequence_number, (profile, source_case_number) in enumerate(
        FASTEST_TESTED_CASES, start=1
    ):
        source_cases = cases_for(profile, config)
        if len(source_cases) < source_case_number:
            raise ValueError(f"Case {source_case_number} missing for {profile}")
        case = dict(source_cases[source_case_number - 1])
        case.update({
            "trajectory_profile": profile,
            "reference_case_name": source_cases[source_case_number - 1]["name"],
            "source_case_index": source_case_number,
            "payload_phase": phase,
            "physical_payload_mass_kg": physical_payload_mass_kg,
            "matrix_case_index": sequence_number,
            "matrix_case_count": len(FASTEST_TESTED_CASES),
        })
        # Deliberately do not set payload_kg here: that existing key programs
        # controller SetPayload in core.runner and must be set only by an
        # operator-approved config with a configured tool.
        cases.append(case)
    return cases
