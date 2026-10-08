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

class RawFeedbackLogger:
    """Capture every feedback packet and a useful decoded CSV alongside it."""

    def __init__(self, robot_ip: str, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.socket: socket.socket | None = None
        self.stop_event = threading.Event()
        self.first_packet = threading.Event()
        self.rows: queue.Queue[dict] = queue.Queue(maxsize=20000)
        self.receiver: threading.Thread | None = None
        self.writer: threading.Thread | None = None
        self.sample = 0
        self.received_packets = 0
        self.invalid_packets = 0
        self.dropped_rows = 0
        self.error_samples = 0
        self.collision_samples = 0
        self.robot_ip = robot_ip
        self.t0 = time.perf_counter()
        self.commanded_point: list[float] = [float("nan")] * 6
        self.previous_rover_timestamp_ms: int | None = None
        self.previous_host_time_s: float | None = None

    def set_commanded_point(self, target: list[float] | tuple[float, ...]) -> None:
        values = [float(value) for value in list(target)[:6]]
        if len(values) < 6:
            values.extend([float("nan")] * (6 - len(values)))
        self.commanded_point = values[:6]

    def start(self) -> None:
        self.socket = socket.create_connection((self.robot_ip, FEEDBACK_PORT), timeout=3.0)
        self.socket.settimeout(0.5)
        self.receiver = threading.Thread(target=self._receive_loop, name="feedback-reader", daemon=True)
        self.writer = threading.Thread(target=self._write_loop, name="feedback-writer", daemon=True)
        self.writer.start()
        self.receiver.start()

    def _receive_loop(self) -> None:
        try:
            with (self.run_dir / "feedback_raw.bin").open("wb", buffering=1024 * 1024) as raw:
                while not self.stop_event.is_set():
                    packet = self._receive_exact(PACKET_SIZE)
                    if packet is None:
                        break
                    raw.write(packet)
                    if struct.unpack_from("<H", packet, 0)[0] != PACKET_SIZE or struct.unpack_from("<Q", packet, 48)[0] != MAGIC:
                        self.invalid_packets += 1
                        continue
                    self.received_packets += 1
                    self.first_packet.set()
                    row = self._decode(packet)
                    self.error_samples += int(bool(row["error_status"]))
                    self.collision_samples += int(bool(row["collision_state"]))
                    row["sample"] = self.received_packets
                    try:
                        self.rows.put_nowait(row)
                    except queue.Full:
                        self.dropped_rows += 1
        except Exception as exc:
            if not self.stop_event.is_set():
                self.write_event("FEEDBACK_RECEIVER_ERROR", repr(exc))
        finally:
            self.stop_event.set()

    def _receive_exact(self, size: int) -> bytes | None:
        chunks = []
        total = 0
        while total < size and not self.stop_event.is_set():
            try:
                data = self.socket.recv(size - total)  # type: ignore[union-attr]
            except socket.timeout:
                continue
            if not data:
                raise ConnectionError("Robot closed feedback connection")
            chunks.append(data)
            total += len(data)
        return b"".join(chunks) if total == size else None

    def _decode(self, packet: bytes) -> dict:
        if self.t0 is None:
            raise RuntimeError("Logger has not been started")

        host_time_s = time.perf_counter() - self.t0
        rover_timestamp_ms = struct.unpack_from("<Q", packet, 32)[0]

        rover_step_ms = None
        host_step_ms = None
        interval_difference_ms = None
        interval_differs = None
        if self.previous_rover_timestamp_ms is not None and self.previous_host_time_s is not None:
            rover_step_ms = rover_timestamp_ms - self.previous_rover_timestamp_ms
            host_step_ms = (host_time_s - self.previous_host_time_s) * 1000.0
            interval_difference_ms = host_step_ms - rover_step_ms
            interval_differs = abs(interval_difference_ms) > TIMESTAMP_DIFFERENCE_TOLERANCE_MS

        self.previous_rover_timestamp_ms = rover_timestamp_ms
        self.previous_host_time_s = host_time_s

        row: dict[str, object] = {
            "sample": None,
            "host_time_s": host_time_s,
            "host_utc": utc_now(),
            "timestamp_ms": rover_timestamp_ms,
            "timestamp_step_ms": rover_step_ms,
            "host_step_ms": host_step_ms,
            "interval_difference_ms": interval_difference_ms,
            "interval_differs": interval_differs,
        }

        scalar_fields = {
            "RobotMode": (24, "<Q"),
            "SpeedScaling": (64, "<d"),
            "VRobot": (88, "<d"),
            "IRobot": (96, "<d"),
            "running_status": (1028, "<B"),
            "error_status": (1029, "<B"),
            "collision_state": (1038, "<B"),
            "CurrentCommandId": (1112, "<Q"),
        }
        for name, (offset, fmt) in scalar_fields.items():
            row[name] = struct.unpack_from(fmt, packet, offset)[0]

        vector_fields = {
            "QTarget": 192,
            "QDTarget": 240,
            "QDDTarget": 288,
            "ITarget": 336,
            "MTarget": 384,
            "QActual": 432,
            "QDActual": 480,
            "IActual": 528,
            "VActual": 960,
            "MActual": 1120,
            "MotorTemperatures": 864,
            "ToolVectorActual": 624,
            "TCPSpeedActual": 672,
            "TCPForce": 720,
            "ToolVectorTarget": 768,
            "TCPSpeedTarget": 816,
        }
        for prefix, offset in vector_fields.items():
            values = struct.unpack_from("<6d", packet, offset)
            for index, value in enumerate(values, 1):
                row[f"{prefix}[{index}]"] = value

        for prefix, offset in {"TargetQuaternion": 1352, "ActualQuaternion": 1384}.items():
            values = struct.unpack_from("<4d", packet, offset)
            for index, value in enumerate(values, 1):
                row[f"{prefix}[{index}]"] = value

        for index, value in enumerate(self.commanded_point[:6], 1):
            row[f"commanded_point[{index}]"] = value

        return row

    def _write_loop(self) -> None:
        path = self.run_dir / "feedback.csv"
        first_row = True
        fieldnames = []
        with path.open("w", newline="", encoding="utf-8", buffering=1024 * 1024) as handle:
            writer = None
            while not self.stop_event.is_set() or not self.rows.empty():
                try:
                    row = self.rows.get(timeout=0.1)
                except queue.Empty:
                    continue
                if first_row:
                    fieldnames = list(row)
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    first_row = False
                writer.writerow(row)
                self.rows.task_done()

    def write_event(self, event: str, details: str = "") -> None:
        path = self.run_dir / "events.csv"
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["host_time_s", "host_utc", "event", "details"])
            if not exists:
                writer.writeheader()
            writer.writerow({"host_time_s": time.perf_counter() - self.t0, "host_utc": utc_now(), "event": event, "details": details})

    def stop(self) -> dict:
        self.stop_event.set()
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        if self.receiver:
            self.receiver.join(timeout=3)
        if self.writer:
            self.writer.join(timeout=5)
        stats = {
            "received_packets": self.received_packets,
            "invalid_packets": self.invalid_packets,
            "dropped_rows": self.dropped_rows,
            "error_samples": self.error_samples,
            "collision_samples": self.collision_samples,
        }
        (self.run_dir / "logger_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        return stats
