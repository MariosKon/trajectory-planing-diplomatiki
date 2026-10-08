from __future__ import annotations

from dataclasses import dataclass

try:
    from ruckig import InputParameter, OutputParameter, Result, Ruckig
except ImportError as exc:  # pragma: no cover - depends on external package
    raise ImportError(
        "Ruckig is required for this example. Install it with: py -m pip install ruckig"
    ) from exc


@dataclass(frozen=True)
class RuckigStep:
    time_s: float
    position: list[float]
    velocity: list[float]
    acceleration: list[float]
    calculation_duration_us: float
    trajectory_duration_s: float
    finished: bool


class OnlineRuckigPlanner:
    """State-to-state online Ruckig planner advanced once per ServoP cycle."""

    def __init__(
        self,
        start: list[float],
        target: list[float],
        period_s: float,
        max_velocity: list[float],
        max_acceleration: list[float],
        max_jerk: list[float],
        minimum_duration_s: float | None = None,
    ) -> None:
        axis_count = len(start)
        if axis_count == 0 or len(target) != axis_count:
            raise ValueError("start and target must contain the same non-zero number of axes")
        for name, values in (
            ("max_velocity", max_velocity),
            ("max_acceleration", max_acceleration),
            ("max_jerk", max_jerk),
        ):
            if len(values) != axis_count:
                raise ValueError(f"{name} must contain {axis_count} values")

        self._otg = Ruckig(axis_count, period_s)
        self._input = InputParameter(axis_count)
        self._output = OutputParameter(axis_count)

        self._input.current_position = list(start)
        self._input.current_velocity = [0.0] * axis_count
        self._input.current_acceleration = [0.0] * axis_count

        self._input.target_position = list(target)
        self._input.target_velocity = [0.0] * axis_count
        self._input.target_acceleration = [0.0] * axis_count

        self._input.max_velocity = list(max_velocity)
        self._input.max_acceleration = list(max_acceleration)
        self._input.max_jerk = list(max_jerk)

        if minimum_duration_s is not None:
            self._input.minimum_duration = minimum_duration_s

        self._finished = False

    def update(self) -> RuckigStep:
        if self._finished:
            raise RuntimeError("Ruckig planner has already finished")

        result = self._otg.update(self._input, self._output)
        if result not in (Result.Working, Result.Finished):
            raise RuntimeError(f"Ruckig update failed with result: {result}")

        step = RuckigStep(
            time_s=float(self._output.time),
            position=[float(value) for value in self._output.new_position],
            velocity=[float(value) for value in self._output.new_velocity],
            acceleration=[float(value) for value in self._output.new_acceleration],
            calculation_duration_us=float(self._output.calculation_duration),
            trajectory_duration_s=float(self._output.trajectory.duration),
            finished=result == Result.Finished,
        )

        # Pure online trajectory generation: advance Ruckig from its own commanded
        # state. We intentionally do not feed measured robot feedback back into
        # the planner, so the comparison with the offline planners stays clean.
        self._output.pass_to_input(self._input)
        self._finished = step.finished
        return step
