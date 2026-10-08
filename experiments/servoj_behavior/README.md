# ServoJ behavior — standalone cubic joint-space reference

## Joint configurations

All values are **joint angles in degrees**, not TCP coordinates:

| Joint | Start | End | Delta |
| --- | ---: | ---: | ---: |
| J1 | 26 | -50 | -76 |
| J2 | 53.8 | 54 | +0.2 |
| J3 | 55.2 | 54.9 | -0.3 |
| J4 | 71 | 71.4 | +0.4 |
| J5 | 116 | 40 | -76 |
| J6 | -180.2 | -180.2 | 0 |

The supplied start string `116-180.2` is interpreted as **J5=116,
J6=-180.2**. Confirm that interpretation and the measured joint
configurations on the physical robot before any real execution.

## MATLAB reference generation

Run `make_servoj_cubic_csv.m` directly in MATLAB; it does not read a CSV.
It generates `points_servoj_cubic.csv` beside the script using the same
normalized cubic as ServoP:

`q_i(u) = qStart_i + (qEnd_i-qStart_i) * (3*u^2 - 2*u^3)`,
with `u=t/T` and zero velocities at both ends.

- Sample interval: **30 ms**.
- Reference jointwise velocity bound: **40 deg/s**.
- Reference jointwise acceleration bound: **60 deg/s²**.
- Max displacement: **76°** for J1 and J5.
- Duration: `max(1.5*76/40, sqrt(6*76/60))` rounded to the
  30 ms grid: **2.85 s**, **95 intervals**, **96 rows**.
- Maximum cubic speed: **40 deg/s**; peak acceleration ≈ **56.14 deg/s²**.
- CSV columns: `mode,j1,j2,j3,j4,j5,j6`, with `mode=ServoJ`.

The motion limits above are **initial planner choices, not verified
mechanical/controller limits**. Modify both the MATLAB settings and the
matching Python preflight limits if a different profile is needed.
Reference jerk is constant only within the segment; switching from
standstill at the start/end introduces acceleration discontinuities.

## Parameter cases (fixed reference in all cases)

| Case | Aheadtime | Gain |
| --- | ---: | ---: |
| 1 | 20 | 500 |
| 2 | 20 | 300 |
| 3 | 20 | 700 |
| 4 | 50 | 500 |
| 5 | 50 | 300 |
| 6 | 50 | 700 |
| 7 | 80 | 500 |
| 8 | 80 | 300 |
| 9 | 80 | 700 |

The SDK accepts `aheadtime` in [20,100], `gain` in [200,1000].
Every case uses a global speed factor of 100 and logs the actual servo
parameters in `commands.csv`. Preparation and return-home use the
configured slow movements.

## Run from repository root

```powershell
python main.py --experiment servoj_behavior --list-cases
python main.py --experiment servoj_behavior --case 1 --repetitions 1
# Only after supervising and verifying the *complete joint-motion* path:
python main.py --experiment servoj_behavior --case 1 --repetitions 1 --execute
```

No `--execute` means **dry-run**. The loader checks joint headers,
ServoJ mode, endpoints, exact cubic shape, minimum sample count and
30 ms period before any robot connection.

## Scientific comparison and safety

The ServoJ path is a straight line **in joint coordinates**, which
normally produces a curved and changing-orientation **TCP path**. It is
not the Cartesian straight line used by ServoP/MoveL. Consequently,
ServoJ and ServoP metrics should be compared with this geometrical
difference explicitly stated. For a controlled comparison of different
servo *interfaces* following the same TCP path, a separate inverse-
kinematics reference would be required, including branch continuity.

Before actual execution check all robot joint limits, singularities,
tool orientation, payload, self-collision, workspace clearance, cable
clearance, and appropriate emergency-stop access. Numeric endpoints and
reference velocity limits alone do not prove a safe physical path.
Software tests do not control real hardware, and oscillation/
overshoot can differ substantially with gains.

The existing scope analysis integrates full capture energy, **not
motion-only energy**, pending robot-to-scope time synchronization.
