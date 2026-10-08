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
