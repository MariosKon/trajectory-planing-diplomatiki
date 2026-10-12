#!/usr/bin/env python3
"""Recursive liquid free-surface analysis for the revised Final Results dataset.

Supported layouts
-----------------
New (preferred):
    <root>/<method>/<experiment_timestamp>/case_###/trial_###/camera.mkv
    <root>/<method>/<experiment_timestamp>/case_###/trial_###/events.csv
    <root>/<method>/<experiment_timestamp>/case_###/trial_###/case.json
    <root>/<method>/<experiment_timestamp>/case_###/trial_###/result.json
    <root>/<method>/<experiment_timestamp>/case_###/trial_###/camera_metadata.json

Legacy layouts with camera.mp4 are also accepted automatically.

For each trial, results are written next to the source data in:
    <trial>/liquid_analysis/
        surface_data.csv
        summary.csv
        angle_plot.png
        tracking_cropped.mp4
        fft_first_1s_motion.csv / .png
        fft_whole_motion.csv / .png
        fft_post_motion.csv / .png
        status.json

A dataset-level summary and calibration file are written at the dataset root.
Source videos and experiment files are never modified.

Timing / completion logic
-------------------------
Robot-motion start and stop are determined from the VIDEO, not from logger event
timestamps. This is deliberate because the camera and logger are not synchronized.
MOTION_START/MOTION_END (and legacy Servo events) are retained only as diagnostic
metadata; they never gate video processing. The coarse detector uses the two
calibrated image-space vessel endpoints and infers travel direction per video.
This prevents brief velocity spikes or unrelated red objects from being mistaken
for a complete traversal. Boundaries are then refined at native frame rate.

The post-motion FFT uses a fixed-duration window immediately after the visually
detected robot stop. By default it uses the first 1.0 s after motion ends:
    (visual_stop, visual_stop + 1.0 s]
There is no logger-based delay and no waiting period before this FFT window.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Optional
from fnmatch import fnmatch

import cv2
import numpy as np
import pandas as pd
import shutil
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt



# -------------------------- robust video timing -------------------------------

def _ffmpeg_progress_timing(video: Path):
    """Recover camera cadence from ffmpeg_camera_progress.txt.

    Some repaired Matroska files in this dataset advertise absurd rates such as
    90 kfps because packet timestamps were missing.  The ffmpeg progress log,
    however, contains repeated (frame, out_time_us) observations.  Their slope
    gives a robust effective frame rate independent of the bogus container tbr.
    """
    progress = video.with_name("ffmpeg_camera_progress.txt")
    if not progress.is_file():
        return None, None

    points = []
    current_frame = None
    try:
        for raw in progress.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("frame="):
                try:
                    current_frame = int(line.split("=", 1)[1].strip())
                except Exception:
                    current_frame = None
            elif line.startswith("out_time_us=") and current_frame is not None:
                try:
                    t = float(line.split("=", 1)[1].strip()) / 1e6
                    if np.isfinite(t) and t >= 0:
                        points.append((t, current_frame))
                except Exception:
                    pass
    except Exception:
        return None, None

    if not points:
        return None, None

    # De-duplicate times and use the overall slope.  The absolute timestamp
    # offset is irrelevant; only delta-frame / delta-time matters.
    clean = []
    for t, f in points:
        if not clean or t > clean[-1][0] + 1e-9:
            clean.append((t, f))
    final_frame_count = int(max(f for _, f in clean))

    fps = None
    if len(clean) >= 2:
        t0, f0 = clean[0]
        t1, f1 = clean[-1]
        dt = t1 - t0
        df = f1 - f0
        if dt > 0.25 and df >= 5:
            candidate = float(df / dt)
            if 5.0 <= candidate <= 120.0:
                fps = candidate

    return fps, final_frame_count


def _metadata_fps(video: Path):
    meta_path = video.with_name("camera_metadata.json")
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        frames = meta.get("camera_metadata_frame_count", None)
        if frames is None:
            frames = meta.get("frame_count", None)
        duration = meta.get("recorded_wall_duration_s", None)
        if frames is not None and duration is not None:
            candidate = float(frames) / float(duration)
            if 5.0 <= candidate <= 120.0:
                return candidate
    except Exception:
        pass
    return None


def reliable_video_fps(video: Path, cap=None):
    """Return (fps, source, raw_opencv_fps).

    Prefer OpenCV only when it is physically plausible and consistent with the
    ffmpeg progress cadence.  Otherwise use the progress-log cadence, then
    metadata, then a conservative 30 fps fallback.
    """
    own_cap = cap is None
    if cap is None:
        cap = cv2.VideoCapture(str(video))
    raw = float(cap.get(cv2.CAP_PROP_FPS)) if cap is not None else float("nan")
    if own_cap and cap is not None:
        cap.release()

    progress_fps, _ = _ffmpeg_progress_timing(video)
    meta_fps = _metadata_fps(video)

    raw_ok = np.isfinite(raw) and 5.0 <= raw <= 120.0
    prog_ok = progress_fps is not None and np.isfinite(progress_fps) and 5.0 <= progress_fps <= 120.0

    if raw_ok:
        if prog_ok:
            disagreement = abs(raw - progress_fps) / max(progress_fps, 1e-9)
            if disagreement > 0.15:
                return float(progress_fps), "ffmpeg_progress", raw
        return float(raw), "opencv", raw
    if prog_ok:
        return float(progress_fps), "ffmpeg_progress", raw
    if meta_fps is not None:
        return float(meta_fps), "camera_metadata", raw
    return 30.0, "fallback_30fps", raw


def _sequential_skip(cap, start_frame: int):
    """Advance from the beginning by decoded frames instead of random seeking.

    Random frame seeking can be unreliable in the repaired/VFR Matroska files.
    The videos are short, so sequentially skipping a few hundred frames is cheap
    and deterministic.
    """
    start_frame = max(0, int(start_frame))
    for _ in range(start_frame):
        if not cap.grab():
            return False
    return True



# ------------------------ OpenCV/Matroska compatibility ----------------------

def _metadata_frame_count(video: Path):
    meta_path = video.with_name("camera_metadata.json")
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        value = meta.get("frame_count", None)
        if value is None:
            value = meta.get("camera_metadata_frame_count", None)
        if value is not None:
            value = int(value)
            if value > 0:
                return value
    except Exception:
        pass
    return None


def _opencv_decode_probe(video: Path, wanted: int = 12) -> int:
    """Return how many initial frames OpenCV can decode sequentially."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return 0
    decoded = 0
    for _ in range(max(1, int(wanted))):
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        decoded += 1
    cap.release()
    return decoded


def prepare_video_source(video: Path, out_dir: Path):
    """Return an OpenCV-decodable video path and diagnostic information.

    Some early camera.mkv files in this dataset contain H.264 frames but invalid
    or unset Matroska packet timestamps.  FFmpeg itself can decode those files,
    while some OpenCV/FFmpeg builds stop after only a few frames.  If OpenCV
    fails a short sequential probe despite metadata/progress showing a normal
    recording, create a cached compatibility MP4 with synthetic constant-rate
    timestamps.  Every decoded source frame is kept in order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fps_hint, fps_source, raw_fps = reliable_video_fps(video)
    expected_meta = _metadata_frame_count(video)
    _, expected_progress = _ffmpeg_progress_timing(video)
    expected = expected_meta or expected_progress

    probe = _opencv_decode_probe(video, wanted=12)
    # A normal recording should trivially decode twelve leading frames.  Do not
    # normalize genuinely tiny videos unless metadata says they should be long.
    if probe >= 6 or (expected is not None and expected < 12 and probe >= 2):
        return video, {
            "video_decode_source": "original",
            "opencv_probe_frames": int(probe),
            "expected_frames_hint": expected,
            "original_fps_hint": float(fps_hint),
            "original_fps_hint_source": fps_source,
            "original_raw_opencv_fps": raw_fps,
        }

    if expected is None or expected < 30:
        # No evidence that this is the known malformed-timestamp case.
        return video, {
            "video_decode_source": "original_probe_weak",
            "opencv_probe_frames": int(probe),
            "expected_frames_hint": expected,
            "original_fps_hint": float(fps_hint),
            "original_fps_hint_source": fps_source,
            "original_raw_opencv_fps": raw_fps,
        }

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "OpenCV cannot decode this MKV and ffmpeg was not found. "
            "Install ffmpeg (Ubuntu/Debian: sudo apt install ffmpeg) and rerun."
        )

    cache = out_dir / "_opencv_compatibility.mp4"
    reuse = False
    if cache.is_file():
        try:
            reuse = cache.stat().st_mtime >= video.stat().st_mtime and _opencv_decode_probe(cache, 12) >= 6
        except Exception:
            reuse = False

    if not reuse:
        fps_arg = f"{float(fps_hint):.8f}"
        # setpts=N/(fps*TB) deliberately ignores broken source timestamps and
        # assigns time strictly from decoded frame order.  This preserves every
        # decoded frame while making the stream easy for OpenCV to consume.
        vf = f"setpts=N/({fps_arg}*TB)"
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-fflags", "+genpts+discardcorrupt",
            "-i", str(video),
            "-map", "0:v:0", "-an",
            "-vf", vf,
            "-r", fps_arg,
            "-fps_mode", "cfr",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(cache),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0 or not cache.is_file():
            tail = (proc.stderr or "").strip().splitlines()[-8:]
            raise RuntimeError(
                "OpenCV cannot decode this MKV and automatic ffmpeg normalization failed: "
                + " | ".join(tail)
            )
        normalized_probe = _opencv_decode_probe(cache, 12)
        if normalized_probe < 6:
            raise RuntimeError(
                f"ffmpeg created a compatibility video, but OpenCV still decoded only "
                f"{normalized_probe} probe frame(s)"
            )

    return cache, {
        "video_decode_source": "ffmpeg_normalized_cache" if reuse else "ffmpeg_normalized",
        "opencv_probe_frames": int(probe),
        "expected_frames_hint": expected,
        "original_fps_hint": float(fps_hint),
        "original_fps_hint_source": fps_source,
        "original_raw_opencv_fps": raw_fps,
        "compatibility_video": str(cache.name),
    }

# ------------------------- vessel + liquid detection -------------------------

def _largest_true_run(bits: np.ndarray):
    """Return inclusive (start, end) of the longest True run in a 1-D mask."""
    idx = np.flatnonzero(bits)
    if len(idx) == 0:
        return None
    best_s = best_e = s = prev = int(idx[0])
    for value in idx[1:]:
        value = int(value)
        if value <= prev + 1:
            prev = value
        else:
            if prev - s > best_e - best_s:
                best_s, best_e = s, prev
            s = prev = value
    if prev - s > best_e - best_s:
        best_s, best_e = s, prev
    return best_s, best_e


def _red_base_candidates(frame: np.ndarray):
    """Find plausible horizontal red vessel-base rectangles.

    The old detector selected the single reddest image row. In some robot poses,
    a red/brown object near y~694 became stronger than the actual holder, so an
    otherwise visible vessel was reported as missing. This detector instead
    finds red connected components and extracts their horizontal base band.
    """
    h_img, w_img = frame.shape[:2]
    ry0 = max(0, min(430, h_img - 1))
    ry1 = min(h_img, 720)
    rx0 = 0
    rx1 = min(w_img, 900)
    roi = frame[ry0:ry1, rx0:rx1]
    if roi.size == 0:
        return []

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Slightly more tolerant than the original mask to survive motion blur.
    m1 = cv2.inRange(hsv, (0, 65, 40), (15, 255, 255))
    m2 = cv2.inRange(hsv, (165, 65, 40), (179, 255, 255))
    mask = cv2.bitwise_or(m1, m2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 7), np.uint8))

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    for label in range(1, n_labels):
        x, y, w, h, area = map(int, stats[label])
        if area < 250 or w < 40 or w > 160 or h < 10 or h > 100:
            continue

        component = labels[y:y + h, x:x + w] == label
        row_widths = np.zeros(h, dtype=int)
        row_runs = [None] * h
        for yy in range(h):
            run = _largest_true_run(component[yy])
            row_runs[yy] = run
            if run is not None:
                row_widths[yy] = run[1] - run[0] + 1

        # Rows belonging to the horizontal holder base. This works even when
        # the base merges with another red region into a taller component.
        min_row_width = max(40, min(65, int(round(0.55 * w))))
        good_rows = row_widths >= min_row_width
        if h >= 3:
            good_rows = cv2.morphologyEx(
                good_rows.astype(np.uint8).reshape(-1, 1),
                cv2.MORPH_CLOSE,
                np.ones((3, 1), np.uint8),
            ).ravel().astype(bool)
        band = _largest_true_run(good_rows)
        if band is None:
            continue
        ys, ye = band
        band_h = ye - ys + 1
        if band_h < 8 or band_h > 60:
            continue

        lefts, rights = [], []
        for yy in range(ys, ye + 1):
            run = row_runs[yy]
            if run is not None and run[1] - run[0] + 1 >= 30:
                lefts.append(run[0])
                rights.append(run[1])
        if not lefts:
            continue

        xx0 = int(round(float(np.median(lefts))))
        xx1 = int(round(float(np.median(rights))))
        bx = rx0 + x + xx0
        by = ry0 + y + ys
        bw = xx1 - xx0 + 1
        bh = band_h
        if bw < 40 or bw > 140:
            continue

        cy = by + bh / 2.0
        # Geometry-only score. A temporal hint is added in red_base_bbox().
        score = (
            1000.0
            - 7.0 * abs(bw - 85)
            - 4.0 * abs(bh - 30)
            - 1.5 * abs(cy - 605.0)
            + 0.02 * area
        )
        candidates.append((score, (int(bx), int(by), int(bw), int(bh))))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def red_base_bbox(frame: np.ndarray, hint=None, endpoint_xs=None):
    """Return (x, y, w, h) for the red vessel base.

    If a previous-frame bbox is supplied, temporal continuity is used only as
    a tie-breaker/guard against other red objects in the scene.
    """
    candidates = _red_base_candidates(frame)
    if not candidates:
        return None
    if hint is None:
        # At the beginning of every trial the vessel should be settled at one
        # of the two calibrated path endpoints. Use that strong geometric prior
        # to avoid latching onto an unrelated red object on frame 1.
        if endpoint_xs is not None:
            xs = [float(v) for v in endpoint_xs if v is not None and np.isfinite(v)]
            if xs:
                rescored = []
                for base_score, bbox in candidates:
                    x, y, w, h = bbox
                    cx = x + w / 2.0
                    endpoint_distance = min(abs(cx - ex) for ex in xs)
                    rescored.append((base_score - 10.0 * endpoint_distance, bbox))
                return max(rescored, key=lambda item: item[0])[1]
        return candidates[0][1]

    hx, hy, hw, hh = hint
    hcx = hx + hw / 2.0
    hcy = hy + hh / 2.0
    rescored = []
    for base_score, bbox in candidates:
        x, y, w, h = bbox
        cx = x + w / 2.0
        cy = y + h / 2.0
        distance = math.hypot(cx - hcx, cy - hcy)
        rescored.append((base_score - 4.0 * distance, bbox))
    return max(rescored, key=lambda item: item[0])[1]

def robust_surface_fit(frame: np.ndarray, bbox):
    """Fit y = slope*x + intercept to the dark-liquid upper surface."""
    x, y, w, h = bbox
    margin = max(3, int(round((w - 73) / 2))) if w > 73 else 3
    x_start = max(0, x + margin)
    x_stop = min(frame.shape[1], x + w - margin)
    y0 = max(0, y - 75)
    y1 = min(frame.shape[0], max(y0 + 2, y - 22))
    if x_stop - x_start < 20 or y1 - y0 < 8:
        return None

    patch = frame[y0:y1, x_start:x_stop]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

    # Vectorized strongest negative vertical gradient for each x-column.
    jj = np.argmin(gy, axis=0)
    cols = np.arange(gy.shape[1])
    xs = (x_start + cols).astype(float)
    ys = (y0 + jj).astype(float)
    strengths = (-gy[jj, cols]).astype(float)
    good = strengths >= np.percentile(strengths, 15)

    for _ in range(6):
        if int(good.sum()) < 20:
            break
        p = np.polyfit(xs[good], ys[good], 1)
        residual = ys - (p[0] * xs + p[1])
        med = float(np.median(residual[good]))
        mad = float(np.median(np.abs(residual[good] - med)))
        sigma = 1.4826 * mad
        cutoff = max(1.5, 3.0 * sigma)
        new_good = good & (np.abs(residual - med) <= cutoff)
        if int(new_good.sum()) < 20 or np.array_equal(new_good, good):
            break
        good = new_good

    if int(good.sum()) < 10:
        return None
    p = np.polyfit(xs[good], ys[good], 1)
    residual = ys[good] - (p[0] * xs[good] + p[1])
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    span = float(xs[good].max() - xs[good].min())
    center_x = x + w / 2.0
    center_y = float(p[0] * center_x + p[1])
    return {
        "slope": float(p[0]), "intercept": float(p[1]),
        "angle_deg": float(np.degrees(np.arctan(p[0]))),
        "rmse_px": rmse, "fit_points": int(good.sum()),
        "fit_span_px": span, "surface_y_at_center_px": center_y,
    }

def qc_label(rmse: float, points: float, span: float) -> str:
    if not np.isfinite(rmse):
        return "BAD"
    if rmse <= 0.8 and points >= 40 and span >= 55:
        return "GOOD"
    if rmse <= 1.5 and points >= 25 and span >= 40:
        return "CHECK"
    return "BAD"


# ----------------------------- run validation --------------------------------

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def read_events(run_dir: Path) -> dict:
    """Read both the revised MOTION_START/MOTION_END convention and legacy events."""
    path = run_dir / "events.csv"
    out = {
        "events_present": False,
        "motion_start_event": False,
        "motion_end_event": False,
        "servo_finished": None,
        "event_motion_duration_s": np.nan,
        "event_completion_ok": None,
        "event_completion_rule": "NO_EVENTS",
    }
    if not path.exists():
        return out

    try:
        e = pd.read_csv(path)
        out["events_present"] = True
        names = e.get("event", pd.Series(dtype=str)).astype(str).str.strip()

        has_motion_start = bool((names == "MOTION_START").any())
        has_motion_end = bool((names == "MOTION_END").any())
        has_servo_first = bool((names == "FIRST_SERVO_POINT").any()) or bool((names == "SERVO_FIRST_COMMAND_SENT").any())
        has_servo_finish = bool((names == "SERVO_FINISHED").any())

        out["motion_start_event"] = has_motion_start
        out["motion_end_event"] = has_motion_end
        out["servo_finished"] = has_servo_finish

        # Revised dataset: MOTION_END is the completion signal for every motion
        # family, including MoveL, cubic, quintic and ServoP experiments.
        if has_motion_start:
            out["event_completion_rule"] = "MOTION_END"
            out["event_completion_ok"] = has_motion_end
            if has_motion_end and "host_time_s" in e.columns:
                t0 = float(e.loc[names == "MOTION_START", "host_time_s"].iloc[0])
                t1 = float(e.loc[names == "MOTION_END", "host_time_s"].iloc[-1])
                out["event_motion_duration_s"] = t1 - t0
        # Legacy ServoP fallback.
        elif has_servo_first:
            out["event_completion_rule"] = "SERVO_FINISHED_LEGACY"
            out["event_completion_ok"] = has_servo_finish
            if has_servo_finish and "host_time_s" in e.columns:
                first_name = "FIRST_SERVO_POINT" if bool((names == "FIRST_SERVO_POINT").any()) else "SERVO_FIRST_COMMAND_SENT"
                t0 = float(e.loc[names == first_name, "host_time_s"].iloc[0])
                t1 = float(e.loc[names == "SERVO_FINISHED", "host_time_s"].iloc[-1])
                out["event_motion_duration_s"] = t1 - t0
        else:
            # No recognized completion convention: do not reject automatically.
            out["event_completion_rule"] = "EVENTS_DIAGNOSTIC_ONLY"
            out["event_completion_ok"] = None
    except Exception:
        pass
    return out


def identify_run(run_dir: Path, root: Path) -> dict:
    """Identify method / experiment / case / trial from the directory hierarchy."""
    try:
        parts = list(run_dir.relative_to(root).parts)
    except Exception:
        parts = list(run_dir.parts)

    out = {
        "method": "",
        "experiment_id": "",
        "case_id": "",
        "trial_id": run_dir.name,
        "dataset_schema": "legacy",
    }

    # New schema ends in .../<method>/<experiment>/case_###/trial_###
    if len(parts) >= 4 and parts[-1].lower().startswith("trial_") and parts[-2].lower().startswith("case_"):
        out.update({
            "method": parts[-4],
            "experiment_id": parts[-3],
            "case_id": parts[-2],
            "trial_id": parts[-1],
            "dataset_schema": "final_results_v2",
        })
    else:
        if len(parts) >= 2:
            out["method"] = parts[-2]
        elif parts:
            out["method"] = parts[0]
    return out


def read_metadata(run_dir: Path, root: Optional[Path] = None) -> dict:
    """Collect useful metadata without making it a processing dependency."""
    out = {}

    # Legacy metadata.json.
    legacy = _read_json(run_dir / "metadata.json")
    cfg = legacy.get("config", {}) if isinstance(legacy.get("config", {}), dict) else {}
    for key in ["servo_mode", "servo_time_s", "aheadtime", "gain", "payload_kg"]:
        if key in cfg:
            out[key] = cfg.get(key)

    # Revised per-trial case description.
    case = _read_json(run_dir / "case.json")
    if case:
        out["case_name"] = case.get("name")
        out["motion_mode"] = case.get("mode")
        for key in [
            "duration_s", "expected_points", "expected_peak_speed_mm_s",
            "expected_peak_acceleration_mm_s2", "expected_peak_jerk_mm_s3",
            "global_speed_factor", "speed", "acceleration",
        ]:
            if key in case:
                out[f"case_{key}"] = case.get(key)

    # result.json is diagnostic. Do not use result_status as a robot-completion
    # gate because "partial" can mean a Rigol/power-data problem only.
    result = _read_json(run_dir / "result.json")
    if result:
        out["result_status"] = result.get("status")
        motion = result.get("motion", {}) if isinstance(result.get("motion", {}), dict) else {}
        for src_key, dst_key in [
            ("elapsed_s", "result_motion_elapsed_s"),
            ("planned_trajectory_duration_s", "result_planned_trajectory_duration_s"),
            ("global_speed_factor", "result_global_speed_factor"),
            ("speed_percent", "result_speed_percent"),
            ("acceleration_percent", "result_acceleration_percent"),
            ("effective_aheadtime", "result_effective_aheadtime"),
            ("effective_gain", "result_effective_gain"),
        ]:
            if src_key in motion:
                out[dst_key] = motion.get(src_key)
        data_errors = result.get("data_errors")
        if data_errors:
            out["result_has_data_errors"] = True
            out["result_data_errors"] = json.dumps(data_errors, ensure_ascii=False)
        else:
            out["result_has_data_errors"] = False

    cam = _read_json(run_dir / "camera_metadata.json")
    if cam:
        out["camera_recorded_wall_duration_s"] = cam.get("recorded_wall_duration_s")
        out["camera_metadata_frame_count"] = cam.get("frame_count")
        out["camera_metadata_error"] = cam.get("error")
        validation = cam.get("video_validation", {}) if isinstance(cam.get("video_validation", {}), dict) else {}
        out["camera_validation"] = validation.get("validation")
        out["camera_decoded_frames"] = validation.get("decoded_frames")

    return out


def is_movel_run(run_dir: Path, meta: dict) -> bool:
    """Recognize MoveL from case metadata or any directory-name variant."""
    def normalized(value) -> str:
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    for key in ["motion_mode", "servo_mode", "case_name"]:
        if normalized(meta.get(key, "")) == "movel":
            return True
    return any("movel" in normalized(part) for part in run_dir.parts)


# ------------------------------ motion timing --------------------------------

def _merge_true_runs(mask: np.ndarray, max_gap: int) -> list[tuple[int, int]]:
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    runs = []
    s = p = int(idx[0])
    for ii in idx[1:]:
        ii = int(ii)
        if ii - p <= max_gap + 1:
            p = ii
        else:
            runs.append((s, p))
            s = p = ii
    runs.append((s, p))
    return runs


def track_vessel(video: Path, scan_fps: float = 10.0, endpoint_xs=None) -> tuple[pd.DataFrame, float, int, int, int]:
    """Track vessel at a reduced sampling rate for fast motion-window detection.

    The sampling cadence uses a sanitized FPS.  This is important for the revised
    dataset because some Matroska files report bogus OpenCV FPS values (for
    example 90000) when source packet timestamps are malformed.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")

    fps, fps_source, raw_fps = reliable_video_fps(video, cap)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    stride = max(1, int(round(fps / max(1.0, scan_fps))))

    rows = []
    i = 0
    prev_bbox = None
    last_decoded = None
    while True:
        ok = cap.grab()
        if not ok:
            break
        take = (i % stride == 0)
        if take:
            ok2, frame = cap.retrieve()
            if not ok2:
                break
            b = red_base_bbox(frame, prev_bbox, endpoint_xs=endpoint_xs)
            if b is None:
                rows.append((i, i / fps, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan))
            else:
                prev_bbox = b
                x, y, w, h = b
                rows.append((i, i / fps, x, y, w, h, x + w / 2.0, y + h / 2.0))
            last_decoded = i
        i += 1
    cap.release()

    # `i` is the number of frames OpenCV could actually decode.  Do not trust
    # CAP_PROP_FRAME_COUNT on malformed-timestamp MKVs.
    n_frames = int(i)
    track = pd.DataFrame(rows, columns=[
        "frame", "time_s", "base_x", "base_y", "base_w", "base_h",
        "base_center_x", "base_center_y",
    ])
    track.attrs["fps_source"] = fps_source
    track.attrs["raw_opencv_fps"] = raw_fps
    track.attrs["decoded_frame_count"] = n_frames
    return track, fps, width, height, n_frames


def track_vessel_frame_range(video: Path, start_frame: int, end_frame: int, fps: float,
                             endpoint_xs=None) -> pd.DataFrame:
    """Track the red vessel base at EVERY frame in a limited interval.

    This is used only to refine coarse motion boundaries, so it keeps the speed of
    the 10 fps full-video scan while recovering native-frame timing precision.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")
    start_frame = max(0, int(start_frame))
    end_frame = max(start_frame, int(end_frame))
    if not _sequential_skip(cap, start_frame):
        cap.release()
        return pd.DataFrame(columns=["frame", "time_s", "base_center_x", "base_center_y"])

    rows = []
    prev_bbox = None
    frame_no = start_frame
    while frame_no <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        bbox = red_base_bbox(frame, prev_bbox, endpoint_xs=endpoint_xs)
        if bbox is None:
            rows.append((frame_no, frame_no / fps, np.nan, np.nan))
        else:
            prev_bbox = bbox
            x, y, w, h = bbox
            rows.append((frame_no, frame_no / fps, x + w / 2.0, y + h / 2.0))
        frame_no += 1
    cap.release()
    return pd.DataFrame(rows, columns=["frame", "time_s", "base_center_x", "base_center_y"])


def refine_motion_boundaries(video: Path, coarse: dict, fps: float, n_frames: int,
                             margin_s: float = 1.0, endpoint_xs=None) -> dict:
    """Refine coarse start/stop from the video at native frame rate.

    The vessel path is projected onto the line between its initial and final resting
    positions. Motion start is the first sustained departure from the initial rest
    position; motion end is the first sustained arrival at the final rest position.
    No logger timestamps are used.
    """
    coarse_s = int(coarse["motion_start_frame"])
    coarse_e = int(coarse["motion_end_frame"])
    margin = max(int(round(float(margin_s) * fps)), int(round(0.5 * fps)))
    start = max(0, coarse_s - margin)
    end = min(max(0, n_frames - 1), coarse_e + margin)

    tr = track_vessel_frame_range(video, start, end, fps, endpoint_xs=endpoint_xs)
    if len(tr) < max(12, int(round(0.6 * fps))):
        return {**coarse, "boundary_refinement": "COARSE_FALLBACK_TOO_SHORT"}

    xy = tr[["base_center_x", "base_center_y"]].copy()
    detected_fraction = float(xy.notna().all(axis=1).mean())
    # Short detection gaps are safe to interpolate for the kinematic boundary
    # estimate. Long/terminal gaps still cause a fallback below.
    limit = max(2, int(round(0.20 * fps)))
    xy = xy.interpolate(limit=limit, limit_direction="both")
    if xy.isna().any().any():
        return {**coarse,
                "boundary_refinement": "COARSE_FALLBACK_TRACK_GAPS",
                "refine_detection_fraction": detected_fraction}

    smooth_n = max(3, int(round(0.10 * fps)))
    if smooth_n % 2 == 0:
        smooth_n += 1
    sm = xy.rolling(smooth_n, center=True, min_periods=1).median().to_numpy(float)
    frames = tr["frame"].to_numpy(int)

    # Stable endpoint windows live inside the refinement margins.
    stable_n = max(5, int(round(0.30 * fps)))
    stable_n = min(stable_n, max(3, len(sm) // 4))
    p0 = np.median(sm[:stable_n], axis=0)
    p1 = np.median(sm[-stable_n:], axis=0)
    vec = p1 - p0
    span = float(np.linalg.norm(vec))
    if not np.isfinite(span) or span < 20.0:
        return {**coarse,
                "boundary_refinement": "COARSE_FALLBACK_SMALL_SPAN",
                "refine_detection_fraction": detected_fraction}

    unit = vec / span
    q = (sm - p0) @ unit
    q0 = float(np.median(q[:stable_n]))
    q1 = float(np.median(q[-stable_n:]))
    travel = q1 - q0
    if travel < 0:
        q = -q
        q0 = -q0
        q1 = -q1
        travel = -travel

    def mad_sigma(values: np.ndarray) -> float:
        med = float(np.median(values))
        mad = float(np.median(np.abs(values - med)))
        return 1.4826 * mad

    start_noise = mad_sigma(q[:stable_n])
    end_noise = mad_sigma(q[-stable_n:])
    # ~0.4% of path gives a few pixels on the present camera geometry, while
    # noise terms protect against false boundaries from sub-pixel tracker jitter.
    start_tol = max(2.0, 0.004 * travel, 5.0 * start_noise)
    end_tol = max(2.0, 0.004 * travel, 5.0 * end_noise)
    sustain = max(3, int(round(0.10 * fps)))

    # Search after the initial stable window. Require sustained departure rather
    # than a single threshold crossing.
    s_i = None
    for i in range(max(1, stable_n - 1), len(q) - sustain + 1):
        block = q[i:i + sustain]
        if np.all(block >= q0 + 0.55 * start_tol) and np.max(block) >= q0 + start_tol:
            s_i = i
            break

    # Search for sustained arrival at the final endpoint, starting well after
    # motion began to avoid accidental proximity to the target in noisy data.
    e_i = None
    if s_i is not None:
        search_from = max(s_i + sustain, int(round(0.35 * len(q))))
        for i in range(search_from, len(q) - sustain + 1):
            block = q[i:i + sustain]
            if np.all(np.abs(block - q1) <= 1.5 * end_tol) and np.median(block) >= q1 - end_tol:
                e_i = i
                break

    if s_i is None or e_i is None or e_i <= s_i:
        return {**coarse,
                "boundary_refinement": "COARSE_FALLBACK_NO_STABLE_CROSSING",
                "refine_detection_fraction": detected_fraction,
                "refine_path_span_px": span,
                "refine_start_tol_px": start_tol,
                "refine_end_tol_px": end_tol}

    s_frame = int(frames[s_i])
    # Arrival starts at e_i; the previous frame is the last clearly moving frame.
    e_frame = max(s_frame + 1, int(frames[e_i]) - 1)
    return {
        **coarse,
        "coarse_motion_start_frame": coarse_s,
        "coarse_motion_end_frame": coarse_e,
        "coarse_motion_start_s": coarse_s / fps,
        "coarse_motion_end_s": coarse_e / fps,
        "motion_start_frame": s_frame,
        "motion_end_frame": e_frame,
        "motion_start_s": s_frame / fps,
        "motion_end_s": e_frame / fps,
        "motion_duration_s": (e_frame - s_frame + 1) / fps,
        "boundary_refinement": "VIDEO_NATIVE_FPS",
        "refine_detection_fraction": detected_fraction,
        "refine_path_span_px": span,
        "refine_start_tol_px": start_tol,
        "refine_end_tol_px": end_tol,
    }


def detect_robot_motion(track: pd.DataFrame, fps: float, speed_threshold_px_s: float = 10.0) -> dict:
    if len(track) < 6:
        raise RuntimeError("Video is too short for motion detection")

    xy = track[["base_center_x", "base_center_y"]].copy().interpolate(limit_direction="both")
    if xy.isna().any().any():
        raise RuntimeError("Vessel tracking failed in too many sampled frames")
    times = track["time_s"].to_numpy(float)
    frames = track["frame"].to_numpy(int)
    dt_med = float(np.median(np.diff(times))) if len(times) > 1 else 1.0 / fps
    sample_rate = 1.0 / max(dt_med, 1e-6)

    smooth_n = max(3, int(round(0.20 * sample_rate)))
    if smooth_n % 2 == 0:
        smooth_n += 1
    sm = xy.rolling(smooth_n, center=True, min_periods=1).median().to_numpy(float)
    vel = np.zeros(len(sm), dtype=float)
    if len(sm) > 1:
        dxy = np.linalg.norm(np.diff(sm, axis=0), axis=1)
        dts = np.maximum(np.diff(times), 1e-6)
        vel[1:] = dxy / dts
    vn = max(3, int(round(0.12 * sample_rate)))
    vel = pd.Series(vel).rolling(vn, center=True, min_periods=1).median().to_numpy()

    early = max(3, int(round(0.8 * sample_rate)))
    noise = float(np.nanmedian(vel[:early]))
    threshold = max(float(speed_threshold_px_s), noise + 8.0)
    runs = _merge_true_runs(vel >= threshold, max_gap=max(1, int(round(0.20 * sample_rate))))
    min_len = max(2, int(round(0.25 * sample_rate)))
    runs = [r for r in runs if (r[1] - r[0] + 1) >= min_len]

    if runs:
        s_i, e_i = max(runs, key=lambda r: float(np.nansum(vel[r[0]:r[1] + 1])))
        low = max(2.0, 0.20 * threshold)
        while s_i > 1 and vel[s_i - 1] >= low:
            s_i -= 1
        while e_i + 1 < len(vel) and vel[e_i + 1] >= low:
            e_i += 1
    else:
        k = max(3, int(round(0.5 * sample_rate)))
        p0 = np.median(sm[:k], axis=0)
        p1 = np.median(sm[-k:], axis=0)
        span = float(np.linalg.norm(p1 - p0))
        tol = max(5.0, 0.01 * span)
        d0 = np.linalg.norm(sm - p0, axis=1)
        d1 = np.linalg.norm(sm - p1, axis=1)
        sustain = max(2, int(round(0.15 * sample_rate)))
        s_i = next((i for i in range(len(sm)-sustain+1) if np.all(d0[i:i+sustain] > tol)), None)
        e_i = None if s_i is None else next((i for i in range(s_i+sustain, len(sm)-sustain+1) if np.all(d1[i:i+sustain] <= tol)), None)
        if s_i is None or e_i is None:
            raise RuntimeError("Could not detect a clear robot movement interval")

    k = max(3, int(round(0.5 * sample_rate)))
    p0 = np.median(sm[:k], axis=0)
    p1 = np.median(sm[-k:], axis=0)
    endpoint_span = float(np.linalg.norm(p1 - p0))
    s_frame = int(frames[s_i])
    e_frame = int(frames[e_i])
    return {
        "motion_start_frame": s_frame, "motion_end_frame": e_frame,
        "motion_start_s": s_frame / fps, "motion_end_s": e_frame / fps,
        "motion_duration_s": (e_frame - s_frame + 1) / fps,
        "endpoint_span_px": endpoint_span, "motion_speed_threshold_px_s": threshold,
        "motion_detection_method": "VELOCITY_OR_LOCAL_ENDPOINTS",
    }


def detect_robot_motion_calibrated_endpoints(track: pd.DataFrame, fps: float,
                                             endpoint_xs,
                                             speed_threshold_px_s: float = 10.0) -> dict:
    """Detect the complete vessel traversal using calibrated image endpoints.

    Camera and robot logger clocks are not assumed synchronized. This detector
    therefore uses video positions only. The two calibrated x endpoints are
    geometric references; each video independently determines travel direction.
    """
    if len(track) < 6:
        raise RuntimeError("Video is too short for motion detection")

    xs = [float(v) for v in (endpoint_xs or []) if v is not None and np.isfinite(v)]
    if len(xs) < 2 or abs(xs[1] - xs[0]) < 20.0:
        return detect_robot_motion(track, fps, speed_threshold_px_s)

    cal_lo, cal_hi = min(xs), max(xs)
    cal_span = cal_hi - cal_lo
    times = track["time_s"].to_numpy(float)
    frames = track["frame"].to_numpy(int)
    dt_med = float(np.median(np.diff(times))) if len(times) > 1 else 1.0 / fps
    sample_rate = 1.0 / max(dt_med, 1e-6)

    xraw = pd.to_numeric(track["base_center_x"], errors="coerce")
    detection_fraction = float(xraw.notna().mean())
    if detection_fraction < 0.55:
        return detect_robot_motion(track, fps, speed_threshold_px_s)
    x = xraw.interpolate(limit=max(2, int(round(0.35 * sample_rate))),
                         limit_direction="both")
    if x.isna().any():
        return detect_robot_motion(track, fps, speed_threshold_px_s)

    smooth_n = max(3, int(round(0.20 * sample_rate)))
    if smooth_n % 2 == 0:
        smooth_n += 1
    sm = x.rolling(smooth_n, center=True, min_periods=1).median().to_numpy(float)

    stable_n = max(3, int(round(0.70 * sample_rate)))
    stable_n = min(stable_n, max(3, len(sm) // 4))
    early_x = float(np.median(sm[:stable_n]))
    late_x = float(np.median(sm[-stable_n:]))

    endpoints = np.array([cal_lo, cal_hi], dtype=float)
    start_idx = int(np.argmin(np.abs(endpoints - early_x)))
    target_idx = int(np.argmin(np.abs(endpoints - late_x)))
    start_x = float(endpoints[start_idx])
    target_x = float(endpoints[target_idx])
    early_err = abs(early_x - start_x)
    late_err = abs(late_x - target_x)

    endpoint_accept = max(45.0, 0.12 * cal_span)
    if start_idx == target_idx or early_err > endpoint_accept or late_err > endpoint_accept:
        legacy = detect_robot_motion(track, fps, speed_threshold_px_s)
        legacy["calibrated_endpoint_start_error_px"] = early_err
        legacy["calibrated_endpoint_end_error_px"] = late_err
        legacy["calibrated_endpoint_track_fraction"] = detection_fraction
        return legacy

    direction = 1.0 if target_x > start_x else -1.0
    progress_px = direction * (sm - start_x)
    travel = abs(target_x - start_x)
    depart_px = max(5.0, 0.012 * travel)
    arrive_px = max(8.0, 0.025 * travel)
    sustain = max(2, int(round(0.18 * sample_rate)))

    s_i = None
    for i in range(max(1, stable_n - 1), len(sm) - sustain + 1):
        block = progress_px[i:i + sustain]
        if np.all(block >= 0.65 * depart_px) and np.max(block) >= depart_px:
            s_i = i
            break

    e_i = None
    if s_i is not None:
        target_progress = travel
        for i in range(s_i + sustain, len(sm) - sustain + 1):
            block = progress_px[i:i + sustain]
            if np.all(np.abs(block - target_progress) <= 1.5 * arrive_px) and \
                    np.median(block) >= target_progress - arrive_px:
                e_i = i
                break

    if s_i is None or e_i is None or e_i <= s_i:
        legacy = detect_robot_motion(track, fps, speed_threshold_px_s)
        legacy["calibrated_endpoint_start_error_px"] = early_err
        legacy["calibrated_endpoint_end_error_px"] = late_err
        legacy["calibrated_endpoint_track_fraction"] = detection_fraction
        return legacy

    s_frame = int(frames[s_i])
    e_frame = int(frames[max(s_i + 1, e_i - 1)])
    observed_span = abs(late_x - early_x)
    return {
        "motion_start_frame": s_frame,
        "motion_end_frame": e_frame,
        "motion_start_s": s_frame / fps,
        "motion_end_s": e_frame / fps,
        "motion_duration_s": (e_frame - s_frame + 1) / fps,
        "endpoint_span_px": observed_span,
        "motion_speed_threshold_px_s": np.nan,
        "motion_detection_method": "CALIBRATED_ENDPOINTS",
        "calibrated_start_endpoint_x": start_x,
        "calibrated_target_endpoint_x": target_x,
        "calibrated_endpoint_start_error_px": early_err,
        "calibrated_endpoint_end_error_px": late_err,
        "calibrated_endpoint_track_fraction": detection_fraction,
    }


# ------------------------- free surface measurements -------------------------

def analyze_frame_range(video: Path, start_frame: int, end_frame: int, fps: float) -> pd.DataFrame:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")
    if not _sequential_skip(cap, int(start_frame)):
        cap.release()
        return pd.DataFrame()
    rows = []
    frame_no = int(start_frame)
    prev_bbox = None
    while frame_no <= int(end_frame):
        ok, frame = cap.read()
        if not ok:
            break
        bbox = red_base_bbox(frame, prev_bbox)
        if bbox is None:
            rows.append({
                "original_frame": frame_no, "original_time_s": frame_no / fps,
                "vessel_detected": 0, "surface_fit_valid": 0,
                "failure_reason": "VESSEL_NOT_FOUND",
                "valid": 0, "base_x": np.nan, "base_y": np.nan,
                "base_w": np.nan, "base_h": np.nan, "base_center_x": np.nan,
                "base_center_y": np.nan, "surface_slope_image_dy_dx": np.nan,
                "surface_angle_image_deg": np.nan, "surface_y_at_center_px": np.nan,
                "fit_rmse_px": np.nan, "fit_points": 0, "fit_span_px": 0.0,
                "quality": "BAD",
            })
        else:
            prev_bbox = bbox
            x, y, w, h = bbox
            fit = robust_surface_fit(frame, bbox)
            if fit is None:
                rows.append({
                    "original_frame": frame_no, "original_time_s": frame_no / fps,
                    "vessel_detected": 1, "surface_fit_valid": 0,
                    "failure_reason": "SURFACE_FIT_FAILED",
                    "valid": 0, "base_x": x, "base_y": y, "base_w": w, "base_h": h,
                    "base_center_x": x + w / 2.0, "base_center_y": y + h / 2.0,
                    "surface_slope_image_dy_dx": np.nan, "surface_angle_image_deg": np.nan,
                    "surface_y_at_center_px": np.nan, "fit_rmse_px": np.nan,
                    "fit_points": 0, "fit_span_px": 0.0, "quality": "BAD",
                })
            else:
                q = qc_label(fit["rmse_px"], fit["fit_points"], fit["fit_span_px"])
                rows.append({
                    "original_frame": frame_no, "original_time_s": frame_no / fps,
                    "vessel_detected": 1, "surface_fit_valid": 1,
                    "failure_reason": "",
                    "valid": 1, "base_x": x, "base_y": y, "base_w": w, "base_h": h,
                    "base_center_x": x + w / 2.0, "base_center_y": y + h / 2.0,
                    "surface_slope_image_dy_dx": fit["slope"],
                    "surface_angle_image_deg": fit["angle_deg"],
                    "surface_y_at_center_px": fit["surface_y_at_center_px"],
                    "fit_rmse_px": fit["rmse_px"], "fit_points": fit["fit_points"],
                    "fit_span_px": fit["fit_span_px"], "quality": q,
                })
        frame_no += 1
    cap.release()
    return pd.DataFrame(rows)

def analyze_full_for_calibration(video: Path, endpoint_seconds: float = 1.2) -> tuple[pd.DataFrame, float]:
    """Analyze settled endpoint frames using robust video timing.

    Frame count is obtained by actually decoding/grabbing the video once.  This
    avoids bogus CAP_PROP_FRAME_COUNT values on malformed-timestamp Matroska
    files.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open calibration video: {video}")
    fps, _, _ = reliable_video_fps(video, cap)
    n = 0
    while cap.grab():
        n += 1
    cap.release()
    if n < 2:
        raise RuntimeError("Calibration video contains too few decodable frames")

    k = max(8, int(round(endpoint_seconds * fps)))
    k = min(k, n)
    first = analyze_frame_range(video, 0, min(n - 1, k - 1), fps)
    last_start = max(0, n - k)
    last = analyze_frame_range(video, last_start, max(0, n - 1), fps)
    return pd.concat([first, last], ignore_index=True), fps


def endpoint_calibration(df: pd.DataFrame) -> tuple[float, float, dict]:
    d = df[(df["valid"] == 1) & np.isfinite(df["surface_angle_image_deg"])].copy()
    if len(d) < 20:
        raise RuntimeError("Not enough valid frames to estimate perspective calibration")
    xmin, xmax = float(d.base_center_x.min()), float(d.base_center_x.max())
    left = d[(d.base_center_x <= xmin + 2.5) & (d.fit_rmse_px <= 0.8)]
    right = d[(d.base_center_x >= xmax - 2.5) & (d.fit_rmse_px <= 0.8)]
    if len(left) < 5 or len(right) < 5:
        k = max(5, len(d) // 10)
        right = d.head(k)
        left = d.tail(k)
    x_left = float(np.median(left.base_center_x))
    a_left = float(np.median(left.surface_angle_image_deg))
    x_right = float(np.median(right.base_center_x))
    a_right = float(np.median(right.surface_angle_image_deg))
    if abs(x_right - x_left) < 10:
        raise RuntimeError("Calibration endpoints are too close in image space")
    m = (a_right - a_left) / (x_right - x_left)
    b = a_left - m * x_left
    return float(m), float(b), {
        "left_x": x_left, "left_angle_deg": a_left,
        "right_x": x_right, "right_angle_deg": a_right,
        "reference_slope_deg_per_px": m, "reference_intercept_deg": b,
        "calibration_path_span_px": abs(x_right - x_left),
    }


def apply_reference(df: pd.DataFrame, m: float, b: float, motion_start_frame: int, fps: float,
                    plot_smoothing_frames: int = 0) -> pd.DataFrame:
    """Apply perspective reference. Raw per-frame angle remains the primary signal.

    Optional smoothing is created only as a visualization/derived column; it is
    never used by summary statistics or the tracking overlay.
    """
    df = df.copy()
    df["cropped_frame"] = np.arange(len(df), dtype=int)
    if len(df):
        df["cropped_time_s"] = (df["original_frame"] - int(df["original_frame"].iloc[0])) / fps
    else:
        df["cropped_time_s"] = []
    df["motion_time_s"] = (df["original_frame"] - motion_start_frame) / fps
    df["robot_moving"] = (df["original_frame"] >= motion_start_frame).astype(int)
    df["surface_reference_angle_deg"] = m * df["base_center_x"] + b
    df["surface_angle_corrected_deg"] = df["surface_angle_image_deg"] - df["surface_reference_angle_deg"]
    df["surface_slope_corrected"] = np.tan(np.radians(df["surface_angle_corrected_deg"]))

    n = max(0, int(plot_smoothing_frames))
    if n >= 2:
        # Median filter is useful for viewing noisy traces, but it can suppress
        # real short-duration peaks. Keep it out of all quantitative metrics.
        df["surface_angle_plot_smoothed_deg"] = (
            df["surface_angle_corrected_deg"].rolling(n, center=True, min_periods=1).median()
        )
    return df


def stats(prefix: str, d: pd.DataFrame) -> dict:
    d = d[(d.valid == 1) & (d.quality != "BAD") & np.isfinite(d.surface_angle_corrected_deg)]
    if len(d) == 0:
        return {f"{prefix}_{k}": np.nan for k in [
            "mean_angle_deg", "mean_abs_angle_deg", "rms_angle_deg", "min_angle_deg",
            "max_angle_deg", "peak_to_peak_deg", "median_fit_rmse_px"
        ]}
    a = d.surface_angle_corrected_deg.to_numpy(float)
    return {
        f"{prefix}_mean_angle_deg": float(np.nanmean(a)),
        f"{prefix}_mean_abs_angle_deg": float(np.nanmean(np.abs(a))),
        f"{prefix}_rms_angle_deg": float(np.sqrt(np.nanmean(a * a))),
        f"{prefix}_min_angle_deg": float(np.nanmin(a)),
        f"{prefix}_max_angle_deg": float(np.nanmax(a)),
        f"{prefix}_peak_to_peak_deg": float(np.nanmax(a) - np.nanmin(a)),
        f"{prefix}_median_fit_rmse_px": float(d.fit_rmse_px.median()),
    }

def compute_angle_fft(d: pd.DataFrame, fps: float, min_hz: float = 0.1,
                      max_hz: float = 10.0, max_missing_fraction: float = 0.20):
    """FFT of corrected liquid angle on an evenly sampled frame interval.

    Invalid/BAD measurements are treated as missing and linearly interpolated.
    A linear trend is removed and a Hann window is applied before the rFFT.
    Zero padding makes the plotted peak smoother but does not improve the true
    frequency resolution, which is reported separately as ~1 / segment duration.
    """
    if len(d) < max(16, int(round(0.45 * fps))):
        return None, {
            "fft_status": "TOO_SHORT",
            "fft_samples": int(len(d)),
            "fft_duration_s": float(len(d) / fps) if fps > 0 else np.nan,
        }

    values = d["surface_angle_corrected_deg"].astype(float).copy()
    usable = (
        (d["valid"].to_numpy(int) == 1)
        & (d["quality"].astype(str).to_numpy() != "BAD")
        & np.isfinite(values.to_numpy(float))
    )
    values.loc[~usable] = np.nan
    missing_fraction = float(values.isna().mean())
    if values.notna().sum() < max(16, int(round(0.6 * len(values)))):
        return None, {
            "fft_status": "TOO_MANY_MISSING",
            "fft_samples": int(len(d)),
            "fft_duration_s": float(len(d) / fps),
            "fft_interpolated_fraction": missing_fraction,
        }
    if missing_fraction > max_missing_fraction:
        return None, {
            "fft_status": "TOO_MANY_MISSING",
            "fft_samples": int(len(d)),
            "fft_duration_s": float(len(d) / fps),
            "fft_interpolated_fraction": missing_fraction,
        }

    # Preserve uniform frame spacing required by the FFT.
    y = values.interpolate(method="linear", limit_direction="both").to_numpy(float)
    n = len(y)
    t = np.arange(n, dtype=float) / fps

    # Remove DC plus slow linear drift before spectral analysis.
    if n >= 2:
        p = np.polyfit(t, y, 1)
        detrended = y - np.polyval(p, t)
        trend_deg_per_s = float(p[0])
    else:
        detrended = y - np.mean(y)
        trend_deg_per_s = 0.0

    window = np.hanning(n)
    coherent_gain_sum = float(window.sum())
    if coherent_gain_sum <= 0:
        return None, {"fft_status": "WINDOW_ERROR"}

    # 4x zero padding for a smoother spectrum/peak estimate. The independent
    # frequency resolution remains fps / n, not fps / nfft.
    target = max(n, 4 * n)
    nfft = 1 << int(math.ceil(math.log2(target)))
    fft_vals = np.fft.rfft(detrended * window, n=nfft)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fps)
    amps = 2.0 * np.abs(fft_vals) / coherent_gain_sum
    if len(amps):
        amps[0] = 0.0

    nyquist = fps / 2.0
    lo = max(0.0, float(min_hz))
    hi = min(float(max_hz), nyquist)
    band = (freqs >= lo) & (freqs <= hi) & (freqs > 0)
    if not np.any(band):
        return None, {
            "fft_status": "EMPTY_FREQUENCY_BAND",
            "fft_samples": n,
            "fft_duration_s": n / fps,
            "fft_nyquist_hz": nyquist,
        }

    band_indices = np.flatnonzero(band)
    peak_idx = int(band_indices[np.argmax(amps[band])])
    peak_freq = float(freqs[peak_idx])
    peak_amp = float(amps[peak_idx])

    # Parabolic interpolation around the largest spectral bin. This estimates
    # the peak location between zero-padded bins without claiming extra true
    # resolution from the finite record length.
    if 1 <= peak_idx < len(amps) - 1:
        a0, a1, a2 = map(float, amps[peak_idx - 1:peak_idx + 2])
        denom = a0 - 2.0 * a1 + a2
        if abs(denom) > 1e-15:
            delta = 0.5 * (a0 - a2) / denom
            if abs(delta) <= 1.0:
                peak_freq = float((peak_idx + delta) * fps / nfft)
                peak_amp = float(a1 - 0.25 * (a0 - a2) * delta)

    spectrum = pd.DataFrame({
        "frequency_hz": freqs[band],
        "amplitude_deg": amps[band],
    })
    metrics = {
        "fft_status": "OK",
        "fft_samples": int(n),
        "fft_duration_s": float(n / fps),
        "fft_interpolated_fraction": missing_fraction,
        "fft_detrend_deg_per_s": trend_deg_per_s,
        "fft_min_hz": lo,
        "fft_max_hz": hi,
        "fft_nyquist_hz": nyquist,
        "fft_true_resolution_hz": float(fps / n),
        "fft_zero_padded_bin_spacing_hz": float(fps / nfft),
        "fft_dominant_frequency_hz": peak_freq,
        "fft_dominant_period_s": float(1.0 / peak_freq) if peak_freq > 0 else np.nan,
        "fft_peak_amplitude_deg": peak_amp,
    }
    return spectrum, metrics


def write_fft_plot(spectrum: pd.DataFrame, metrics: dict, out_path: Path, title: str,
                   segment_label: str = "post-motion"):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(spectrum["frequency_hz"], spectrum["amplitude_deg"], linewidth=1.1)
    peak_f = metrics.get("fft_dominant_frequency_hz", np.nan)
    peak_a = metrics.get("fft_peak_amplitude_deg", np.nan)
    if np.isfinite(peak_f) and np.isfinite(peak_a):
        ax.scatter([peak_f], [peak_a], s=28, zorder=3,
                   label=f"dominant = {peak_f:.3f} Hz ({1.0/peak_f:.3f} s)")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Angle amplitude (deg)")
    ax.set_title(title + f" — {segment_label} angle FFT")
    ax.grid(True, alpha=0.2)
    if np.isfinite(peak_f):
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)

def write_plot(df: pd.DataFrame, out_path: Path, title: str, motion_duration_s: float,
               post_fft_duration_s: float = 1.0):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df.motion_time_s, df.surface_angle_corrected_deg, linewidth=0.9, alpha=0.85, label="per-frame angle")
    if "surface_angle_plot_smoothed_deg" in df.columns:
        n = int(df.attrs.get("plot_smoothing_frames", 0))
        label = f"{n}-frame median (plot only)" if n else "smoothed (plot only)"
        ax.plot(df.motion_time_s, df.surface_angle_plot_smoothed_deg, linewidth=1.4, label=label)
    bad = df.quality != "GOOD"
    if bad.any():
        ax.scatter(df.loc[bad, "motion_time_s"], df.loc[bad, "surface_angle_corrected_deg"], s=10, label="QC check/bad")
    ax.axvline(0.0, linewidth=1.0, linestyle="--", label="robot starts")
    ax.axvline(motion_duration_s, linewidth=1.0, linestyle="--", label="robot stops")
    if post_fft_duration_s > 0:
        ax.axvspan(
            motion_duration_s,
            motion_duration_s + post_fft_duration_s,
            alpha=0.12,
            label=f"post-motion FFT: first {post_fft_duration_s:g}s",
        )
    ax.axhline(0, linewidth=0.8)
    ax.set_xlabel("Time relative to robot-motion start (s)")
    ax.set_ylabel("Corrected liquid-surface angle (deg)")
    ax.set_title(title)
    ax.grid(True, alpha=0.2)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def write_tracking_video(video: Path, df: pd.DataFrame, out_path: Path, fps: float,
                         width: int, height: int, motion_start: int, motion_end: int):
    if len(df) == 0:
        return
    start_frame = int(df.original_frame.iloc[0])
    end_frame = int(df.original_frame.iloc[-1])
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    lookup = df.set_index("original_frame")
    frame_no = start_frame
    while frame_no <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_no in lookup.index:
            r = lookup.loc[frame_no]
            phase = "MOVING" if motion_start <= frame_no <= motion_end else "PADDING"
            if int(r.valid) == 1 and np.isfinite(r.surface_slope_image_dy_dx):
                x, y, w, h = int(r.base_x), int(r.base_y), int(r.base_w), int(r.base_h)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 1)
                slope = float(r.surface_slope_image_dy_dx)
                yc = float(r.surface_y_at_center_px)
                xc = x + w / 2.0
                x1, x2 = x + 4, x + w - 4
                y1 = int(round(yc + slope * (x1 - xc)))
                y2 = int(round(yc + slope * (x2 - xc)))
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                txt = (f"t={r.motion_time_s:+.2f}s  angle={r.surface_angle_corrected_deg:+.2f} deg  "
                       f"RMSE={r.fit_rmse_px:.2f}px  {r.quality}  {phase}")
            else:
                reason = str(r.get("failure_reason", "NO_MEASUREMENT"))
                txt = f"t={r.motion_time_s:+.2f}s  NO MEASUREMENT: {reason}  {phase}"
            cv2.putText(frame, txt, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.68,
                        (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(frame)
        frame_no += 1
    cap.release()
    writer.release()


# ------------------------------- processing ----------------------------------

def write_status(out_dir: Path, status: str, reason: str = "", **kwargs):
    payload = {"status": status, "reason": reason, **kwargs}
    (out_dir / "status.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _run_title(run_info: dict) -> str:
    bits = [run_info.get("method"), run_info.get("case_id"), run_info.get("trial_id")]
    return " / ".join(str(x) for x in bits if x)


def _write_fft_segment(df: pd.DataFrame, fps: float, out_dir: Path, file_stem: str,
                       title: str, segment_label: str, min_hz: float, max_hz: float):
    spectrum, metrics = compute_angle_fft(df, fps, min_hz, max_hz)
    if spectrum is not None and metrics.get("fft_status") == "OK":
        spectrum.to_csv(out_dir / f"{file_stem}.csv", index=False)
        write_fft_plot(
            spectrum, metrics, out_dir / f"{file_stem}.png",
            title, segment_label=segment_label,
        )
    return metrics


def process_video(video: Path, root: Path, m: float, b: float, calibration_span_px: float,
                  calibration_left_x: float, calibration_right_x: float,
                  pre_s: float, post_s: float, speed_threshold: float,
                  write_video: bool, include_incomplete: bool,
                  plot_smoothing_frames: int = 0, strict_visual_path: bool = False,
                  do_fft: bool = True, fft_min_hz: float = 0.1, fft_max_hz: float = 10.0,
                  post_fft_duration_s: float = 1.0, boundary_refine_margin_s: float = 1.0) -> dict:
    run_dir = video.parent
    out_dir = run_dir / "liquid_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_info = identify_run(run_dir, root)
    events = read_events(run_dir)
    meta = read_metadata(run_dir, root)
    movel_run = is_movel_run(run_dir, meta)
    title = _run_title(run_info)

    base = {
        "relative_run_path": str(run_dir.relative_to(root)),
        **run_info,
        "condition": run_info.get("method", run_dir.parent.name),
        "run_id": run_dir.name,
        "video": video.name,
        "is_movel": movel_run,
        **meta,
        **events,
    }

    # Logger events are diagnostic only. Camera and logger clocks are not assumed
    # to be synchronized, so missing/misaligned completion events never gate the
    # liquid analysis. Video kinematics below determine start and stop.

    try:
        analysis_video, decode_info = prepare_video_source(video, out_dir)
        endpoint_xs = (calibration_left_x, calibration_right_x)
        track, fps, width, height, n_frames = track_vessel(
            analysis_video, endpoint_xs=endpoint_xs
        )
        fps_source = track.attrs.get("fps_source", "unknown")
        raw_opencv_fps = track.attrs.get("raw_opencv_fps", np.nan)
        coarse_mot = detect_robot_motion_calibrated_endpoints(
            track, fps, endpoint_xs, speed_threshold
        )
        mot = refine_motion_boundaries(
            analysis_video, coarse_mot, fps, n_frames,
            margin_s=boundary_refine_margin_s, endpoint_xs=endpoint_xs
        )
        ms, me = mot["motion_start_frame"], mot["motion_end_frame"]
        crop_start = max(0, int(math.floor(ms - pre_s * fps)))
        # Ensure the crop includes the requested post-motion FFT window even if
        # --post-seconds is set smaller than --post-fft-seconds.
        effective_post_s = max(post_s, post_fft_duration_s)
        crop_end = min(n_frames - 1, int(math.ceil(me + effective_post_s * fps)))
        actual_pre = (ms - crop_start) / fps
        actual_post = (crop_end - me) / fps
        padding_complete = (actual_pre + 1.0 / fps >= pre_s) and (actual_post + 1.0 / fps >= post_s)
        path_coverage_ratio = mot["endpoint_span_px"] / calibration_span_px if calibration_span_px > 0 else np.nan

        visual_complete = bool(path_coverage_ratio >= 0.85)
        if strict_visual_path and not visual_complete and not include_incomplete:
            write_status(out_dir, "SKIPPED_VISUAL_INCOMPLETE",
                         "visual path coverage below 85%",
                         path_coverage_ratio=path_coverage_ratio)
            return {**base, "status": "SKIPPED_VISUAL_INCOMPLETE",
                    "path_coverage_ratio": path_coverage_ratio,
                    "visual_path_complete": visual_complete}

        df = analyze_frame_range(analysis_video, crop_start, crop_end, fps)
        df = apply_reference(df, m, b, ms, fps, plot_smoothing_frames)
        df.attrs["plot_smoothing_frames"] = int(max(0, plot_smoothing_frames))
        df["robot_moving"] = ((df.original_frame >= ms) & (df.original_frame <= me)).astype(int)
        df["time_from_visual_stop_s"] = (df.original_frame - me) / fps

        # Post-motion FFT = the first fixed-duration interval immediately AFTER
        # the visually detected final moving frame.  The final moving frame
        # itself is not part of the post-motion window.
        post_fft_n_frames = max(1, int(round(max(0.0, post_fft_duration_s) * fps)))
        post_fft_start_frame = me + 1
        post_fft_end_frame = min(crop_end, post_fft_start_frame + post_fft_n_frames - 1)
        post_fft_mask = (
            (df.original_frame >= post_fft_start_frame)
            & (df.original_frame <= post_fft_end_frame)
        )
        df["post_motion_fft_window"] = post_fft_mask.astype(int)
        # Backward-compatible alias for older downstream notebooks.
        df["ringdown_fft_window"] = df["post_motion_fft_window"]
        df.to_csv(out_dir / "surface_data.csv", index=False)

        motion_duration = (me - ms + 1) / fps
        write_plot(
            df, out_dir / "angle_plot.png", title, motion_duration,
            post_fft_duration_s=post_fft_duration_s,
        )
        if write_video:
            write_tracking_video(analysis_video, df, out_dir / "tracking_cropped.mp4", fps, width, height, ms, me)

        usable = df[(df.valid == 1) & (df.quality != "BAD")]
        motion_df = df[df.robot_moving == 1].copy()
        first1_df = motion_df[(motion_df.motion_time_s >= 0.0) & (motion_df.motion_time_s < 1.0)].copy()
        post_df = df[df.post_motion_fft_window == 1].copy()

        first1_fft = {"fft_status": "DISABLED"}
        motion_fft = {"fft_status": "DISABLED"}
        post_fft = {"fft_status": "DISABLED"}
        if do_fft:
            first1_fft = _write_fft_segment(
                first1_df, fps, out_dir, "fft_first_1s_motion", title,
                "first 1.0 s of motion", fft_min_hz, fft_max_hz,
            )
            motion_fft = _write_fft_segment(
                motion_df, fps, out_dir, "fft_whole_motion", title,
                "whole robot motion", fft_min_hz, fft_max_hz,
            )
            post_fft = _write_fft_segment(
                post_df, fps, out_dir, "fft_post_motion", title,
                f"first {post_fft_duration_s:g} s immediately after visual stop", fft_min_hz, fft_max_hz,
            )

        summary = {
            **base,
            "status": "OK" if padding_complete else "OK_PADDING_TRUNCATED",
            "fps": fps,
            "source_frames": n_frames,
            "source_duration_s": n_frames / fps,
            "timing_source": "VIDEO_ONLY",
            "video_fps_source": fps_source,
            "raw_opencv_fps": raw_opencv_fps,
            **decode_info,
            "motion_boundary_method": mot.get("boundary_refinement", "COARSE_VIDEO"),
            "motion_detection_method": coarse_mot.get("motion_detection_method", "UNKNOWN"),
            "calibrated_start_endpoint_x": coarse_mot.get("calibrated_start_endpoint_x"),
            "calibrated_target_endpoint_x": coarse_mot.get("calibrated_target_endpoint_x"),
            "calibrated_endpoint_start_error_px": coarse_mot.get("calibrated_endpoint_start_error_px"),
            "calibrated_endpoint_end_error_px": coarse_mot.get("calibrated_endpoint_end_error_px"),
            "calibrated_endpoint_track_fraction": coarse_mot.get("calibrated_endpoint_track_fraction"),
            "motion_start_s_video": ms / fps,
            "motion_end_s_video": me / fps,
            "motion_duration_s_visual": motion_duration,
            "coarse_motion_start_s_video": mot.get("coarse_motion_start_s", coarse_mot.get("motion_start_s")),
            "coarse_motion_end_s_video": mot.get("coarse_motion_end_s", coarse_mot.get("motion_end_s")),
            "boundary_refine_detection_fraction": mot.get("refine_detection_fraction", np.nan),
            "boundary_refine_path_span_px": mot.get("refine_path_span_px", np.nan),
            "post_fft_duration_requested_s": post_fft_duration_s,
            "post_fft_start_s_video": post_fft_start_frame / fps,
            "post_fft_end_s_video": post_fft_end_frame / fps,
            "post_fft_frames": int(len(post_df)),
            "post_fft_actual_duration_s": float(len(post_df) / fps),
            "event_vs_visual_motion_duration_s": (
                float(events["event_motion_duration_s"] - motion_duration)
                if np.isfinite(events.get("event_motion_duration_s", np.nan)) else np.nan
            ),
            "crop_start_s_video": crop_start / fps,
            "crop_end_s_video": crop_end / fps,
            "crop_duration_s": (crop_end - crop_start + 1) / fps,
            "requested_pre_s": pre_s,
            "requested_post_s": post_s,
            "effective_post_s": effective_post_s,
            "actual_pre_s": actual_pre,
            "actual_post_s": actual_post,
            "padding_complete": padding_complete,
            "endpoint_span_px": mot["endpoint_span_px"],
            "path_coverage_ratio": path_coverage_ratio,
            "visual_path_complete": visual_complete,
            "vessel_detection_fraction_window": float((df.vessel_detected == 1).mean()) if len(df) else np.nan,
            "surface_fit_fraction_window": float((df.surface_fit_valid == 1).mean()) if len(df) else np.nan,
            "missing_vessel_frames_window": int((df.vessel_detected == 0).sum()) if len(df) else 0,
            "surface_fit_failed_frames_window": int(((df.vessel_detected == 1) & (df.surface_fit_valid == 0)).sum()) if len(df) else 0,
            "valid_fraction_window": float((df.valid == 1).mean()) if len(df) else np.nan,
            "good_fraction_window": float((df.quality == "GOOD").mean()) if len(df) else np.nan,
            "usable_frames_window": int(len(usable)),
            "usable_frames_motion": int(len(motion_df[(motion_df.valid == 1) & (motion_df.quality != "BAD")])),
            **stats("window", df),
            **stats("motion", motion_df),
            **{f"first1_{k}": v for k, v in first1_fft.items()},
            **{f"motion_{k}": v for k, v in motion_fft.items()},
            **{f"post_{k}": v for k, v in post_fft.items()},
        }
        pd.DataFrame([summary]).to_csv(out_dir / "summary.csv", index=False)
        write_status(
            out_dir, summary["status"],
            timing_source="VIDEO_ONLY",
            video_decode_source=decode_info.get("video_decode_source"),
            original_fps_hint_source=decode_info.get("original_fps_hint_source"),
            motion_boundary_method=mot.get("boundary_refinement", "COARSE_VIDEO"),
            motion_start_frame=ms, motion_end_frame=me,
            coarse_motion_start_frame=mot.get("coarse_motion_start_frame", coarse_mot.get("motion_start_frame")),
            coarse_motion_end_frame=mot.get("coarse_motion_end_frame", coarse_mot.get("motion_end_frame")),
            post_fft_duration_requested_s=post_fft_duration_s,
            post_fft_start_frame=post_fft_start_frame,
            post_fft_end_frame=post_fft_end_frame,
            crop_start_frame=crop_start, crop_end_frame=crop_end,
            event_completion_rule=events.get("event_completion_rule"),
            event_completion_ok=events.get("event_completion_ok"),
            path_coverage_ratio=path_coverage_ratio,
            visual_path_complete=visual_complete,
            is_movel=movel_run,
            plot_smoothing_frames=int(max(0, plot_smoothing_frames)),
            fft_enabled=bool(do_fft),
            first1_fft_status=first1_fft.get("fft_status"),
            whole_motion_fft_status=motion_fft.get("fft_status"),
            post_fft_status=post_fft.get("fft_status"),
            padding_complete=padding_complete,
        )
        return summary
    except Exception as exc:
        message = str(exc)
        if "OpenCV cannot decode this MKV" in message or "automatic ffmpeg normalization failed" in message:
            status = "VIDEO_DECODE_FAILED"
        elif message.startswith("Cannot open video:"):
            status = "UNREADABLE_VIDEO"
        elif "Vessel tracking failed" in message:
            status = "TRACKING_FAILED"
        elif "Could not detect a clear robot movement interval" in message:
            status = "MOTION_DETECTION_FAILED"
        else:
            status = "ERROR"
        write_status(out_dir, status, message)
        return {**base, "status": status, "error": message}


def _is_excluded(path: Path, root: Path, exclude_patterns: Optional[list[str]] = None) -> bool:
    """Return True when path falls under one of the requested exclusions.

    A pattern without a slash matches a folder/file name anywhere below root:
        --exclude servop_behavior

    A pattern containing a slash is matched against the root-relative POSIX path
    and may use shell wildcards:
        --exclude "ruckig/*/case_009"
        --exclude "moveL/20261009_134603_564176"
    Matching is case-insensitive so the same command behaves consistently on
    Windows and Linux.
    """
    if not exclude_patterns:
        return False

    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()

    rel_cf = rel.casefold()
    parts_cf = [part.casefold() for part in Path(rel).parts]

    for raw in exclude_patterns:
        pattern = str(raw).strip().replace("\\", "/").strip("/")
        if not pattern:
            continue
        pat_cf = pattern.casefold()

        if "/" not in pat_cf:
            # Convenient folder-name exclusion anywhere in the selected tree.
            if any(fnmatch(part, pat_cf) for part in parts_cf):
                return True
            continue

        # Relative path/pattern exclusion. Matching a directory also excludes
        # everything nested beneath it.
        if fnmatch(rel_cf, pat_cf) or fnmatch(rel_cf, pat_cf.rstrip("/") + "/*"):
            return True

    return False


def find_runs(root: Path, video_name: Optional[str] = None,
              exclude_patterns: Optional[list[str]] = None) -> tuple[list[Path], list[Path]]:
    """Find one preferred camera file per trial, honoring requested exclusions.

    Revised datasets use camera.mkv and may also contain camera_original.mkv.
    The repaired/validated camera.mkv is preferred and camera_original.mkv is
    never selected automatically. Legacy camera.mp4 is accepted as fallback.
    """
    def allowed(p: Path) -> bool:
        return "liquid_analysis" not in p.parts and not _is_excluded(p, root, exclude_patterns)

    if video_name:
        candidates = sorted(p for p in root.rglob(video_name) if allowed(p))
    else:
        preferred = sorted(p for p in root.rglob("camera.mkv") if allowed(p))
        preferred_dirs = {p.parent.resolve() for p in preferred}
        legacy = sorted(
            p for p in root.rglob("camera.mp4")
            if allowed(p) and p.parent.resolve() not in preferred_dirs
        )
        candidates = preferred + legacy

    # One video per trial directory.
    videos_by_dir = {}
    for p in candidates:
        videos_by_dir.setdefault(p.parent.resolve(), p)
    videos = sorted(videos_by_dir.values())
    video_dirs = set(videos_by_dir)

    # A trial is defined by an events.csv; if it has no preferred video, mark it.
    # Excluded trial folders are intentionally absent from the master summary.
    no_video_dirs = []
    for events in root.rglob("events.csv"):
        if "liquid_analysis" in events.parts or _is_excluded(events, root, exclude_patterns):
            continue
        if events.parent.resolve() not in video_dirs:
            no_video_dirs.append(events.parent)
    return videos, sorted(set(no_video_dirs))


def main():
    ap = argparse.ArgumentParser(description="Recursively analyze liquid-surface angle in robot experiment folders")
    ap.add_argument("root", help="Dataset root folder (for example: ...\\Final Results)")
    ap.add_argument(
        "--video-name", default=None,
        help="Exact video filename override. Default auto-detects camera.mkv, then legacy camera.mp4",
    )
    ap.add_argument(
        "--exclude", action="append", default=[],
        help=(
            "Exclude a folder name or root-relative path/glob. May be repeated. "
            "Examples: --exclude servop_behavior --exclude \"ruckig/*/case_009\""
        ),
    )
    ap.add_argument(
        "--calibration-video",
        help="Optional known-good camera.mkv/camera.mp4. Default is the first preferred video found",
    )
    ap.add_argument("--pre-seconds", type=float, default=1.0, help="Fixed time kept before detected robot motion")
    ap.add_argument("--post-seconds", type=float, default=1.0,
                    help="Fixed time kept after detected robot motion (default: 1.0 s)")
    ap.add_argument("--motion-speed-threshold", type=float, default=10.0, help="Minimum tracked vessel speed in px/s for coarse video scan")
    ap.add_argument(
        "--boundary-refine-margin-seconds", type=float, default=1.0,
        help="Native-frame video margin around coarse start/stop used to refine motion boundaries",
    )
    ap.add_argument(
        "--post-fft-seconds", type=float, default=1.0,
        help="Duration of FFT window immediately after the visually detected robot stop (default: 1.0 s)",
    )
    ap.add_argument("--no-video", action="store_true", help="Do not create cropped annotated tracking videos")
    ap.add_argument(
        "--include-incomplete", action="store_true",
        help="Deprecated compatibility flag. Logger completion events are diagnostic only; video timing is always used.",
    )
    ap.add_argument(
        "--strict-visual-path", action="store_true",
        help="Also reject trials whose visual path coverage is below 85%% (off by default)",
    )
    ap.add_argument(
        "--plot-smoothing-frames", type=int, default=0,
        help="Optional centered median for angle_plot.png only; 0 keeps the raw per-frame signal",
    )
    ap.add_argument("--no-fft", action="store_true", help="Disable all FFT outputs")
    ap.add_argument("--fft-min-hz", type=float, default=0.1, help="Lowest frequency considered for dominant FFT peak")
    ap.add_argument("--fft-max-hz", type=float, default=10.0, help="Highest frequency considered for dominant FFT peak")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    videos, no_video_dirs = find_runs(root, args.video_name, args.exclude)
    if not videos:
        wanted = args.video_name or "camera.mkv / camera.mp4"
        raise SystemExit(f"No {wanted} files found under {root}")

    print(f"Dataset root: {root}")
    if args.exclude:
        print("Excluded: " + ", ".join(args.exclude))
    print(f"Found {len(videos)} trial videos; {len(no_video_dirs)} trial folders have no preferred camera video.")
    print(f"Temporal crop: {args.pre_seconds:.2f}s before motion + motion + {args.post_seconds:.2f}s after motion")
    print(f"Plot smoothing: {args.plot_smoothing_frames} frame(s) (0 = raw per-frame plot)")
    print("Motion timing: VIDEO ONLY (native-frame boundary refinement; logger events are diagnostic)")
    print(f"FFT: {'disabled' if args.no_fft else f'first 1 s + whole motion + first {args.post_fft_seconds:g}s immediately after visual stop, {args.fft_min_hz:g}-{args.fft_max_hz:g} Hz'}")
    print(f"Strict visual-path rejection: {args.strict_visual_path}")

    # Calibration is a perspective correction, not a motion-timing calibration.
    # If no explicit calibration video is supplied, try videos until one yields
    # clean settled endpoints rather than blindly assuming videos[0] is valid.
    if args.calibration_video:
        calibration_video = Path(args.calibration_video).resolve()
        cal_source, cal_decode = prepare_video_source(calibration_video, calibration_video.parent / "liquid_analysis")
        cal_df, _ = analyze_full_for_calibration(cal_source)
        m, b, cal = endpoint_calibration(cal_df)
        cal["calibration_decode_source"] = cal_decode.get("video_decode_source")
    else:
        calibration_video = None
        calibration_errors = []
        for candidate in videos:
            try:
                cal_source, cal_decode = prepare_video_source(candidate, candidate.parent / "liquid_analysis")
                cal_df, _ = analyze_full_for_calibration(cal_source)
                m, b, cal = endpoint_calibration(cal_df)
                cal["calibration_decode_source"] = cal_decode.get("video_decode_source")
                calibration_video = candidate
                break
            except Exception as exc:
                calibration_errors.append(f"{candidate}: {exc}")
        if calibration_video is None:
            preview = "\n".join(calibration_errors[:5])
            raise SystemExit("Could not find a usable calibration video. First failures:\n" + preview)

    print(f"Calibration video: {calibration_video}")
    try:
        cal["calibration_video"] = str(calibration_video.relative_to(root))
    except ValueError:
        cal["calibration_video"] = str(calibration_video)
    pd.DataFrame([cal]).to_csv(root / "liquid_analysis_calibration.csv", index=False)
    print(f"Perspective reference: angle = {m:.8f} * x + {b:.6f} deg")

    summaries = []
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {video.relative_to(root)}")
        s = process_video(
            video, root, m, b, float(cal["calibration_path_span_px"]),
            float(cal["left_x"]), float(cal["right_x"]),
            args.pre_seconds, args.post_seconds, args.motion_speed_threshold,
            not args.no_video, args.include_incomplete,
            args.plot_smoothing_frames, args.strict_visual_path,
            not args.no_fft, args.fft_min_hz, args.fft_max_hz,
            args.post_fft_seconds, args.boundary_refine_margin_seconds,
        )
        summaries.append(s)
        print(f"    -> {s.get('status')}")

    for d in no_video_dirs:
        out_dir = d / "liquid_analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        reason = f"{args.video_name or 'camera.mkv/camera.mp4'} not found"
        write_status(out_dir, "NO_VIDEO", reason)
        run_info = identify_run(d, root)
        summaries.append({
            "relative_run_path": str(d.relative_to(root)),
            **run_info,
            "condition": run_info.get("method", d.parent.name),
            "run_id": d.name,
            "video": "",
            "status": "NO_VIDEO",
            **read_metadata(d, root),
            **read_events(d),
        })

    summary_df = pd.DataFrame(summaries)
    summary_path = root / "liquid_analysis_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print("\nStatus counts:")
    print(summary_df["status"].value_counts(dropna=False).to_string())
    print(f"\nMaster summary: {summary_path}")


if __name__ == "__main__":
    main()