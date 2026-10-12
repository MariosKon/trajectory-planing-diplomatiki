# Liquid video post-processing

This folder contains the thesis video-analysis pipeline for the `Final Results` dataset.

## Timing rule

Robot start and stop are determined from the **video**, not logger timestamps. The detector uses the calibrated vessel endpoint positions, determines the travel direction independently for each video, and refines start/stop at native frame rate.

The post-motion FFT is the **first 1.0 s immediately after the visually detected stop**.

Logger events remain in the summary only as diagnostics because camera and robot timestamps are not synchronized.

## Linux setup

```bash
cd video_post_processing
chmod +x setup_video_env.sh
./setup_video_env.sh
```

Do not commit the generated `video_env/` directory. The setup script and `requirements-video.txt` reproduce it.

## Windows PowerShell setup

From `video_post_processing\`:

```powershell
.\setup_video_env.ps1
```

If PowerShell blocks local scripts, either run the setup directly with:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_video_env.ps1
```

or use the venv commands manually.

Run the regression tests on Windows with:

```powershell
.\video_env\Scripts\python.exe .\test_motion_detector.py
```

Fast dataset validation on Windows:

```powershell
.\video_env\Scripts\python.exe .\Video_post_process_video_timing_v5.py "..\Final Results" --no-video
```

### Excluding subfolders

Use `--exclude` as many times as needed. Excluded folders are not processed and
do not appear as errors in the master summary.

Exclude a method folder everywhere below the selected root:

```powershell
.\video_env\Scripts\python.exe .\Video_post_process_video_timing_v5.py "..\Final Results" --exclude servop_behavior
```

Exclude several folders:

```powershell
.\video_env\Scripts\python.exe .\Video_post_process_video_timing_v5.py "..\Final Results" --exclude servop_behavior --exclude servoP_confirmation
```

Exclude a specific relative path or wildcard:

```powershell
.\video_env\Scripts\python.exe .\Video_post_process_video_timing_v5.py "..\Final Results" --exclude "ruckig/*/case_009"
```

## Run

From `video_post_processing/`:

```bash
./video_env/bin/python Video_post_process_video_timing_v5.py "../Final Results"
```

Fast validation without rendering tracking videos:

```bash
./video_env/bin/python Video_post_process_video_timing_v5.py "../Final Results" --no-video
```

## Outputs

Each trial gets a `liquid_analysis/` folder containing the per-frame CSV, summary, angle plot, FFT outputs, status JSON, and optionally the annotated cropped video.

Dataset-level outputs are written to the selected dataset root:

- `liquid_analysis_summary.csv`
- `liquid_analysis_calibration.csv`

## Tests

```bash
./video_env/bin/python test_motion_detector.py
```

The endpoint detector was regression-tested for a slow full traversal, a false short tracker jump, and reverse-direction motion. The complete pipeline was also smoke-tested locally against three representative experiment videos and a Final-Results-style trial hierarchy.
