# Payload sensitivity study — fastest tested Cartesian trajectories

**Branch:** `experiment/payload-analysis` (9 October 2026).

## Goal and design

Compare the recorded Rigol electrical-power traces and robot tracking for
the **same six trajectories** under three manually established physical
payload conditions: `baseline` (as-is), `full`, and `empty`.
By default, run **one repetition of each algorithm per condition**:
six trials per load condition, **18 trials total**. After validating the
recordings and physical behavior, pass `--repetitions 5` for five
repetitions per algorithm (**30 trials per condition, 90 total**).
Every phase is launched independently. No software operation changes the contents or attachment
of the physical payload.

For a liquid container, define full and empty based on the *same* vessel,
tooling, mounting and location, where feasible. Record total effective
mass (including the vessel), liquid mass/fill condition, and center-of-mass
changes. The `baseline` phase preserves whatever physical setup existed
before the test and must be accurately documented; it is not automatically
an empty or full condition. These three conditions are categorical
experimental labels, not robot commands.

The original motion parameters were exercised in the 2026-10-09 final
hardware runs. This does **not** validate the same trajectories with
heavier, shifted, or liquid payloads: verify load limits, clearance,
fixture stability and possible liquid sloshing before real motion.

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

## Three deliberately separate commands

From the project root, run offline checks and verify the cases:

```powershell
python -m unittest discover -s tests -v
python main.py --experiment payload --list-cases
python main.py --experiment payload --payload-phase baseline
```

After inspecting the physical setup, instrument configuration, loading,
path, speed and safety limits, run the **as-is** condition:

```powershell
python main.py --experiment payload --payload-phase baseline --execute
```

The process exits after six trials. Review `trial_summary.csv`,
`experiment_summary.json`, feedback, Rigol traces, and camera recording.
If a movement fails, do not proceed. If a recording is `partial`, inspect
its acquisition validity before using its power statistics.

For final measurements after each payload setup has passed a supervised
single-repetition check, add `--repetitions 5` to **each** phase's
command. For example, the final baseline run is:

```powershell
python main.py --experiment payload --payload-phase baseline --repetitions 5 --execute
```

Repeat with `--payload-phase full` and `--payload-phase empty`
in separately supervised invocations. The existing runner groups five
repetitions of each of the six selected trajectories and saves individual
trial folders; it stops a batch on a failed movement. Prior pilot
measurements are separate and not automatically included in the
five-repetition final analysis.

Safely stop motion, establish the **full** physical condition and verify
tool mass, mounting, center of mass, limits and clearances again.
Only then start the next command:

```powershell
python main.py --experiment payload --payload-phase full --execute
```

Repeat the mechanical checks after changing to the **empty** condition
(same vessel/mounting when possible):

```powershell
python main.py --experiment payload --payload-phase empty --execute
```

These are independent six-case runs, *not* a continuous unattended
18-motion sequence. You can choose the physical order for safety and
convenience; the phase labels describe the actual load, not its order.

Optionally append `--payload-mass-kg N` to **each** phase command
(where N is a measured nonnegative mass in kg). This field is
**recording metadata only**, not the robot's configured `SetPayload` value.
Use measured totals; do not enter guesses.

## Robot controller payload versus measured physical payload

The new `physical_payload_mass_kg` case field does **not** call the robot's
`SetPayload` command. The existing runner programs `SetPayload` only
when `config.payload_kg` is specified **and** `config.tool_index` is
configured. Independently review and set these configuration values when
appropriate for the tool and physical mass; do not assume an attached load
is automatically configured because `--payload-mass-kg` was provided.

Keep all the non-payload test conditions identical across all three conditions:
tool TCP, workspace/path, fixture location, ServoP tuning, Rigol
current-probe position and scale, timebase, camera, and logger setup.
The existing `config/common.json` selects 0.5 s/div (nominal 6 s
scope window). Save each phase's copied `configuration.json` to
track any deliberate controller-payload changes.

## Output and interpretation

The three invocations save into independent directories:

- `results/payload/baseline/<timestamp>/`
- `results/payload/full/<timestamp>/`
- `results/payload/empty/<timestamp>/`

Each uses the standard `case_001` through `case_006` and
`trial_001` through `trial_00N` folders (N is the requested number of
repetitions), `case.json`, robot feedback and
`commands.csv` where applicable, Rigol power trace, scope screenshot,
camera recording, `trial_summary.csv`, and aggregate JSON.
The aggregate CSV additionally identifies `trajectory_profile`,
`reference_case_name`, `source_case_index`, `payload_phase`, and
`physical_payload_mass_kg`. Original CSV reference SHA-256 checks
remain in force before robot motion.

Suggested comparison for each **algorithm across all three load conditions**: overlay the Rigol
power waveforms on a consistent time axis, compare a clearly defined
motion-relative power statistic only when synchronization supports it,
compare TCP position error, actual motion duration and joint velocities,
and inspect the footage. Do not treat the existing scope-wide
`rigol_acquisition_energy_J` as synchronized motion-only energy,
or infer physical vibration directly from power-trace variability.
A single repetition per condition cannot estimate test-to-test variability.
With five repetitions, calculate per-algorithm means and standard deviations
for each load, then compare condition differences while acknowledging that
a small sample does not establish statistical certainty.
