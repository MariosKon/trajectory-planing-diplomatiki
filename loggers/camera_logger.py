from __future__ import annotations
import csv
import json
import queue
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pyvisa
except ImportError:
    pyvisa = None

try:
    import cv2
except ImportError:
    cv2 = None

PACKET_SIZE = 1440
FEEDBACK_PORT = 30004
MAGIC = 0x0123456789ABCDEF
TIMESTAMP_DIFFERENCE_TOLERANCE_MS = 1.0

def utc_now():
    return datetime.now(timezone.utc).isoformat()

class RTSPVideoRecorder:
    """Capture an RTSP stream into a local MP4 file while the robot run is active."""

    def __init__(self, rtsp_url: str, run_dir: str | Path, fps: float = 30.0):
        if cv2 is None:
            raise RuntimeError("OpenCV is required for RTSP video capture. Install opencv-python-headless.")
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.rtsp_url = rtsp_url
        self.fps = fps
        self.output_path = self.run_dir / "camera.mp4"
        self.capture: Any | None = None
        self.writer: Any | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.frame_count = 0
        self.error: str | None = None

    def start(self) -> None:
        self.capture = cv2.VideoCapture(self.rtsp_url)
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open RTSP stream: {self.rtsp_url}")

        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            raise RuntimeError(f"RTSP stream did not provide a valid frame size: {self.rtsp_url}")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(str(self.output_path), fourcc, self.fps, (width, height))
        if not self.writer.isOpened():
            raise RuntimeError(f"Unable to create video writer for {self.output_path}")

        self.thread = threading.Thread(target=self._record_loop, name="rtsp-recorder", daemon=True)
        self.thread.start()

    def _record_loop(self) -> None:
        try:
            while not self.stop_event.is_set():
                ok, frame = self.capture.read() if self.capture is not None else (False, None)
                if not ok or frame is None:
                    self.error = "RTSP stream ended or failed while recording"
                    break
                if self.writer is not None:
                    self.writer.write(frame)
                self.frame_count += 1
        finally:
            if self.writer is not None:
                self.writer.release()
            if self.capture is not None:
                self.capture.release()

    def stop(self) -> dict:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)
        return {
            "path": str(self.output_path),
            "frame_count": self.frame_count,
            "error": self.error,
        }
