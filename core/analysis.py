import csv
import json
import math
import statistics
from pathlib import Path

def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def rmse(values):
    values = [x for x in values if x is not None]
    if not values:
        return None
    return math.sqrt(sum(x*x for x in values)/len(values))

def analyze_trial(folder):
    folder = Path(folder)
    feedback = rows(folder/"feedback.csv")
    rigol = rows(folder/"rigol_scope.csv")
    events = rows(folder/"events.csv")
    # IMPORTANT: logger activity can continue while VISA downloads
    # megabytes of waveform data. Time-filter all motion metrics.
    event_times = {}
    for event_row in events:
        timestamp = number(event_row.get("host_time_s"))
        if timestamp is not None:
            event_times[event_row.get("event")] = timestamp

    motion_start = event_times.get("MOTION_START")
    motion_end = event_times.get("MOTION_END")
    valid_window = (
        motion_start is not None and motion_end is not None
        and motion_end > motion_start
    )
    motion_feedback = [
        sample for sample in feedback
        if valid_window
        and (timestamp := number(sample.get("host_time_s"))) is not None
        and motion_start <= timestamp <= motion_end
    ]
    metrics = {
        "robot_samples": len(feedback),
        "robot_motion_samples": len(motion_feedback),
        "robot_motion_window_valid": bool(valid_window and motion_feedback),
        "rigol_samples": len(rigol),
        "motion_duration_s": motion_end - motion_start if valid_window else None,
    }
    # ServoP command timing and robot-idle polling are not the same as
    # physical 1-99%% Cartesian TCP travel time.
    first_sent = event_times.get("SERVO_FIRST_COMMAND_SENT")
    last_sent = event_times.get("SERVO_LAST_COMMAND_SENT")
    stream_done = event_times.get("SERVO_STREAM_PERIOD_END")
    idle_confirmed = event_times.get("SERVO_ROBOT_IDLE")
    metrics["command_stream_first_to_last_s"] = (
        last_sent-first_sent if first_sent is not None
        and last_sent is not None and last_sent >= first_sent else None
    )
    metrics["command_stream_period_end_from_first_s"] = (
        stream_done-first_sent if stream_done is not None
        and first_sent is not None and stream_done >= first_sent else None
    )
    metrics["post_stream_idle_wait_s"] = (
        idle_confirmed-stream_done if idle_confirmed is not None
        and stream_done is not None and idle_confirmed >= stream_done else None
    )

    for prefix, axes, name in (
        ("Q", range(1, 7), "joint_tracking_rmse"),
        ("ToolVector", range(1, 4), "tcp_position_tracking_rmse_mm"),
    ):
        errors = []
        target_prefix = prefix + "Target"
        actual_prefix = prefix + "Actual"
        for row in motion_feedback:
            components = []
            for axis in axes:
                target = number(row.get(f"{target_prefix}[{axis}]"))
                actual = number(row.get(f"{actual_prefix}[{axis}]"))
                if target is None or actual is None:
                    components = []
                    break
                components.append(target-actual)
            if components:
                errors.append(math.sqrt(sum(x*x for x in components)))
        metrics[name] = rmse(errors)
        metrics[name + "_max"] = max(errors) if errors else None

    for name, prefix in (
        ("joint_velocity_max", "QDActual"),
        ("tcp_speed_max", "TCPSpeedActual"),
    ):
        peaks = []
        axis_count = 6 if prefix == "QDActual" else 3
        for row in motion_feedback:
            values = [
                number(row.get(f"{prefix}[{i}]"))
                for i in range(1, axis_count+1)
            ]
            if all(x is not None for x in values):
                peaks.append(math.sqrt(sum(x*x for x in values)))
        metrics[name] = max(peaks) if peaks else None

    # Measure robot TCP 1-99% of translation, not the command/idle window.
    # MoveL endpoints come from case.json; CSV ServoP endpoints are the first
    # and final command points. Joint-space ServoJ is excluded.
    metrics["tcp_travel_1pct_99pct_s"] = None
    command_rows = rows(folder/"commands.csv")
    start_pose, end_pose = None, None
    if command_rows and all(row.get("mode") == "ServoP" for row in command_rows):
        start_pose = [number(command_rows[0].get(f"position_{i}"))
                      for i in range(1, 4)]
        end_pose = [number(command_rows[-1].get(f"position_{i}"))
                    for i in range(1, 4)]
    elif (folder/"case.json").exists():
        try:
            case = json.loads((folder/"case.json").read_text(encoding="utf-8"))
            if case.get("mode") == "movel":
                start_pose = [number(value) for value in case["start"][:3]]
                end_pose = [number(value) for value in case["target"][:3]]
        except (ValueError, TypeError, KeyError, IndexError):
            pass
    if (start_pose is not None and end_pose is not None
            and all(x is not None for x in start_pose+end_pose)):
        displacement = [b-a for a, b in zip(start_pose, end_pose)]
        squared_distance = sum(v*v for v in displacement)
        if squared_distance > 1e-12:
            crossing_1, crossing_99 = None, None
            for sample in motion_feedback:
                xyz = [number(sample.get(f"ToolVectorActual[{i}]"))
                       for i in range(1, 4)]
                sample_time = number(sample.get("host_time_s"))
                if sample_time is None or any(value is None for value in xyz):
                    continue
                progress = sum((x-a)*d for x, a, d in
                               zip(xyz, start_pose, displacement)) / squared_distance
                if crossing_1 is None and progress >= 0.01:
                    crossing_1 = sample_time
                if crossing_99 is None and progress >= 0.99:
                    crossing_99 = sample_time
            if (crossing_1 is not None and crossing_99 is not None
                    and crossing_99 >= crossing_1):
                metrics["tcp_travel_1pct_99pct_s"] = crossing_99 - crossing_1

    scope_samples = []
    for row in rigol:
        t = number(row.get("time_s", row.get("host_time_s")))
        p = number(row.get("power_W"))
        if t is not None and p is not None:
            scope_samples.append((t, p))
    scope_samples.sort()
    metrics["mean_power_W"] = (
        statistics.fmean(p for _, p in scope_samples)
        if scope_samples else None
    )
    metrics["peak_power_W"] = (
        max(p for _, p in scope_samples)
        if scope_samples else None
    )
    energy = 0.0
    for (t0,p0),(t1,p1) in zip(scope_samples, scope_samples[1:]):
        if t1 > t0:
            energy += 0.5*(p0+p1)*(t1-t0)
    metrics["rigol_acquisition_energy_J"] = (
        energy if len(scope_samples) > 1 else None
    )

    # The full oscilloscope acquisition may include periods before/after
    # motion. It is not automatically equivalent to motion-only energy.
    (folder/"metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    with (folder/"metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(metrics.items())
    return metrics

def aggregate(trials, destination):
    output = []
    for item in trials:
        record = dict(item)
        output.append(record)

    destination = Path(destination)
    keys = sorted(set().union(*(r.keys() for r in output))) if output else []
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(output)

    summary = {}
    for key in keys:
        values = [number(row.get(key)) for row in output
                  if row.get("status") == "completed"]
        values = [v for v in values if v is not None]
        if values:
            summary[key] = {
                "mean": statistics.fmean(values),
                "std": statistics.stdev(values) if len(values)>1 else 0.0,
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }

    result = {
        "trials": len(output),
        "completed": sum(r.get("status") == "completed" for r in output),
        "partial": sum(r.get("status") == "partial" for r in output),
        "failed": sum(r.get("status") == "failed" for r in output),
        "metrics": summary,
    }
    (destination.parent/"experiment_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
