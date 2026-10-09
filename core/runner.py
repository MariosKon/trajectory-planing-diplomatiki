import csv
import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path


from .robot import slow_move, wait_for_motion, check_response
from .analysis import analyze_trial, aggregate
from loggers.manager import LoggingManager

def load_points(path):
    from experiments.csv_servo.points import load_points as legacy_loader
    return legacy_loader(path, "ServoP")


def configure_motion_speed(robot, case):
    """Apply explicit case-wide speed factor, or MoveL/MoveJ convention."""
    if "global_speed_factor" in case:
        response = robot.robot_control.SpeedFactor(case["global_speed_factor"])
        check_response(response)
        return response
    if case.get("mode") in ("movel", "movej"):
        # The measured controller did not vary TCP speed when only MovL's
        # local v percentage changed. Use the case speed as the global factor,
        # and keep the motion command's local v at 100 (no double scaling).
        response = robot.robot_control.SpeedFactor(case.get("speed", 100))
        check_response(response)
        return response
    return None


def effective_servo_parameters(cfg, case, command_mode):
    """Resolve SDK tuning; preserve ServoJ defaults and explicit sweep cases."""
    if command_mode == "ServoP":
        default_aheadtime, default_gain = cfg.servop_aheadtime, cfg.servop_gain
    else:
        default_aheadtime, default_gain = cfg.aheadtime, cfg.gain
    aheadtime = float(case.get("aheadtime", default_aheadtime))
    gain = float(case.get("gain", default_gain))
    if not 20.0 <= aheadtime <= 100.0:
        raise ValueError("Servo aheadtime must be in [20, 100]")
    if not 200.0 <= gain <= 1000.0:
        raise ValueError("Servo gain must be in [200, 1000]")
    return aheadtime, gain


def execute_motion(robot, cfg, case, manager, run_dir):
    from dobot_sdk import CoordinateType
    mode = case["mode"]
    started = time.perf_counter()
    durations = []
    late = 0
    max_lateness = 0.0

    if mode in ("movel", "movej"):
        target = case["target"]
        manager.robot.set_commanded_point(target)
        speed = case.get("speed", 100)
        accel = case.get("acceleration", 100)
        global_speed = case.get("global_speed_factor", speed)
        command_v = 100
        manager.event(
            "MOTION_PARAMETERS",
            f"mode={mode}; requested_speed={speed}; v={command_v}; "
            f"a={accel}; global_speed={global_speed}",
        )
        print(
            f"[{mode.upper()}] SpeedFactor={global_speed}% "
            f"v={command_v}% a={accel}%",
            flush=True,
        )
        if mode == "movel":
            response = robot.motion.MovL(
                target, CoordinateType.CARTESIAN, a=accel, v=command_v
            )
        else:
            response = robot.motion.MovJ(
                target, CoordinateType.JOINT, a=accel, v=command_v
            )
        check_response(response)
        wait_for_motion(robot, cfg.motion_timeout_s)
        return {
            "command_count": 1,
            "response": str(response),
            "speed_percent": speed,
            "global_speed_factor": global_speed,
            "command_v_percent": command_v,
            "acceleration_percent": accel,
            "elapsed_s": time.perf_counter()-started,
        }

    if mode == "csv":
        if "csv_sha256" in case:
            actual_sha = hashlib.sha256(Path(case["csv_path"]).read_bytes()).hexdigest()
            if actual_sha != case["csv_sha256"]:
                raise ValueError("Reference CSV changed after preflight; refusing motion")
        points = load_points(case["csv_path"])
        if "expected_points" in case and len(points) != case["expected_points"]:
            raise ValueError("Fixed-time trajectory point count changed")
        period = cfg.servo_time_s
        planner = None
    elif mode == "ruckig":
        from experiments.ruckig.planner import OnlineRuckigPlanner
        planner = OnlineRuckigPlanner(
            start=case["start"],
            target=case["target"],
            period_s=cfg.servo_time_s,
            max_velocity=case["max_velocity"],
            max_acceleration=case["max_acceleration"],
            max_jerk=case["max_jerk"],
            minimum_duration_s=case.get("minimum_duration_s"),
        )
        points = None
        period = cfg.servo_time_s
    else:
        raise ValueError(f"Unknown motion mode: {mode}")

    if mode == "csv":
        # Mixed command-mode CSVs need explicit tuning to avoid ambiguous defaults.
        if len({point.mode for point in points}) > 1 and not (
            "aheadtime" in case and "gain" in case
        ):
            raise ValueError("Mixed ServoP/ServoJ CSV requires explicit aheadtime and gain")
        aheadtime, gain = effective_servo_parameters(cfg, case, points[0].mode)
        manager.event(
            "MOTION_PARAMETERS",
            f"servo_t_s={period};aheadtime={aheadtime};gain={gain};"
            f"planned_duration_s={case.get('duration_s')};"
            f"global_speed={case.get('global_speed_factor', cfg.slow_speed)}",
        )
    else:
        # Online Ruckig streams ServoP commands.
        aheadtime, gain = effective_servo_parameters(cfg, case, "ServoP")

    fields = [
        "sample", "host_time_s", "mode", "servo_t_s", "aheadtime", "gain", "lateness_ms",
        "command_duration_ms", "planner_time_s",
        "planner_calculation_us", "finished",
    ] + [f"position_{i}" for i in range(1,7)]

    count = 0
    with (run_dir/"commands.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        while True:
            if planner is not None:
                step = planner.update()
                values = step.position
                command_mode = "ServoP"
                finished = step.finished
                planner_time = step.time_s
                calculation = step.calculation_duration_us
            else:
                if count >= len(points):
                    break
                point = points[count]
                values = point.values
                command_mode = point.mode
                finished = count == len(points)-1
                planner_time = None
                calculation = None

            deadline = started + count*period
            remaining = deadline-time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
            elif count > 0:
                late += 1
                max_lateness = max(max_lateness, -remaining)

            manager.robot.set_commanded_point(values)
            command_started = time.perf_counter()

            if command_mode == "ServoJ":
                response = robot.motion.ServoJ(
                    values, period, aheadtime, gain
                )
            elif command_mode == "ServoP":
                response = robot.motion.ServoP(
                    values, period, aheadtime, gain
                )
            else:
                raise ValueError(f"Unsupported mode: {command_mode}")

            check_response(response)
            duration = time.perf_counter()-command_started
            durations.append(duration)

            row = {
                "sample": count+1,
                "host_time_s": time.perf_counter()-manager.robot.t0,
                "mode": command_mode,
                "servo_t_s": period,
                "aheadtime": aheadtime,
                "gain": gain,
                "lateness_ms": max(0.0, -remaining)*1000,
                "command_duration_ms": duration*1000,
                "planner_time_s": planner_time,
                "planner_calculation_us": calculation,
                "finished": finished,
            }
            row.update({
                f"position_{i}": value
                for i, value in enumerate(values, start=1)
            })
            writer.writerow(row)
            count += 1
            if planner is not None and finished:
                break

    remaining = started+count*period-time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)
    wait_for_motion(robot, cfg.motion_timeout_s)
    return {
        "command_count": count,
        "late_commands": late,
        "maximum_lateness_ms": max_lateness*1000,
        "mean_command_duration_ms": (
            sum(durations)/len(durations)*1000 if durations else None
        ),
        "elapsed_s": time.perf_counter()-started,
    }

def run_trial(cfg, case, run_dir, robot=None):
    # Reject modified fixed-time reference before connecting/moving the robot.
    if case.get("mode") == "csv" and "csv_sha256" in case:
        actual_sha = hashlib.sha256(
            Path(case["csv_path"]).read_bytes()
        ).hexdigest()
        if actual_sha != case["csv_sha256"]:
            raise ValueError("Reference CSV changed after case selection")
    from dobot_sdk import CoordinateType
    owns_robot = robot is None
    if owns_robot:
        from dobot_sdk import DobotRobot
        robot = DobotRobot(cfg.robot_ip)
        robot.Connect()
    manager = LoggingManager(cfg, run_dir)
    result = {"status": "failed", "case": case}
    connected = robot is not None
    success = False

    try:
        if owns_robot:
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot()

        payload = case.get("payload_kg", cfg.payload_kg)
        if cfg.tool_index is not None:
            robot.robot_control.SetTool(cfg.tool_index, cfg.tool_pose)
            if payload is not None:
                robot.robot_control.SetPayload(payload)
            robot.robot_control.Tool(cfg.tool_index)
        elif payload is not None:
            raise ValueError(
                "Configure tool_index before applying a payload"
            )

        robot.robot_control.SpeedFactor(cfg.slow_speed)
        robot.robot_control.AccJ(cfg.slow_acceleration)

        print("[ROBOT] Moving to home position", flush=True)
        # Preparation is deliberately excluded from the trial recording.
        slow_move(robot, cfg.home, CoordinateType.JOINT, cfg)

        if case["mode"] == "csv":
            points = load_points(case["csv_path"])
            start = points[0].values
            coordinate = (
                CoordinateType.JOINT if points[0].mode == "ServoJ"
                else CoordinateType.CARTESIAN
            )
        else:
            start = case["start"]
            coordinate = (
                CoordinateType.JOINT if case["mode"] == "movej"
                else CoordinateType.CARTESIAN
            )

        print("[ROBOT] Moving to experiment start position", flush=True)
        slow_move(robot, start, coordinate, cfg)
        speed_response = configure_motion_speed(robot, case)
        if speed_response is not None:
            print(
                f"[ROBOT] Global speed factor set to "
                "100% (explicit case settings)", flush=True
            )
        print("[LOGGING] Starting robot, Rigol and camera loggers", flush=True)
        manager.start()
        print("[LOGGING] Acquisition started", flush=True)
        if manager.rigol_started:
            rigol_start = manager.rigol.metadata.get("host_start_perf_s")
            if isinstance(rigol_start, (int, float)):
                rigol_lead_s = time.perf_counter() - rigol_start
                manager.event(
                    "RIGOL_TO_MOTION_LEAD",
                    f"seconds={rigol_lead_s:.6f}",
                )
                print(
                    f"[RIGOL] :RUN-to-motion command lead: {rigol_lead_s:.3f}s",
                    flush=True,
                )
        manager.event("MOTION_START", str(case))
        print("[MOTION] Executing trajectory", flush=True)
        result["motion"] = execute_motion(
            robot, cfg, case, manager, run_dir
        )
        print("[MOTION] Trajectory completed", flush=True)
        manager.event("MOTION_END")
        success = True
        result["status"] = "completed"

    except BaseException as exc:
        result["error"] = repr(exc)
        if connected:
            try:
                robot.robot_control.Stop()
            except Exception:
                pass
        raise

    finally:
        print("[LOGGING] Stopping acquisition and saving data", flush=True)
        result["logging"] = manager.stop()
        # Recorder failures mean lost measurements, not failed robot motion.
        # Keep the trial and proceed to the next case after safe homing.
        data_errors = {}
        for key in ("rigol_error", "camera_error"):
            if result["logging"].get(key):
                data_errors[key] = result["logging"][key]
        for key in ("rigol", "camera"):
            report = result["logging"].get(key, {})
            if isinstance(report, dict) and report.get("error"):
                data_errors[key] = report["error"]
        if data_errors and success:
            result["status"] = "partial"
            result["data_errors"] = data_errors
            print(f"[DATA WARNING] Partial recording: {data_errors}", flush=True)

        # A robot-feedback failure or observed fault/collision is not
        # recoverable data loss: stop the remaining physical movements.
        safety_errors = {}
        if result["logging"].get("robot_error"):
            safety_errors["robot_error"] = result["logging"]["robot_error"]
        feedback_stats = result["logging"].get("robot", {})
        if isinstance(feedback_stats, dict):
            for key in ("error_samples", "collision_samples"):
                if feedback_stats.get(key, 0):
                    safety_errors[key] = feedback_stats[key]
        if safety_errors:
            result["status"] = "failed"
            result["safety_errors"] = safety_errors
            success = False

        # Never attempt automatic recovery motion after a failed trial.
        if connected and success:
            try:
                check_response(robot.robot_control.SpeedFactor(cfg.slow_speed))
                slow_move(robot, cfg.home, CoordinateType.JOINT, cfg)
                result["error_ids"] = str(
                    robot.robot_control.GetErrorID()
                )
            except Exception as exc:
                result["status"] = "failed"
                result["home_error"] = repr(exc)

        if owns_robot:
            try:
                robot.robot_control.DisableRobot()
            except Exception as exc:
                result["disable_error"] = repr(exc)
                result["status"] = "failed"
            try:
                robot.Disconnect()
            except Exception as exc:
                result["disconnect_error"] = repr(exc)

        (run_dir/"result.json").write_text(
            json.dumps(result, indent=2, default=str),
            encoding="utf-8"
        )
    return result


def batch(cfg, experiment, cases, repetitions, execute=False):
    root = (
        Path(__file__).resolve().parents[1]
        / "results"
        / experiment
        / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    root.mkdir(parents=True, exist_ok=False)

    (root / "configuration.json").write_text(
        json.dumps(asdict(cfg), indent=2),
        encoding="utf-8",
    )

    total_cases = len(cases)
    total_trials = total_cases * repetitions
    completed = 0
    partial = 0
    failed = 0
    attempted = 0
    all_trials = []
    abort = False

    batch_start = time.perf_counter()

    def log(message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}", flush=True)

    def format_time(seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def case_description(case):
        parts = [f"Mode={case.get('mode', 'unknown')}"]

        for key, label in (
            ("speed", "Speed"),
            ("acceleration", "Acceleration"),
            ("payload_kg", "Payload kg"),
            ("csv_path", "Trajectory CSV"),
            ("minimum_duration_s", "Min duration s"),
            ("duration_s", "Planned duration s"),
            ("expected_peak_speed_mm_s", "Planned peak TCP mm/s"),
            ("aheadtime", "Aheadtime"),
            ("gain", "Gain"),
            ("global_speed_factor", "Global speed %"),
        ):
            if key in case and case[key] is not None:
                parts.append(f"{label}={case[key]}")

        for key in (
            "max_velocity",
            "max_acceleration",
            "max_jerk",
        ):
            if key in case:
                parts.append(f"{key}={case[key]}")

        return " | ".join(parts)

    log("=" * 66)
    log(f"EXPERIMENT: {experiment.upper()}")
    log(f"Parameter combinations: {total_cases}")
    log(f"Repetitions per combination: {repetitions}")
    log(f"TOTAL TRIALS: {total_trials}")
    log(f"Execution mode: {'REAL ROBOT' if execute else 'DRY RUN'}")
    log(f"Results: {root}")
    log("=" * 66)

    robot = None
    if execute:
        from dobot_sdk import DobotRobot
        robot = DobotRobot(cfg.robot_ip)
        robot.Connect()
        robot.robot_control.RequestControl()
        robot.robot_control.ClearError()
        robot.robot_control.EnableRobot()
        print("[ROBOT] Robot enabled once for the batch", flush=True)

    try:
        for case_index, case in enumerate(cases, start=1):
            matrix_index = int(case.get("matrix_case_index", case_index))
            matrix_count = int(case.get("matrix_case_count", total_cases))
            log("")
            log("-" * 66)
            log(f"TEST CASE {matrix_index}/{matrix_count}" +
                (f" (selected {case_index}/{total_cases})"
                 if matrix_count != total_cases else ""))
            log(case_description(case))
            log("-" * 66)

            for trial_index in range(1, repetitions + 1):
                global_index = (
                    (case_index - 1) * repetitions
                    + trial_index
                )

                remaining_before = total_trials - attempted

                folder = (
                    root
                    / f"case_{matrix_index:03d}"
                    / f"trial_{trial_index:03d}"
                )
                folder.mkdir(parents=True, exist_ok=False)

                (folder / "case.json").write_text(
                    json.dumps(case, indent=2),
                    encoding="utf-8",
                )

                log("")
                log(f">>> TRIAL {global_index}/{total_trials}")
                log(f"    Matrix case: {matrix_index}/{matrix_count}")
                log(f"    Repetition: {trial_index}/{repetitions}")
                log(f"    Trials remaining (including this): {remaining_before}")

                trial_start = time.perf_counter()

                record = {
                    "case": matrix_index,
                    "matrix_case_count": matrix_count,
                    "selected_case": case_index,
                    "trial": trial_index,
                    "global_trial": global_index,
                    "status": "planned",
                }
                for key in (
                    "aheadtime", "gain", "global_speed_factor",
                    "duration_s", "expected_points",
                    "expected_peak_speed_mm_s",
                    "expected_peak_acceleration_mm_s2",
                    "expected_peak_jerk_mm_s3",
                    "exceeds_movel_fast_speed",
                ):
                    if key in case:
                        record[key] = case[key]
                if case.get("mode") in ("movel", "movej"):
                    record["speed_percent"] = case.get("speed", 100)
                    record["acceleration_percent"] = case.get("acceleration", 100)
                    record["global_speed_factor"] = case.get(
                        "global_speed_factor", case.get("speed", 100)
                    )
                    record["command_v_percent"] = 100

                if case.get("exceeds_movel_fast_speed"):
                    log("    [CAUTION] Planned peak TCP speed exceeds the "
                        "fastest measured MoveL plateau (~470.5 mm/s). "
                        "Physical motion requires explicit safety review.")
                if execute:
                    try:
                        log("    [RUNNING] Robot and acquisition sequence")
                        result = run_trial(cfg, case, folder, robot=robot)
                        record["status"] = result["status"]

                        if record["status"] not in ("completed", "partial"):
                            abort = True

                    except BaseException as exc:
                        record["status"] = "failed"
                        record["error"] = repr(exc)
                        abort = True
                        log(f"    [ERROR] {exc!r}")

                    finally:
                        log("    [ANALYSIS] Calculating metrics")

                        try:
                            metrics = analyze_trial(folder)
                            record.update(metrics)
                            log("    [ANALYSIS] Metrics saved")
                        except Exception as exc:
                            record["analysis_error"] = repr(exc)
                            if record["status"] in ("completed", "partial") and not abort:
                                record["status"] = "partial"
                            else:
                                record["status"] = "failed"
                                abort = True
                            log(f"    [ANALYSIS ERROR] {exc!r}")

                attempted += 1

                if record["status"] == "completed":
                    completed += 1
                elif record["status"] == "partial":
                    partial += 1
                elif record["status"] == "failed":
                    failed += 1

                all_trials.append(record)

                elapsed_trial = time.perf_counter() - trial_start
                elapsed_total = time.perf_counter() - batch_start
                remaining = total_trials - attempted
                percent = 100.0 * attempted / total_trials

                log("")
                log(f"    STATUS: {record['status'].upper()}")
                log(f"    Trial duration: {format_time(elapsed_trial)}")
                log(f"    Progress: {attempted}/{total_trials} ({percent:.1f}%)")
                log(f"    Completed: {completed} | Partial: {partial} | Failed: {failed}")
                log(f"    Remaining: {remaining}")

                if attempted > 0 and not abort:
                    average_time = elapsed_total / attempted
                    estimated_remaining = average_time * remaining
                    log(
                        "    Estimated remaining time: "
                        f"{format_time(estimated_remaining)}"
                    )

                if abort:
                    log("")
                    log("BATCH STOPPED: A trial failed.")
                    log("Remaining movements will not execute.")
                    break

            if abort:
                break

        log("")
        log("[SUMMARY] Aggregating experiment results")
        aggregate(all_trials, root / "trial_summary.csv")
    finally:
        if robot is not None:
            try:
                robot.robot_control.DisableRobot()
                print("[ROBOT] Robot disabled once at batch end", flush=True)
            except Exception as exc:
                log(f"[ERROR] Robot disable failed: {exc!r}")
            try:
                robot.Disconnect()
            except Exception as exc:
                log(f"[ERROR] Robot disconnect failed: {exc!r}")

    log("=" * 66)
    log(f"EXPERIMENT FINISHED: {experiment.upper()}")
    log(f"Completed: {completed}/{total_trials}")
    log(f"Partial recordings: {partial}")
    log(f"Failed: {failed}")
    log(f"Not attempted: {total_trials - attempted}")
    log(f"Total elapsed: {format_time(time.perf_counter() - batch_start)}")
    log(f"Results saved: {root}")
    log("=" * 66)

    return root
