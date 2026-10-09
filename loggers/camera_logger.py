"""RTSP capture using FFmpeg stream copy (no OpenCV decode/re-encode).

Each trial has its own Matroska recording, FFmpeg log, progress report,
and JSON metadata. The existing LoggingManager start()/stop() API remains.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .h264_mkv_repair import repair_recording


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RTSPVideoRecorder:
    """Record an RTSP video stream as received, without synthetic frames."""

    def __init__(
        self,
        rtsp_url: str,
        run_dir: str | Path,
        fps: float = 30.0,
        ffmpeg_bin: str = "ffmpeg",
        startup_timeout_s: float = 20.0,
        stop_timeout_s: float = 8.0,
    ):
        # The fps argument is retained for interface compatibility; source
        # timestamps, NOT a hard-coded output frame rate, govern the video.
        self.rtsp_url = rtsp_url
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.run_dir / "camera.mkv"
        self.log_path = self.run_dir / "ffmpeg_camera.log"
        self.progress_path = self.run_dir / "ffmpeg_camera_progress.txt"
        self.metadata_path = self.run_dir / "camera_metadata.json"
        self.ffmpeg_bin = ffmpeg_bin
        self.startup_timeout_s = startup_timeout_s
        self.stop_timeout_s = stop_timeout_s
        self.process = None
        self._log_handle = None
        self.recording_start_s = None
        self.recording_end_s = None
        self.start_utc = None
        self.end_utc = None
        self.startup_elapsed_s = None
        self.error = None
        self._stopped = False

    def _command(self, executable: str) -> list[str]:
        return [
            executable,
            "-hide_banner",
            "-loglevel", "info",
            "-nostats",
            "-stats_period", "1",
            "-progress", str(self.progress_path),
            "-y",
            "-rtsp_transport", "tcp",
            # Generate missing packet PTS where DTS is available. Some
            # cameras supply neither usable PTS nor DTS: assign timestamps
            # on reception in that case (host arrival time, not capture time).
            "-fflags", "+genpts",
            "-use_wallclock_as_timestamps", "1",
            "-i", self.rtsp_url,
            "-map", "0:v:0",
            "-an",
            "-c:v", "copy",
            "-flush_packets", "1",
            "-avoid_negative_ts", "make_zero",
            "-f", "matroska",
            str(self.output_path),
        ]

    def start(self) -> None:
        if self.process is not None:
            raise RuntimeError("Camera recorder is already started")
        executable = shutil.which(self.ffmpeg_bin)
        if executable is None:
            raise RuntimeError(
                "FFmpeg executable not found. Install FFmpeg and add ffmpeg to PATH."
            )
        self._log_handle = self.log_path.open("wb")
        self.start_utc = utc_now()
        self.recording_start_s = time.perf_counter()
        try:
            # Keep stdin available so 'q' can finalize the container at stop.
            # stderr is a file to prevent PIPE deadlocks and preserve diagnostics.
            self.process = subprocess.Popen(
                self._command(executable),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._log_handle,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + self.startup_timeout_s
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"FFmpeg exited during camera startup (code "
                        f"{self.process.returncode}); see {self.log_path}"
                    )
                # Container headers can exceed 1024 bytes before a single
                # usable video frame arrives. Require FFmpeg's frame progress
                # instead of considering an existing file as proof of video.
                if self._progress_frames() > 0:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"No recorded video frame reported by FFmpeg within "
                        f"{self.startup_timeout_s:g}s; see {self.log_path}"
                    )
                time.sleep(0.05)
            self.startup_elapsed_s = time.perf_counter() - self.recording_start_s
        except Exception:
            # A failed startup must not leave an FFmpeg child writing behind
            # while LoggingManager continues robot/Rigol acquisition.
            self._close_process()
            raise

    def _close_process(self) -> tuple[int | None, bool]:
        forced = False
        returncode = None
        process = self.process
        if process is not None:
            if process.poll() is None:
                try:
                    if process.stdin is not None:
                        process.stdin.write(b"q\n")
                        process.stdin.flush()
                except (OSError, ValueError, BrokenPipeError):
                    pass
                try:
                    returncode = process.wait(timeout=self.stop_timeout_s)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.terminate()
                    try:
                        returncode = process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        returncode = process.wait(timeout=2.0)
            else:
                returncode = process.returncode
            if process.stdin is not None:
                process.stdin.close()
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
        self.process = None
        return returncode, forced

    def _progress(self) -> dict[str, str]:
        report = {}
        if self.progress_path.exists():
            for line in self.progress_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    report[key] = value
        return report

    def _progress_frames(self) -> int:
        progress = self._progress()
        try:
            return max(0, int(progress.get("frame", "0")))
        except (TypeError, ValueError):
            return 0

    def stop(self) -> dict:
        if self._stopped:
            raise RuntimeError("Camera recorder already stopped")
        self._stopped = True
        errors = []
        returncode = None
        forced = False
        try:
            returncode, forced = self._close_process()
        except Exception as exc:
            errors.append(f"FFmpeg cleanup error: {exc!r}")
        self.recording_end_s = time.perf_counter()
        self.end_utc = utc_now()
        if forced:
            errors.append("FFmpeg did not stop gracefully; process terminated")
        if returncode not in (None, 0):
            errors.append(f"FFmpeg exited with code {returncode}; see {self.log_path}")
        size = self.output_path.stat().st_size if self.output_path.exists() else 0
        if size < 1024:
            errors.append("Camera recording is missing or empty")
        progress = self._progress()
        frame_str = progress.get("frame", "")
        try:
            frames = int(frame_str)
        except ValueError:
            frames = None
        if frames == 0:
            errors.append("FFmpeg reported zero video frames")
        # Check the video contents, not just the muxer's reported frame count.
        # A camera can insert invalid zero-length H.264 NAL units even when
        # FFmpeg reports hundreds of successfully copied packets.
        validation = {"validation": "not_checked"}
        if size >= 1024 and frames != 0:
            try:
                validation = repair_recording(self.output_path, self.ffmpeg_bin)
                size = self.output_path.stat().st_size
            except Exception as exc:
                errors.append(f"Camera validation/repair failed: {exc}")
                validation = {"validation": "failed", "error": str(exc)}
        self.error = "; ".join(errors) if errors else None
        result = {
            "path": str(self.output_path),
            "format": "matroska",
            "codec": "copy",
            "rtsp_transport": "tcp",
            "timestamp_mode": "host_wallclock_on_packet_arrival",
            "startup_confirmed_by": "ffmpeg_frame_progress",
            "ffmpeg_log": str(self.log_path),
            "ffmpeg_progress": str(self.progress_path),
            "frame_count": frames,
            "video_validation": validation,
            "received_frames": None,
            "encoded_fps": None,
            "file_size_bytes": size,
            "host_start_perf_s": self.recording_start_s,
            "host_end_perf_s": self.recording_end_s,
            "host_start_utc": self.start_utc,
            "host_end_utc": self.end_utc,
            "startup_elapsed_s": self.startup_elapsed_s,
            "recorded_wall_duration_s": (
                self.recording_end_s - self.recording_start_s
                if self.recording_start_s is not None else None
            ),
            "note": (
                "Packet arrival-time timestamps are not camera capture timestamps "
                "and are not synchronized to robot motion. The video is "
                "wallclock timestamps may be unsuitable; check the FFmpeg log "
                "and inspect actual playback."
            ),
            "error": self.error,
        }
        self.metadata_path.write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result
