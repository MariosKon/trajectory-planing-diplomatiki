# ServoJ / ServoP parameter evaluation

This feature studies the DOBOT SDK's **ServoJ (joint space)** and **ServoP
(Cartesian space)** commands. The SDK provides no command named ServoL;
ServoP is the Cartesian counterpart.

## Experimental design

The trajectory samples and their 30 ms scheduling period stay **identical**
across cases for a given mode. We change only \`aheadtime\` and \`gain\`.

| Case | aheadtime | gain |
|---:|---:|---:|
| 1 | 20 | 300 |
| 2 | 20 | 500 |
| 3 | 20 | 800 |
| 4 | 50 | 300 |
| 5 | 50 | 500 |
| 6 | 50 | 800 |
| 7 | 80 | 300 |
| 8 | 80 | 500 |
| 9 | 80 | 800 |

The SDK accepts \`aheadtime\` in the range 20–100 and \`gain\` in the
range 200–1000. The initial grid avoids the extremes at which tracking may
be unstable. Do not assume a particular combination is safe without first
observing a controlled low-risk trial.

Both modes require an **explicit user-supplied CSV**. We do not generate
joint-space trajectories by renaming Cartesian columns: ServoJ expects six
joint angles, while ServoP expects six Cartesian pose coordinates.

\`\`\`csv
mode,x1,x2,x3,x4,x5,x6
ServoP,-600,-400,250,-90,0,90
ServoP,-600,-399.9,250,-90,0,90
...
\`\`\`

Use \`ServoJ\` and six legitimate joint angles on every row for a
joint-space test. The CSV file must have at least five rows, only one
servo mode, six finite coordinates per row, and different first/last
points. Samples are interpreted at exactly \`servo_time_s=0.03\` seconds;
the CSV does not carry separate timestamps. Every case checks the SHA256
digest of the file again before commanding the robot so a file edited
after parameter generation cannot silently change the trajectory.

## CLI workflow

With the **same validated CSV for all nine cases**:

\`\`\`powershell
python main.py --experiment servop_params --csv "C:\path\servo_p_points.csv" --list-cases
python main.py --experiment servop_params --csv "C:\path\servo_p_points.csv" --case 1 --repetitions 1
python main.py --experiment servoj_params --csv "C:\path\servo_j_points.csv" --case 1 --repetitions 1
\`\`\`

The examples above are dry runs; no robot commands are sent. Only after
verifying the trajectory, workspace and configuration, and performing
the corresponding supervised test, add \`--execute\`.

For fully verified experiments, \`--repetitions 3\` executes nine
combinations × three repetitions = 27 trials per mode. Begin with one
low-risk case first, under supervision. Runs abort upon failed motion or
logging.

The existing robot feedback, Rigol, video, event and metric logging are
reused. Every streamed command logs \`servo_t_s\`, \`aheadtime\`, \`gain\`,
command delay, command time, and the target point. Parameter settings are
also saved per case. Tracking RMSE uses the actual movement event interval.

## Limits and interpretation

- The 6 s scope window (0.5 s/div) may not cover a long CSV trajectory.
  The case generator rejects a test if the approximate planned duration,
  scope pre-roll, and configured post-roll exceed that window. Increase
  \`rigol_horizontal_scale_s_per_div\` for longer trials and recheck
  instrument response before execution.
- Rigol energy covers the **scope acquisition**, not synchronized
  motion-only electrical energy.
- The comparison isolates ServoJ gains within ServoJ and ServoP gains
  within ServoP; different coordinate spaces are not directly comparable
  merely because the same parameter values are used.
- The planner/CSV generator is intentionally not modified by this feature.
  Provide and review separately validated command sequences for each mode.
- The current method assumes the DOBOT controller accepts the supplied
  command rate and all target poses. SDK range validation alone is not
  a collision or feasibility check.
