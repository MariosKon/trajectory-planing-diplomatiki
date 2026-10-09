# Nine-case piecewise velocity/acceleration/jerk study

The unsuffixed experiments `trapezoidal`, `double_s`, and `ruckig`
run this **nine-case parameter sweep**. The original three-case matched-time
comparison remains separately available as `trapezoidal_matched`,
`double_s_matched`, and `ruckig_matched` (see `piecewise-test-plan.md`).

All use the same 800 mm Cartesian Y translation, unchanged orientation,
30 ms ServoP, SpeedFactor=100, aheadtime=20 and gain=300.

| Case | Velocity limit (mm/s) | Acceleration limit (mm/s²) | Jerk limit (mm/s³) |
| --- | ---: | ---: | ---: |
| 1 | 300 | 500 | 6000 |
| 2 | 300 | 800 | 10000 |
| 3 | 300 | 1100 | 16000 |
| 4 | 380 | 500 | 10000 |
| 5 | 380 | 800 | 16000 |
| 6 | 380 | 1100 | 6000 |
| 7 | 460 | 500 | 16000 |
| 8 | 460 | 800 | 6000 |
| 9 | 460 | 1100 | 10000 |

- **Trapezoidal:** all nine V/A combinations, ideal jerk unbounded at
  acceleration discontinuities. J entries in this table do not apply.
- **Double-S and Ruckig:** balanced L9(3³) design; every V/A, V/J and
  A/J pair appears once. This screens main effects but does not resolve
  interactions (full factorial is 27 cases for either planner).
- **Time:** not held fixed. For trapezoid, continuous minimum time is
  D/V+V/A. For Double-S it is D/V+V/A+A/J (D=800 mm). Profiles have positive
  cruise and acceleration plateau for all selected parameter levels.
  Offline CSVs are uniformly stretched to a 30 ms endpoint grid, reducing
  attained peak V/A/J. Ruckig is an online minimum-time profile using the
  *unscaled* limits, so it may differ in planned time and command onset.

Regenerate the 18 checked CSV files and inspect the CLI case matrix:

```powershell
python -m experiments.piecewise_sweep.generate
python -m unittest discover -s tests -v
python main.py --experiment trapezoidal --list-cases
python main.py --experiment double_s --list-cases
python main.py --experiment ruckig --list-cases
# Optional scope verification for the actual sweep:
python main.py --experiment double_s --case 1 --repetitions 1 --config config/piecewise_sweep_rigol_1s.json
```

Each CSV is checked analytically at case-selection time and SHA-256
revalidated before commanding motion. The older matched-time experiments
can be listed by appending `_matched`.

**Rigol methodology:** previous 3.93 s Cubic/Quintic trials had incomplete
0.5 s/div scope coverage. For comparable power fluctuation across the sweep,
use the committed `config/piecewise_sweep_rigol_1s.json` via
`--config` for **all** sweep cases (1.0 s/div, 12 s NORM window);
do not modify the normal `config/common.json`. Verify capture coverage and acknowledge
the lower high-frequency resolution. Do not compare raw NORM signals
captured with different timebases without alignment and resampling;
the oscilloscope and robot do not have verified clock alignment, and
scope energy is not validated motion-only energy.

**Safety:** The V/A/J limits are commanded Cartesian path quantities, not
independently verified hardware, joint-level or payload safety limits.
The 460 mm/s choice stays below the empirical MoveL plateau, but this
is not a safety certificate. Supervise individual runs starting with
cases 1, 4 and 7, confirm clearances, tracking, power and fault-free
behavior, then qualify higher acceleration levels before batching.
Use `--execute` only after explicit physical review.

3 profiles × 9 cases × 5 repeats means **135 hardware trials** after
qualification. Report per-case measured physical 1–99% TCP travel time,
tracking RMSE, actual peak speed, timing lateness, Rigol power waveform
fluctuation and valid capture coverage. Because limits change motion
duration and attained speed, the L9 main effects are *exploratory*
associations, not isolated equal-time causal effects.
