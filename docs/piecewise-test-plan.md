# Matched-time piecewise study (Trapezoidal / Double-S / Ruckig)

## Motivation and source

The hardware comparison uses the same Cartesian 800 mm Y translation as the
finished MoveL, Cubic and Quintic studies, without changing the six-axis TCP
orientation. The final MoveL speed levels motivate grid-aligned **planned**
durations 3.93, 2.79, and 2.31 s (30 ms ServoP command period). Sources:

- `Final Results/moveL/20261009_134603_564176/`
- `Final Results/cubic/20261009_161123_377529/`
- `Final Results/quintic/20261009_160434_847097/`

The Cubic and Quintic batches have **15 runs each, 10 completed + 5 partial**:
all five 3.93 s trials have incomplete Rigol power capture at the configured
0.5 s/div (six-second scope span). Do **not** count the missing power metrics
as zeros or claim those traces are full-window comparable. Cubic and Quintic
also exceed the empirical ~470.5 mm/s MoveL plateau in their fastest cases;
these are different peak-speed studies.

## Experimental matrix

| Case | Reference duration | Samples, offline profiles | Planned peak speed limit | Trapezoid acceleration | Double-S peak acceleration | Double-S peak jerk |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 3.93 s | 132 | 300 mm/s | 237.47 mm/s² | 316.62 mm/s² | 1002.50 mm/s³ |
| 2 | 2.79 s | 94 | 400 mm/s | 506.33 mm/s² | 675.11 mm/s² | 3418.26 mm/s³ |
| 3 | 2.31 s | 78 | 460 mm/s | 805.79 mm/s² | 1074.38 mm/s² | 7528.05 mm/s³ |

Both offline profiles are symmetric rest-to-rest trajectories with a true
constant-speed middle section. With displacement D=800 mm, time T and selected
peak speed V, their shared acceleration-phase duration is r=T-D/V and cruise
duration T-2r. Trapezoid uses constant acceleration V/r in each ramp,
causing **unbounded ideal jerk at phase boundaries**. Double-S uses
(+j,0,-j) acceleration and its mirror deceleration, with a jerk phase lasting
r/4 and constant-acceleration phase lasting r/2; its peak acceleration is
V/(3r/4), and jerk is that acceleration divided by r/4.

Ruckig uses online ServoP setpoints with the **same V, Double-S acceleration
and jerk limits** and `minimum_duration_s=T`. Ruckig is minimum-duration
constrained, **not analytically fixed to exactly T**; record the actual
planner duration and TCP travel duration before making equal-time claims.
Its first online setpoint begins at t=30 ms rather than the offline CSV's
t=0 sample; inspect this 30 ms command-grid difference. All trajectories
use `SpeedFactor(100)` and ServoP defaults `aheadtime=20, gain=300`,
unless explicitly overridden.

These limits were chosen as conservative **nominal comparisons**, not a
validated robot acceleration, jerk, or payload envelope. The fastest V=460
mm/s remains below the *observed* MoveL plateau, but this observation is
not a physical safety certification. Verify work envelope, payload, endpoint
orientation, motion continuity, and SDK/controller limits before execution.

## Regeneration and offline preflight

The six offline reference CSVs are committed and checked analytically for
every sample, monotonic Y, exact endpoints, expected row counts, and SHA-256
at case selection and before physical execution. Regenerate them with:

```matlab
run('experiments/piecewise_fixed_time/generate_matched_piecewise.m')
```

The MATLAB generator writes all six CSVs from the same equations. No external
CSV is needed; it reopens each export and verifies sampled values.

```powershell
python -m unittest discover -s tests -v
python main.py --experiment trapezoidal --list-cases
python main.py --experiment double_s --list-cases
python main.py --experiment ruckig --list-cases
python main.py --experiment trapezoidal --case 1 --repetitions 1
python main.py --experiment double_s --case 1 --repetitions 1
python main.py --experiment ruckig --case 1 --repetitions 1
```

No `--execute` means no physical robot motion. Existing `--csv` overrides
remain supported for Trapezoidal and Double-S as custom single-file runs,
which are not part of the fixed-time matrix.

## Physical execution order and Rigol warning

**First** conduct one supervised case-1 check per profile, then inspect the
actual path, feedback, `commands.csv`, rigol screenshot, pulse transients,
tracking and the logged servo parameters. Proceed to case 2 and then case 3
only if the previous case is physically acceptable. Five repetitions per
validated case give **45 executions** (3 profiles x 3 cases x 5 repeats).

```powershell
python main.py --experiment trapezoidal --case 1 --repetitions 1 --execute
python main.py --experiment double_s --case 1 --repetitions 1 --execute
python main.py --experiment ruckig --case 1 --repetitions 1 --execute
# Repeat individually with --case 2 and finally --case 3 after review.
# After validation use --repetitions 5 for the selected case.
```

At 0.5 s/div, the Rigol 6 s displayed span is insufficient to capture
all pre-/post-roll and the long 3.93 s motion, as already observed with
Cubic/Quintic. For case 1, prepare a **separate configuration file** copied
from `config/common.json` with
`"rigol_horizontal_scale_s_per_div": 1.0`, and pass it with `--config`.
This covers a 12 s display but reduces the NORM display's sampling density.
Keep 0.5 s/div for the shorter case-2/3 smoothness comparisons. Do not
compare short-timescale RMS from 6 s and 12 s NORM traces without normalizing
sampling and aligning equivalent physical motion windows. The scope and
robot clocks do not have verified synchronization; full-scope energy is
**not** motion-only energy.

For analysis, prioritize **motion-window TCP tracking RMSE**, actual 1%-99%
TCP travel time, maximum TCP speed, command lateness, and motion-equivalent
Rigol power fluctuation after verifying calibration and coverage. Compare
profiles within the same duration and scope setting; do not rank an
incomplete/partial scope record for Rigol smoothness.
