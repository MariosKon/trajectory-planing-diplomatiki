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

Cubic and Quintic expose three fixed-time reference cases each by default; `--csv PATH` still selects a custom single-case CSV. **Trapezoidal, Double-S and online Ruckig expose nine V/A/J sweep cases by default and retain three matched-time reference cases** (3.93, 2.79 and 2.31 seconds) using the same Cartesian reference, selected ServoP tuning and documented velocity / acceleration / jerk constraints. Trapezoidal and Double-S still support `--csv PATH` to run an explicitly supplied single-case CSV. The dedicated `servop_behavior` experiment has its own MATLAB cubic generator and committed reference CSV in `experiments/servop_behavior/`; it varies servo tracking parameters while keeping the same Cartesian MoveL path. MoveJ still requires validated joint-space endpoints. The dedicated payload study now selects the six fastest physically tested trajectory cases and runs them in separate baseline and changed-payload phases; see [the payload experiment protocol](docs/payload-analysis.md). Camera-video analysis is not yet implemented.

## Two-phase payload analysis

The payload comparison uses one repetition each of MoveL, Cubic,
Quintic, Double-S, Ruckig and Trapezoidal at their fastest already
hardware-tested cases. It **does not automatically run** the second
condition after a physical payload change.

```powershell
python main.py --experiment payload --list-cases
python main.py --experiment payload --payload-phase baseline
# Real robot: only after reviewing the motion and payload limits.
python main.py --experiment payload --payload-phase baseline --execute
# STOP; inspect baseline files, safely change/verify payload, then:
python main.py --experiment payload --payload-phase changed --execute
```

To record a measured load without changing the controller payload value,
append `--payload-mass-kg N` to each command (N in kilograms).
Review `tool_index` and `payload_kg` in the hardware configuration separately.
Outputs are under `results/payload/baseline/` and
`results/payload/changed/`. See [the full safety, provenance and comparison
instructions](docs/payload-analysis.md).

## Offline polynomial study: fixed-time Cubic and Quintic

The final MoveL comparison source is `Final Results/moveL/20261009_134603_564176/` (45 successful runs). The polynomial study holds **nominal traversal time fixed** between Cubic and Quintic at each corresponding MoveL speed level. All three cases use the **same Cartesian poses**, linear Y displacement 800 mm, 30 ms ServoP update, selected default `aheadtime=20`, `gain=300`, and **`SpeedFactor(100)`** for streaming. These are prescribed times, not speed-constrained optimization results.

| Case | MoveL speed-factor level | MoveL measured mean time (approx.) | Polynomial CSV duration | Samples |
| --- | --- | --- | --- | --- |
| 1 | 50% | 3.93 s | **3.93 s** | 132 |
| 2 | 75% | 2.81 s | **2.79 s** | 94 |
| 3 | 100% | 2.29–2.30 s | **2.31 s** | 78 |

`CSV duration = (number of samples - 1) * 0.030 s`. The Python runner sends every sample including both endpoints; wall-clock motion measurement also includes command overhead, a final hold interval and robot settling, so **actual motion durations may differ**. Compare measured `MOTION_START`/`MOTION_END` and physical 1–99% movement durations after the hardware tests.

**Speed trade-off:** An equal-time polynomial has a different peak speed from MoveL and even from the other polynomial. Analytic peaks on the 800 mm Y translation are:

| Time | Cubic peak V | Quintic peak V |
| --- | --- | --- |
| 3.93 s | 305.3 mm/s | 381.7 mm/s |
| 2.79 s | 430.1 mm/s | **537.6 mm/s** |
| 2.31 s | **519.5 mm/s** | **649.4 mm/s** |

Bold speeds exceed the ~470.5 mm/s plateau observed in fastest MoveL. **Do not interpret this as speed-limited equivalence** or assume those profiles are safe just because MoveL was successful. Physically review these faster trajectories, the robot's limits, payload and clearances **before enabling `--execute`**. Cubic acceleration is discontinuous when joining a stationary segment; physical jerk is not bounded by the finite interior polynomial derivative.

### Regenerate the references with MATLAB

The MATLAB wrappers require no input CSV; they generate all three files in their respective experiment folders:

```matlab
run('experiments/cubic/make_cubic_csv.m')
run('experiments/quintic/make_quintic_csv.m')
```

The shared implementation is `experiments/polynomial_fixed_time/generate_fixed_time_polynomial.m`. All six reference CSVs are committed and analytically checked by the Python regression suite. MATLAB generation has not yet been physically validated.

**MATLAB diagnostics (enabled by default):** both scripts now print a detailed report for each of their three exports: absolute CSV path, duration, 30 ms step, sample count, initial/final poses, analytic peak velocity/acceleration/interior jerk, and an explicit `CSV read-back: PASS` after MATLAB reopens the saved CSV and checks its header, ServoP modes, row count, numeric values, analytic waypoints, exact endpoints, and monotonic Y. A three-row summary follows. Each script opens **three figures** (one per duration), with position, velocity, acceleration and jerk. The position subplot overlays the actual reloaded CSV points. To suppress figures during batch generation, set `makePlot = false;` in the relevant MATLAB wrapper; verification and printed reports remain enabled. The read-back is a file-consistency test, not proof of physical robot safety.

### List and dry-run the three cases

```powershell
python -m unittest discover -s tests -v
python main.py --experiment cubic --list-cases
python main.py --experiment quintic --list-cases
python main.py --experiment cubic --case 1 --repetitions 1
python main.py --experiment quintic --case 1 --repetitions 1
```

For real hardware, first inspect the actual exported CSVs, assess the planned peak speeds, confirm the controller's ServoP speed factor and check tracking under supervision. Only after that, a **single** case can be launched using `--execute`, for example:

```powershell
python main.py --experiment cubic --case 1 --repetitions 1 --execute
```

Start with case 1 and stop if tracking or physical behavior is unacceptable. **All experiments use the Rigol timebase from `config/common.json`, currently `0.5 s/div` (6-second display span).** Cubic and Quintic no longer automatically widen the scope to 12 seconds. The effective scope setting is logged in `rigol_metadata.json` and `result.json`; change the JSON setting to select a different span without modifying Python. The 6-second display has better time resolution for the same 1,200 preview points, but it can be **shorter than the full acquisition** for the 3.93-second case plus pre/post-roll. Such trials can be marked `partial` with invalid power metrics; do **not** treat their power/energy as quantitatively valid or relax the coverage checks. Scope time is trigger-relative, not aligned automatically with the robot. Full-window Rigol energy is **not** verified motion-only energy.

Once validated, the intended final matrix is 3 cases × 5 repetitions × 2 polynomial profiles = **30 real executions**. No changes are made to trapezoidal, Double-S, Ruckig, or the dedicated ServoP/ServoJ tracking studies by this branch.

### Timing and trial-status diagnostics

The robot's total `MOTION_START` to `MOTION_END` time includes the streamed CSV commands, the final ServoP period and the SDK's `wait_for_motion` idle confirmation. **It is not the nominal polynomial duration.** To avoid conflating these, every polynomial trial now records:

- `planned_trajectory_duration_s = (N - 1)*0.030` and `expected_stream_period_s = N*0.030` for the CSV itself.
- `first_to_last_command_s`, `wait_for_robot_idle_s`, `effective_gain` and `effective_aheadtime` in `result.json` and the trial summary.
- `SERVO_FIRST_COMMAND_SENT`, `SERVO_LAST_COMMAND_SENT`, `SERVO_STREAM_PERIOD_END` and `SERVO_ROBOT_IDLE` in `events.csv`.
- `command_stream_first_to_last_s`, `post_stream_idle_wait_s`, and `tcp_travel_1pct_99pct_s` in `metrics.json` and the trial summary. The physical 1–99% time is calculated from the recorded 3D TCP actual positions projected onto the CSV's commanded start-to-target translation, not from the end-of-command event.

The additional time seen in the first Cubic tests cannot be identified purely as tracking lag; the new timestamps distinguish command pacing, the fixed final period and the wait until robot-idle confirmation. `partial` means robot motion completed but at least one acquisition component failed, and is **counted separately** from `failed` in `experiment_summary.json`. In particular, a 6-second Rigol display does **not** justify overriding the acquisition-coverage validity test for longer recordings. Existing old results are not retroactively rewritten.

The main branch's selected ServoP defaults, **aheadtime=20 and gain=300**, are retained by this study (unless explicitly overridden per case). ServoJ and historical gain-sweep cases keep their distinct defaults. Verify the effective values in `commands.csv` and `trial_summary.csv` before evaluating smoothness.

## Piecewise V/A/J sweep and matched-time control

**Generate the parameter-sweep CSVs in MATLAB** (no input CSV required):

```matlab
run('experiments/piecewise_sweep/generate_piecewise_sweep.m')
```

Edit `caseMatrix` in the MATLAB script to choose the **nine V/A/J rows**.
The script creates **18 CSVs** (9 Trapezoidal + 9 Double-S), writes
`experiments/piecewise_sweep/case_matrix.csv`, reopens and validates every
CSV, prints the limits / duration / sample count / output path in the
MATLAB Command Window, and plots the position, velocity and jerk profiles.
Use `printEveryCsvRow = true` if you want all CSV rows printed too.
Python **reads the MATLAB-exported matrix**, validates each generated
trajectory analytically, and pins the SHA-256 at run selection. You do
not need to edit Python's parameter tuples to change the sweep.

The original [three-case matched-time study](docs/piecewise-test-plan.md)
has its own MATLAB generator:

```matlab
run('experiments/piecewise_fixed_time/generate_matched_piecewise.m')
```

Its Python runner names are `trapezoidal_matched`,
`double_s_matched` and `ruckig_matched`. Those **matched-time**
references use their original fixed-time configuration, independent of
the editable sweep. Ruckig generates points online and therefore needs no
trajectory CSV in either study.

See the [nine-case MATLAB generation and physical-test protocol](docs/piecewise-parameter-sweep.md).

```powershell
python main.py --experiment trapezoidal --list-cases
python main.py --experiment double_s --list-cases
python main.py --experiment ruckig --list-cases
python main.py --experiment double_s --case 1 --repetitions 1
python main.py --experiment double_s_matched --list-cases
```

Real hardware is never commanded without `--execute`. Begin with supervised
single repetitions before moving to faster settings. For the sweep, pass `--config config/piecewise_sweep_rigol_1s.json`
on **every** command (a separate, committed 1.0 s/div scope configuration),
or use another common validated timebase. The 3.93-second
matched-time profiles also need a longer Rigol span than the incomplete
previous 0.5 s/div captures. Do not compare mixed NORM-display timebases
without appropriate resampling and alignment.

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

MoveL / MoveJ cases use **one speed scaling mechanism**: `SpeedFactor(case["speed"])` applies the requested speed percentage globally, while the individual movement has `v=100`. The individual movement still uses `a=case["acceleration"]`. This addresses a regression in which `SpeedFactor(100)` combined with varying `v` produced almost identical measured MoveL TCP speeds on the tested controller. An explicit case `global_speed_factor` still takes precedence. ServoP/ServoJ CSV cases retain their existing speed-factor behavior.

`MOTION_PARAMETERS`, `result.json`, and `trial_summary.csv` record the effective global factor and local movement parameters. Preparation and return-home use the slow settings configured for those phases. The new control strategy is **not yet validated on physical hardware**; `SpeedFactor` may also influence other motion dynamics, so do not assume changing `a` changes acceleration independently.

Before rerunning the full 3×3 MoveL matrix, compare one supervised repetition of cases 1, 4, and 7 (same acceleration 50%, speed 50/75/100%). Do not execute them as an unattended batch:

```powershell
python main.py --experiment movel --case 1 --repetitions 1 --execute
python main.py --experiment movel --case 4 --repetitions 1 --execute
python main.py --experiment movel --case 7 --repetitions 1 --execute
```

Verify each recorded `TCPSpeedTarget` and `TCPSpeedActual` profile and movement duration before proceeding. Previous measurements using `SpeedFactor(100), v=case_speed` and older measurements using *both* `SpeedFactor(case_speed), v=case_speed` are not directly equivalent to these tests.

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

## ServoP behavior experiment (cubic Cartesian reference)

The selected default ServoP tuning is **aheadtime=20, gain=300**, documented
in [the parameter-selection decision](docs/servop-parameter-selection.md).
This default applies to ServoP trajectories that do not override the tuning.
ServoJ defaults and explicit historical parameter-sweep cases are unchanged.

Use the separate [ServoP experiment folder](experiments/servop_behavior/README.md). The committed CSV was generated from the same normalized cubic polynomial as the MATLAB script, and the MATLAB script can regenerate it.

```powershell
python main.py --experiment servop_behavior --list-cases
python main.py --experiment servop_behavior --case 1 --repetitions 1
# Only after supervised validation of the real robot and trajectory:
python main.py --experiment servop_behavior --case 1 --repetitions 1 --execute
```

ServoJ has its own joint-space cubic experiment; it must not reuse the Cartesian ServoP reference.

## ServoJ behavior experiment (cubic joint-space reference)

Use [ServoJ experiment folder](experiments/servoj_behavior/README.md) for
the exact specified six-joint endpoints, MATLAB generator, committed 30 ms
reference CSV, safety checks and nine tracking-parameter cases.

```powershell
python main.py --experiment servoj_behavior --list-cases
python main.py --experiment servoj_behavior --case 1 --repetitions 1
# Real movement ONLY after supervised checks:
python main.py --experiment servoj_behavior --case 1 --repetitions 1 --execute
```
