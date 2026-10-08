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

class RigolScopeLogger:
    """Acquire a scope burst before motion, stop it after motion, and aggregate 8 ms means after download."""

    def __init__(
        self,
        resource_name: str,
        run_dir: str | Path,
        sample_period_s: float = 1.0 / 125.0,
        timeout_ms: int = 1000,
        current_channel: str = "CHAN1",
        voltage_channel: str = "CHAN2",
        power_channel: str = "MATH",
        window_period_s: float = 8e-3,
        download_points: int = 5000,
        max_output_points: int = 2000,
    ):
        self.resource_name = resource_name.strip()
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.sample_period_s = sample_period_s
        self.timeout_ms = timeout_ms
        self.current_channel = current_channel
        self.voltage_channel = voltage_channel
        self.power_channel = power_channel
        self.window_period_s = float(window_period_s)
        self.download_points = max(1, int(download_points))
        self.max_output_points = max(1, int(max_output_points))
        self.scope = None
        self.t0: float | None = None
        self.sample = 0
        self.error: str | None = None
        self._started = False

    def start(self, reference_t0: float | None = None) -> None:
        if pyvisa is None:
            raise RuntimeError("pyvisa is required for Rigol oscilloscope logging. Install it with 'pip install pyvisa'.")
        if np is None:
            raise RuntimeError("numpy is required for waveform-based Rigol logging. Install it with 'pip install numpy'.")

        if self.scope is not None:
            try:
                self.scope.close()
            except Exception:
                pass
            self.scope = None

        self.t0 = time.perf_counter() if reference_t0 is None else float(reference_t0)

        visa_library = None
        if Path(r"C:\Windows\System32\visa64.dll").exists():
            visa_library = r"C:\Windows\System32\visa64.dll"

        try:
            rm = pyvisa.ResourceManager(visa_library) if visa_library else pyvisa.ResourceManager()
        except ValueError:
            rm = pyvisa.ResourceManager("@py")

        self.scope = rm.open_resource(self.resource_name)
        self.scope.timeout = self.timeout_ms

        try:
            scope_idn = self.scope.query("*IDN?").strip()
            self.scope.write("*CLS")
            self.scope.write(":STOP")
            self.scope.write(":WAV:MODE NORM")
            self.scope.write(":WAV:FORM BYTE")
            self.scope.write(":ACQ:TYPE NORMAL")

        except Exception as exc:
            raise RuntimeError(
                f"Unable to talk to Rigol scope {self.resource_name}. "
                "Check the USB connection, VISA backend, and scope state."
            ) from exc

        (self.run_dir / "scope_metadata.txt").write_text(
            f"resource={self.resource_name}\nidentifier={scope_idn}\n",
            encoding="utf-8",
        )

        self.scope.write(":RUN")
        print(f"Rigol scope {self.resource_name} started, capturing waveforms...")
        self._started = True
        time.sleep(0.2)

        # Keep the acquisition buffer bounded so the full waveform transfer is
        # fast enough for normal experiments while the output is downsampled
        # later to a manageable number of points.
        self.scope.write(f":ACQ:MDEP {self.download_points}")
        self.scope.query("*OPC?")

        print(
            "Memory depth:",
            self.scope.query(":ACQ:MDEP?").strip()
        )

        print(
            "Sample rate:",
            self.scope.query(":ACQ:SRAT?").strip()
        )

        print(
            "Timebase:",
            self.scope.query(":TIM:SCAL?").strip()
        )
        # while(1):
        #         pass

    def _download_waveform(self, channel):
        if self.scope is None:
            raise RuntimeError("Rigol scope is not connected")

        self.scope.write(f":WAV:SOUR {channel}")
        self.scope.write(":WAV:MODE RAW")
        self.scope.write(":WAV:FORM BYTE")

        preamble = self.scope.query(":WAV:PRE?").strip().split(",")

        points = int(float(preamble[2]))
        xinc = float(preamble[4])
        xorig = float(preamble[5])
        xref = float(preamble[6])
        yinc = float(preamble[7])
        yorig = float(preamble[8])
        yref = float(preamble[9])

        chunk_size = 250_000
        chunks = []

        # A 1 second timeout is rather aggressive for deep-memory downloads.
        old_timeout = self.scope.timeout
        self.scope.timeout = 10_000

        try:
            for start in range(1, points + 1, chunk_size):
                stop = min(start + chunk_size - 1, points)

                self.scope.write(f":WAV:STAR {start}")
                self.scope.write(f":WAV:STOP {stop}")

                data = self.scope.query_binary_values(
                    ":WAV:DATA?",
                    datatype="B",
                    is_big_endian=False,
                    container=np.array,
                )

                chunks.append(data)

        finally:
            self.scope.timeout = old_timeout

        raw = (
            np.concatenate(chunks)
            if chunks
            else np.array([], dtype=np.uint8)
        )

        values = (
            raw.astype(float) - yref - yorig
        ) * yinc

        time_s = (
            np.arange(raw.size, dtype=float) - xref
        ) * xinc + xorig
        time_s = self._center_time_axis(time_s)

        return time_s, values

    @staticmethod
    def _center_time_axis(time_s: Any) -> np.ndarray:
        """Set the midpoint of the downloaded acquisition to zero seconds."""
        time_s = np.asarray(time_s, dtype=float)
        if time_s.size == 0:
            return time_s
        midpoint = float((time_s[0] + time_s[-1]) / 2.0)
        return time_s - midpoint

    def _downsample(
        self,
        time_s: Any,
        values: Any,
        max_points: int | None = None,
    ) -> tuple[Any, Any]:
        """Average consecutive samples to a bounded output size."""
        time_s = np.asarray(time_s, dtype=float)
        values = np.asarray(values, dtype=float)
        limit = self.max_output_points if max_points is None else max(1, int(max_points))

        if time_s.size != values.size or time_s.size <= limit:
            return time_s, values

        bin_edges = np.linspace(0, time_s.size, limit + 1, dtype=int)
        downsampled_time = np.empty(limit, dtype=float)
        downsampled_values = np.empty(limit, dtype=float)

        for index in range(limit):
            start = int(bin_edges[index])
            stop = int(bin_edges[index + 1])
            block = values[start:stop]
            if block.size == 0:
                block = values[start:start + 1]
            downsampled_time[index] = float(np.mean(time_s[start:stop]))
            downsampled_values[index] = float(np.mean(block))

        downsampled_time[0] = float(time_s[0])
        downsampled_time[-1] = float(time_s[-1])
        downsampled_values[0] = float(values[0])
        downsampled_values[-1] = float(values[-1])
        return downsampled_time, downsampled_values

    def _save_raw_waveform_csv(self, channel: str, time_s: Any, values: Any) -> None:
        if values.size == 0:
            return
        filename = f"rigol_{channel.lower()}_raw.csv"
        data = np.column_stack((time_s.astype(float), values.astype(float)))
        with (self.run_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            np.savetxt(handle, data, delimiter=",", header="time_s,value", comments="", fmt="%.18g")

    def _save_combined_raw_csv(
        self,
        current_time: Any,
        current: Any,
        voltage_time: Any,
        voltage: Any,
        power_time: Any,
        power: Any,
    ) -> None:
        max_len = max(current.size, voltage.size, power.size)
        rows = []
        for idx in range(max_len):
            rows.append(
                [
                    idx + 1,
                    float(current_time[idx]) if idx < current_time.size else float(idx),
                    float(current[idx]) if idx < current.size else float("nan"),
                    float(voltage[idx]) if idx < voltage.size else float("nan"),
                    float(power[idx]) if idx < power.size else float("nan"),
                ]
            )

        with (self.run_dir / "rigol_scope.csv").open("w", newline="", encoding="utf-8") as handle:
            np.savetxt(
                handle,
                np.asarray(rows, dtype=float),
                delimiter=",",
                header="sample,time_s,current_A,voltage_V,power_W",
                comments="",
                fmt="%.18g",
            )

    def _wait_until_stopped(self, timeout_s: float = 3.0) -> None:
        if self.scope is None:
            raise RuntimeError("Rigol scope is not connected")

        deadline = time.perf_counter() + timeout_s

        while time.perf_counter() < deadline:
            state = self.scope.query(":TRIG:STAT?").strip().upper()
            print(f"Rigol state: {state}")

            if state == "STOP":
                return

            time.sleep(0.05)

        raise TimeoutError("Rigol did not enter STOP state")


    def stop(self) -> dict:
        if self.scope is None:
            return {
                "resource": self.resource_name,
                "samples": self.sample,
                "error": "No Rigol scope opened",
            }

        try:
            print("Stopping Rigol...")

            self.scope.write(":STOP")
            self.scope.query("*OPC?")

            self._wait_until_stopped()

            print("Rigol confirmed STOPPED")

            # RAW memory download only from real acquisition channels
            current_time, current = self._download_waveform(
                self.current_channel
            )

            voltage_time, voltage = self._download_waveform(
                self.voltage_channel
            )

            # Do NOT request MATH in RAW mode.
            # Calculate power locally.
            n = min(len(current), len(voltage))

            current_time = current_time[:n]
            current = current[:n]

            voltage_time = voltage_time[:n]
            voltage = voltage[:n]

            current_time, current = self._downsample(current_time, current)
            voltage_time, voltage = self._downsample(voltage_time, voltage)
            power_time = current_time
            power = current * voltage

            self._save_raw_waveform_csv(
                self.current_channel,
                current_time,
                current,
            )

            self._save_raw_waveform_csv(
                self.voltage_channel,
                voltage_time,
                voltage,
            )

            self._save_raw_waveform_csv(
                "power",
                power_time,
                power,
            )

            self._save_combined_raw_csv(
                current_time,
                current,
                voltage_time,
                voltage,
                power_time,
                power,
            )

            self.sample = n

            return {
                "resource": self.resource_name,
                "samples": self.sample,
                "error": None,
            }

        except Exception as exc:
            self.error = repr(exc)
            print(f"Rigol error: {self.error}")

            return {
                "resource": self.resource_name,
                "samples": self.sample,
                "error": self.error,
            }

        finally:
            try:
                if self.scope is not None:
                    self.scope.close()
            except Exception:
                pass

            self.scope = None
            self._started = False
