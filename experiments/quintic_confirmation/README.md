# Quintic ServoP confirmation study

Three cases, five repetitions per case (**15 runs total**):

| Case | aheadtime | gain | repetitions |
| --- | ---: | ---: | ---: |
| 1 | 20 | 300 | 5 |
| 2 | 20 | 500 | 5 |
| 3 | 50 | 300 | 5 |

All cases read **exactly one file**, `experiments/quintic/points_quintic.csv`.
It is a 68-point, 30 ms, 2.01 s grid-aligned **quintic ServoP** profile:
`s(u)=10u^3-15u^4+6u^5`. It uses the unchanged Cartesian endpoints
`[-600,-400,250,-90,0,90]` and `[-600,400,250,-90,0,90]`.
The nominal 2.0 second trajectory duration is rounded up to the fixed
30 ms grid (2.01 s). The CSV is committed; running MATLAB is not necessary.

A SHA-256 digest is recorded in each case and checked immediately before
streaming. **Only** aheadtime and gain change between the three cases.
Payload, home/start/end configuration, servo sampling period, and Rigol
and camera acquisition settings all come from the **unchanged**
`config/common.json` and normal `LoggingManager`. The existing
default `global_speed_factor=100` is used for all three cases.

No physical safety validation has been conducted for this new matrix.
Inspect workspace and payload, then perform a supervised first trial.

From the repository root:

```powershell
python main.py --experiment quintic_confirmation --list-cases
python main.py --experiment quintic_confirmation --repetitions 5
# Only after verifying the robot and acquisition hardware:
python main.py --experiment quintic_confirmation --case 1 --repetitions 1 --execute
python main.py --experiment quintic_confirmation --repetitions 5 --execute
```

Results are written under `results/quintic_confirmation/`. For every
trial, `commands.csv` logs the applied ServoP parameters and lateness.
Changing the CSV between cases invalidates this controlled comparison.
