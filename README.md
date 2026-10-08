# DOBOT Trajectory Experiments

Python experiment framework for a DOBOT manipulator, MATLAB-generated trajectories, and synchronized-in-software recording from robot feedback, a Rigol DS1202Z-E, and an RTSP camera.

## Layout

- `core/` — configuration, robot motion, batch runner, post-trial metrics
- `loggers/` — independent robot feedback, Rigol, and RTSP recorders
- `experiments/` — experiment definitions and MATLAB trajectory generators
- `TCP-IP-Python-V4/` — original DOBOT SDK (unchanged)
- `tests/` — mocked/offline regression tests
- `results/` — a timestamped directory per batch and independent directory per trial

## Installation and offline checks

```powershell
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

No `--execute` means **dry run**: no physical motion. Inspect and verify robot pose, tool/payload, available clearances, camera address, and oscilloscope setup before real runs.

```powershell
python main.py --experiment movel --list-cases
python main.py --experiment movel --case 1 --repetitions 1
python main.py --experiment movel --case 1 --repetitions 1 --execute
```

`--case` is one-based; the chosen matrix index is preserved in the trial folder and summary, even when only one case is run. Without `--case`, all configured cases run.

Other experiments:

```powershell
python main.py --experiment ruckig --repetitions 1
python main.py --experiment cubic --csv PATH_TO_POINTS.csv --repetitions 1
```

Cubic, quintic, trapezoidal and Double-S each use a supplied trajectory CSV **per invocation** in this branch. The planned 3×3 offline/Ruckig matrix is **not yet implemented**. MoveJ still requires validated joint-space endpoints; the payload helper currently defines only one load. Camera-video analysis is not yet implemented.

## Current measurement configuration

The authoritative device settings are in `config/common.json`; review them before executing any movement. Defaults in the Python `Config` class may differ when a JSON setting overrides them.

| Field | Current value | Meaning |
| --- | --- | --- |
| `rigol_horizontal_scale_s_per_div` | 0.5 | 6-second nominal screen span (12 divisions) |
| `rigol_pre_delay_s` | 1.5 | Minimum Rigol `:RUN`-to-motion lead (software clock) |
| `rigol_download_raw` | `false` | Skip multi-million-point RAW transfers in normal experiments |
| `rigol_preview_points` | 1200 | Output points (normally NORM display's 1,200 samples) |
| `robot_logger_pre_delay_s` | 0.5 | Approximate robot feedback lead before motion |
| `robot_logger_post_delay_s` | 1 | Additional robot feedback after `MOTION_END` |
| `camera_stop_delay_s` | 2 | Extra video after Rigol transfer completes |

The camera begins before the scope. Robot feedback begins near the end of scope pre-roll, continues through motion and one second afterward, and stops before scope transfer. The camera continues recording during scope acquisition/download and stops after the additional delay. MP4 output is constant-frame-rate; duplicate frames can preserve elapsed playback time if RTSP frames arrive slowly. The true received frame count and wall duration are returned in camera logging metadata.

Rigol must use `MAIN` (not `ROLL`) timebase mode. The logger checks `STOP` before retrieving waveforms and saves a scope screenshot, `rigol_metadata.json`, `rigol_chan1_display.csv`, `rigol_chan2_display.csv`, and `rigol_scope.csv` (current/voltage/power). The normal 1,200-point six-second window is approximately **200 samples/s**. This is sufficient for coarse movement power profiles, **not high-frequency transients**.

Optional `rigol_download_raw: true` is for debugging only; the DS1202Z-E RAW BYTE preamble conversion produced reversed CHAN1 polarity compared with its NORM display waveform on observed trials. Do not interpret RAW-derived power without independently validating that conversion. The scope's time axis is trigger-relative, **not synchronized with robot timestamps**. `rigol_acquisition_energy_J` is signed power integrated over the **whole scope capture**, *not* verified movement-only energy. Current-probe polarity and scale also require independent validation before publishing absolute energy.

## MoveL / MoveJ

Measured MoveL / MoveJ commands set the global speed factor to 100% and pass speed/acceleration percentages as individual movement arguments (`v`/`a`). Preparation and return-home use the slow global factor configured for those phases. Event records capture the requested motion settings and command response.

Hardware movement completion and limits must be checked in supervised single-run tests. Do not start an unattended batch on unverified paths.

## Metrics and outputs

Each trial records (as applicable) `feedback.csv`, `feedback_raw.bin`, `events.csv`, `camera.mp4`, `rigol_scope.csv`, `rigol_metadata.json`, `rigol_screen.png`, `result.json`, `metrics.json`, `metrics.csv`, and `commands.csv` for externally streamed trajectories. Optional Rigol RAW outputs are only produced when specifically enabled.

The analysis uses only robot feedback between `MOTION_START` and `MOTION_END` for tracking RMSE and joint/TCP velocity maxima, to avoid bias from stationary preparation and logger download intervals. Fields `robot_motion_window_valid` and `robot_motion_samples` help diagnose missing or incomplete events. The scope metrics are **not motion-window filtered** until scope/robot synchronization is validated.

Each batch writes `trial_summary.csv` and `experiment_summary.json`, and includes CLI progress, repetition count, remaining cases, and estimated time.

## Safety and validation

- A successful mocked unit test does **not** verify physical robot movement or measurement calibration.
- Check the tool, payload, start/end poses, connection and device settings before supervised trials.
- Failed motion or acquisition attempts are recorded and abort the batch. No automatic recovery movement is attempted after failure.
- The base SDK is deliberately unchanged.
