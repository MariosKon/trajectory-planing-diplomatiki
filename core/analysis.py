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
    metrics = {
        "robot_samples": len(feedback),
        "rigol_samples": len(rigol),
    }

    for prefix, axes, name in (
        ("Q", range(1, 7), "joint_tracking_rmse"),
        ("ToolVector", range(1, 4), "tcp_position_tracking_rmse_mm"),
    ):
        errors = []
        target_prefix = prefix + "Target"
        actual_prefix = prefix + "Actual"
        for row in feedback:
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
        for row in feedback:
            values = [
                number(row.get(f"{prefix}[{i}]"))
                for i in range(1, axis_count+1)
            ]
            if all(x is not None for x in values):
                peaks.append(math.sqrt(sum(x*x for x in values)))
        metrics[name] = max(peaks) if peaks else None

    event_times = {}
    for row in events:
        t = number(row.get("host_time_s"))
        if t is not None:
            event_times[row.get("event")] = t
    if "MOTION_START" in event_times and "MOTION_END" in event_times:
        metrics["motion_duration_s"] = (
            event_times["MOTION_END"] - event_times["MOTION_START"]
        )
    else:
        metrics["motion_duration_s"] = None

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
        "failed": sum(r.get("status") != "completed" for r in output),
        "metrics": summary,
    }
    (destination.parent/"experiment_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
