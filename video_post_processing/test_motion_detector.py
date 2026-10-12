#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

SCRIPT = Path(__file__).with_name("Video_post_process_video_timing_v5.py")
spec = importlib.util.spec_from_file_location("video_post", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_track(xs, sample_fps=10.0, video_fps=30.0):
    xs = np.asarray(xs, dtype=float)
    times = np.arange(len(xs), dtype=float) / sample_fps
    frames = np.rint(times * video_fps).astype(int)
    return pd.DataFrame({
        "frame": frames,
        "time_s": times,
        "base_x": xs - 40,
        "base_y": 590.0,
        "base_w": 80.0,
        "base_h": 30.0,
        "base_center_x": xs,
        "base_center_y": 605.0,
    })


def test_slow_full_traversal():
    left, right = 193.0, 788.0
    x = np.r_[np.full(15, left), np.linspace(left, right, 35), np.full(15, right)]
    tr = make_track(x)
    mot = mod.detect_robot_motion_calibrated_endpoints(tr, 30.0, (left, right), 10.0)
    assert mot["motion_detection_method"] == "CALIBRATED_ENDPOINTS"
    assert 3.0 <= mot["motion_duration_s"] <= 4.2, mot
    assert mot["endpoint_span_px"] > 0.95 * (right - left), mot


def test_short_false_jump_not_accepted_as_full_motion():
    left, right = 193.0, 788.0
    x = np.full(65, left, dtype=float)
    x[25:28] = [300.0, 350.0, 300.0]
    tr = make_track(x)
    try:
        mot = mod.detect_robot_motion_calibrated_endpoints(tr, 30.0, (left, right), 10.0)
    except RuntimeError:
        return
    assert mot.get("motion_detection_method") != "CALIBRATED_ENDPOINTS", mot


def test_reverse_direction():
    left, right = 193.0, 788.0
    x = np.r_[np.full(12, right), np.linspace(right, left, 28), np.full(12, left)]
    tr = make_track(x)
    mot = mod.detect_robot_motion_calibrated_endpoints(tr, 30.0, (left, right), 10.0)
    assert mot["motion_detection_method"] == "CALIBRATED_ENDPOINTS"
    assert mot["calibrated_start_endpoint_x"] == right
    assert mot["calibrated_target_endpoint_x"] == left




def test_damped_ringdown_fit():
    fps = 30.0
    t = np.arange(0.0, 2.0, 1.0 / fps) + 1.0 / fps
    true_amp = 6.0
    true_freq = 3.2
    true_tau = 1.5
    y = (
        0.35 + 0.08 * t
        + true_amp * np.exp(-t / true_tau) * np.sin(2.0 * np.pi * true_freq * t + 0.4)
    )
    d = pd.DataFrame({
        "time_from_visual_stop_s": t,
        "surface_angle_corrected_deg": y,
        "valid": np.ones(len(t), dtype=int),
        "quality": ["GOOD"] * len(t),
    })
    fit_df, metrics = mod.fit_damped_ringdown(d, fps, min_hz=0.5, max_hz=8.0)
    assert fit_df is not None, metrics
    assert metrics["ringdown_status"] == "OK", metrics
    assert abs(metrics["ringdown_initial_amplitude_deg"] - true_amp) < 0.35, metrics
    assert abs(metrics["ringdown_frequency_hz"] - true_freq) < 0.08, metrics
    assert abs(metrics["ringdown_decay_time_s"] - true_tau) < 0.35, metrics
    assert metrics["ringdown_r2"] > 0.98, metrics


if __name__ == "__main__":
    tests = [
        test_slow_full_traversal,
        test_short_false_jump_not_accepted_as_full_motion,
        test_reverse_direction,
        test_damped_ringdown_fit,
    ]
    for test_func in tests:
        test_func()
        print(f"PASS {test_func.__name__}")
