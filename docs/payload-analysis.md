# Payload sensitivity study — fastest tested Cartesian trajectories

**Branch:** `experiment/payload-analysis` (9 October 2026).

## Goal and design

Compare the recorded Rigol electrical-power trace and the robot's tracking
of the **same six trajectories** before and after a manually changed physical
payload. Execute **one repetition of each algorithm per load condition**:
six trials before the change and six after, **12 trials total**.
This is a preliminary paired comparison, not a statistical repeatability study.

The original motion parameters have already been exercised in the
2026-10-09 final hardware runs. This does **not** validate the same commands
for any heavier or differently mounted payload: check mass, robot limits,
mounting, clearance and stability again before enabling real motion.

| Payload order | Existing experiment | 1-based source case | Selected fastest previously tested profile |
| --- | --- | ---: | --- |
| 1 | `movel` | 9 | Global SpeedFactor 100%, MoveL acceleration 100%; local `v=100` |
| 2 | `cubic` | 3 | ServoP Cartesian cubic, prescribed duration 2.31 s |
| 3 | `quintic` | 3 | ServoP Cartesian quintic, prescribed duration 2.31 s |
| 4 | `double_s` | 9 | L9 sweep: V 460 mm/s, A 1100 mm/s², J 10000 mm/s³; nominal duration 2.28 s |
| 5 | `ruckig` | 9 | Online L9 sweep: V 460 mm/s, A 1100 mm/s², J 10000 mm/s³; duration determined by Ruckig |
| 6 | `trapezoidal` | 9 | L9 sweep: V 460 mm/s, A 1100 mm/s²; nominal duration 2.16 s; jerk is unbounded at transitions |

All use the committed same 800 mm Cartesian path, with start
`[-600,-400,250,-90,0,90]` and target `[-600,400,250,-90,0,90]`
(position in mm). For ServoP, sampling is 30 ms, global speed 100%,
default aheadtime 20 and gain 300; MoveL speed factor is 100%.
These settings are inherited, not reimplemented, from their original
`cases_for` experiments.

**Validation provenance:** `Final Results/moveL/20261009_134603_564176/`,
`cubic/20261009_161123_377529/`,
`quintic/20261009_160434_847097/`,
`double_s/20261009_190853_762003/`,
`ruckig/20261009_183413_094588/`, and
`trapezoidal/20261009_200102_901531/` under `Final Results/`.
All selected source cases have five physically recorded **completed** trials
(no selected-case `partial` statuses in those data sets). The selected
fastest Cubic and Quintic references have analytic peak speeds above the
measured fast MoveL plateau; do not conflate equal path duration with
equal maximum speed or assume clearance for a heavier load.

## Two deliberately separate commands

Run from the project root. First inspect the selected cases and perform
a dry run (no robot commands):

```powershell
python -m unittest discover -s tests -v
python main.py --experiment payload --list-cases
python main.py --experiment payload --payload-phase baseline
```

After checking mechanical safety, logger settings, controller configuration,
and the dry-run case listing, record the **first physical load**:

```powershell
python main.py --experiment payload --payload-phase baseline --execute
```

**The program exits after these six trials. It never continues on its own
with a new payload.** Review the baseline's `trial_summary.csv`,
`experiment_summary.json`, robot traces, Rigol waveforms and video. If any
movement failed, do not proceed; if a capture is `partial`, evaluate
whether it should be rerun before interpreting the power trace.

Stop the robot and safely change the payload **manually**. Verify mechanical
attachment, robot payload/load limits, tool configuration, clearance and
safe homing with the altered load. With the changed payload installed,
and only after confirming that the experiment path and speed are still
acceptable, explicitly start the second phase:

```powershell
python main.py --experiment payload --payload-phase changed --execute
```

To record a physically measured load (in kilograms), append
`--payload-mass-kg <measured_value>` **separately to both phase commands**.
This option is metadata only and does not change the robot's payload
compensation. Do not enter a guessed mass. The total mass, contents and
mounting / center of mass should also be recorded in lab notes.

## Robot controller payload versus measured physical payload

The new `physical_payload_mass_kg` case field does **not** call the robot's
`SetPayload` command. The existing runner programs `SetPayload` only
when `config.payload_kg` is specified **and** `config.tool_index` is
configured. Independently review and set these configuration values when
appropriate for the tool and physical mass; do not assume an attached load
is automatically configured because `--payload-mass-kg` was provided.

Keep all the non-payload test conditions identical between phases:
tool TCP, workspace/path, fixture location, ServoP tuning, Rigol
current-probe position and scale, timebase, camera, and logger setup.
The existing `config/common.json` selects 0.5 s/div (nominal 6 s
scope window). Save each phase's copied `configuration.json` to
track any deliberate controller-payload changes.

## Output and interpretation

The two invocations save into independent directories:

- `results/payload/baseline/<timestamp>/`
- `results/payload/changed/<timestamp>/`

Each uses the standard `case_001` through `case_006` and
`trial_001` folders, `case.json`, robot feedback and
`commands.csv` where applicable, Rigol power trace, scope screenshot,
camera recording, `trial_summary.csv`, and aggregate JSON.
The aggregate CSV additionally identifies `trajectory_profile`,
`reference_case_name`, `source_case_index`, `payload_phase`, and
`physical_payload_mass_kg`. Original CSV reference SHA-256 checks
remain in force before robot motion.

Suggested comparison for each **paired algorithm**: overlay the Rigol
power waveforms on a consistent time axis, compare a clearly defined
motion-relative power statistic only when synchronization supports it,
compare TCP position error, actual motion duration and joint velocities,
and inspect the footage. Do not treat the existing scope-wide
`rigol_acquisition_energy_J` as synchronized motion-only energy,
or infer physical vibration directly from power-trace variability.
A single repetition per condition cannot estimate test-to-test variability;
repeat only if the initial signal provides a clear, valid comparison.
