# ServoP behavior — fixed Cartesian cubic trajectory

This folder is self-contained for the **ServoP** experiment; ServoJ uses its own joint-space CSV.

## Reference trajectory

The exact same configured endpoints as MoveL:

- start = `[-600,-400,250,-90,0,90]`
- end   = `[-600, 400,250,-90,0,90]`
- 800 mm along Y, constant TCP orientation.
- MATLAB script: `make_servop_cubic_csv.m` (hardcoded endpoints, no CSV input).
- Committed reference: `points_servop_cubic.csv`, with `mode,x1,...,x6` columns.
- Requested duration **T = 2.00 s** (no Vmax/Amax inputs).
- Grid-aligned duration **2.01 s**, with 67 intervals / 68 points at 30 ms.
- Cubic: `s(u)=3u^2-2u^3`; theoretical peak speed ≈ **597.01 mm/s**, acceleration ≈ **1188.09 mm/s²**, not imposed safety limits.
- Cubic acceleration changes discontinuously at the start/end when motion
  transitions from standstill; avoid interpreting jerk as bounded there.

Regenerate the CSV in MATLAB by opening this folder and running:

```matlab
make_servop_cubic_csv
```

The script writes beside itself regardless of the MATLAB current folder.
Inspect the plotted path and generated CSV before running on hardware.

## Servo parameter grid

Every case streams **exactly the same CSV**, changing only `aheadtime`
and `gain`. Parameters are SDK-native (aheadtime 20–100, gain 200–1000):

| Gain / aheadtime | 20 | 50 | 80 |
| --- | --- | --- | --- |
| 500 | case 1 | case 4 | case 7 |
| 300 | case 2 | case 5 | case 8 |
| 700 | case 3 | case 6 | case 9 |

`global_speed_factor=100` is applied to every case, as it is for MoveL.
Preparation and return-home use the common slow settings.

## Execute from repository root

```powershell
python main.py --experiment servop_behavior --list-cases
python main.py --experiment servop_behavior --case 1 --repetitions 1
# Real movement only after checking robot setup, payload, path, and timing:
python main.py --experiment servop_behavior --case 1 --repetitions 1 --execute
# Optional: an alternative CSV with the same endpoints/straight line and ServoP mode:
python main.py --experiment servop_behavior --csv "C:\\path\\to\\points.csv" --list-cases
```

Without `--execute`, the framework performs a dry run; it does not move
the robot. CSV header/mode/endpoints/linearity, and the 30 ms config period
are checked **before** connection. Physical acceleration, workspace clearance,
sample-delivery jitter, motion completion, and the meaning of per-case gains
still require supervised verification on the real robot.

For each trial, `commands.csv` now records the actual case's `aheadtime`,
`gain`, and `servo_t_s` alongside sending lateness and command duration.
`trial_summary.csv` also contains these parameters and the existing tracking
metrics. Robot and oscilloscope acquisition clocks are not automatically
aligned; do not attribute full-scope energy to the move alone.

**Important comparability caveat:** matching Cartesian endpoints and geometry
does **not** mean the MoveL percentage speed/acceleration matrix has equal
motion durations or limits. Compare durations and actual TCP kinematics too.
