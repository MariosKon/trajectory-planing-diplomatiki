# DOBOT Trajectory Experiments

Refactored experiment framework.

## Structure
- `core/` — robot control, configuration, repeated trials, analysis
- `loggers/` — robot, Rigol, camera, logging manager
- `experiments/` — independent experiment helpers and MATLAB planners
- `results/` — one directory per experiment batch

## Dependencies

Install the DOBOT SDK dependencies and:

    pip install -r requirements.txt

The original `TCP-IP-Python-V4` folder belongs in this project's root.

## Dry run

    python main.py --experiment movel --repetitions 3

No physical robot commands are sent.

## Real execution

    python main.py --experiment movel --repetitions 3 --execute

## Offline trajectory

First run the corresponding MATLAB script and provide its CSV:

    python main.py --experiment cubic --csv PATH_TO_POINTS.csv --execute

## Ruckig

    python main.py --experiment ruckig --repetitions 3 --execute

## Outputs

Each trial records:
- feedback.csv and feedback_raw.bin
- commands.csv when relevant
- rigol_scope.csv when enabled
- camera.mp4 when enabled
- events.csv
- result.json
- metrics.csv and metrics.json

Each batch records trial_summary.csv and experiment_summary.json.

Camera analysis is intentionally not implemented.

IMPORTANT:
Hardware behavior, positioning, timing, and safety must be verified
with a supervised single trial before any repeated experiment.


## Rigol measurement validation (October 2026)

The Rigol logger now configures horizontal scale and memory depth **before**
starting acquisition. It saves original channel samples in
`rigol_chan1_raw.csv` and `rigol_chan2_raw.csv`, and the oscilloscope
preambles, actual sampling intervals, time windows, and warnings in
`rigol_metadata.json`.

Configure these settings in `config/common.json`:

```json
{
  "rigol_horizontal_scale_s_per_div": 5.0,
  "rigol_memory_depth": 60000,
  "rigol_preview_points": 2000,
  "rigol_current_A_per_unit": null,
  "rigol_voltage_V_per_unit": 1.0
}
```

**Calibration:** When CHAN1 is measured in amperes, the logger interprets its
readings as current. When it is in volts, explicitly supply the verified
A-per-displayed-volt conversion factor; otherwise current and power values
will be NaN rather than fictitious measurements. The scope's `time_s` axis
is trigger-relative; it is **not** a host timestamp and cannot by itself
identify the exact motion interval. Energy currently covers the oscilloscope
acquisition window, not necessarily the robot's movement alone.

The combined `rigol_scope.csv` is a downsampled visualization, with power
calculated at original sampling resolution. For scientific processing use
the original channel CSVs and recorded waveform preambles. Validate the
instrument's horizontal span before any robot motion. The model may reject
memory-depth settings that it does not support.

For MoveL and MoveJ, the global speed factor is set to 100% during the
measured motion, and the case speed percentage is passed only to the
motion command. Preparation and return-home use the configured slow global
factor. Do not start unattended batch tests until target-arrival verification
and device acquisition have been validated with a supervised single run.

Offline tests:

```powershell
python -m unittest discover -s tests -v
```
