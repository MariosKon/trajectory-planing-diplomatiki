#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/video_env"
REQ_FILE="${SCRIPT_DIR}/requirements-video.txt"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed." >&2
  exit 1
fi

if ! python3 -c 'import venv' >/dev/null 2>&1; then
  echo "ERROR: Python venv support is missing." >&2
  echo "Ubuntu/Debian: sudo apt update && sudo apt install python3-venv" >&2
  exit 1
fi

if [ ! -f "$REQ_FILE" ]; then
  echo "ERROR: $REQ_FILE not found." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating $VENV_DIR"
  python3 -m venv "$VENV_DIR"
else
  echo "Reusing $VENV_DIR"
fi

PY="$VENV_DIR/bin/python"
"$PY" -m pip install --upgrade pip setuptools wheel
"$PY" -m pip install -r "$REQ_FILE"

"$PY" - <<'PY'
import sys
import numpy
import cv2
import pandas
import matplotlib
print("Python:", sys.version.split()[0])
print("NumPy:", numpy.__version__)
print("OpenCV:", cv2.__version__)
print("pandas:", pandas.__version__)
print("matplotlib:", matplotlib.__version__)
print("Video analysis environment OK")
PY

echo
echo "Run the analyzer with:"
echo "  \"$PY\" \"$SCRIPT_DIR/Video_post_process_video_timing_v5.py\" <FINAL_RESULTS_ROOT>"
