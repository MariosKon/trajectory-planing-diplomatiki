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

## Select a single test case

List the numbered parameter combinations without connecting to the robot:

```powershell
python main.py --experiment movel --list-cases
```

Check case 1 without robot movement:

```powershell
python main.py --experiment movel --case 1 --repetitions 1
```

After confirming the configuration and under supervision only, add `--execute`.
The `--case` option is 1-based and rejects an invalid index. If omitted, all cases are selected.

## October 8 Rigol ROLL-mode diagnosis

The observed DS1202Z-E recording had a 5 s/div ROLL display but exported only ~3.21 seconds of data at scope time -30 to -26.79 seconds. These are not equivalent to the current display; old acquisition energy results must not be used. The logger now explicitly requires `:TIM:MODE MAIN`, checks `:TRIG:STAT?` reports STOP, and waits at least one configured 12-division screen span (default 0.5 s/div = 6 s) from the RUN command before stopping. This is a deliberately conservative diagnostic capture and is not precise hardware synchronization with the robot. Inspect `rigol_screen.png`, `rigol_metadata.json`, and both channel CSVs and validate behavior with a supervised single run. `rigol_horizontal_scale_s_per_div` can be adjusted to suit longer motion; do not automatically use 5 s/div for short moves because it gives a 60-second window. Instrument readback `:ACQ:MDEP?` returning `AUTO` is a warning, not proof of the requested fixed record length.

## Rigol display-vs-RAW polarity (October 8 follow-up)

A supervised MAIN-mode acquisition covered the complete 6-second window, but
the Rigol CH1 NORM display trace had a positive current peak (~1.58 A)
while the RAW BYTE preamble conversion yielded a negative peak (~-1.61 A).
The old RAW-derived report (-100.76 J acquisition energy) is invalid.
The 1200-point display trace (with CH2 voltage near 47.7 V) gives an
approximate +67.14 J **full-acquisition signed energy** and +74.58 W peak;
this is diagnostic, not motion-only energy or verified absolute calibration.

Until RAW scaling is resolved against the actual instrument, `rigol_scope.csv`
and `core/analysis.py` use the instrument's NORM display traces for I and V
to avoid the observed sign reversal. Raw channel CSVs and preambles remain
available for investigation. Metadata includes `power_trace_source`,
`raw_display_comparison`, and `movement_only_energy_valid=false`. This
reduces the reported time resolution to the display's 1200 points; do not
compare short high-frequency transients or calculate motion-only energy
without hardware trigger synchronization. Do not silently reverse the sign
of RAW samples as a workaround. Validate current-probe polarity and ratio
with an independently known load before interpreting electrical energy.

## Motion-window robot metrics

From this change, robot tracking RMSE, maximum tracking deviation, and
joint/TCP speed peaks use only feedback records whose host timestamps are
between `MOTION_START` and `MOTION_END`. The metrics include
`robot_samples`, `robot_motion_samples`, and
`robot_motion_window_valid`; without a valid motion window, tracking
metrics are left null instead of reporting idle/download time as motion.
The robot feedback logger is stopped before long Rigol VISA RAW transfers.

Scope energy remains a **full-window estimate** and is **not aligned** to
the robot motion interval. The latest measured NORM waveform gave about
66.92 J over a six-second acquisition with 73.63 W peak power, but the
current excursion starts at the left screen boundary. Those results remain
diagnostic pending controlled acquisition placement and calibration.
