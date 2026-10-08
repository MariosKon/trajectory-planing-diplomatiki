"""Rigol waveform acquisition with calibrated, time-aligned electrical data.

Instrument times are oscilloscope/trigger-relative, NOT automatically host time.
Original channel samples are retained, while rigol_scope.csv is a preview.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pyvisa
except ImportError:
    pyvisa = None


class RigolScopeLogger:
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
        download_points: int = 60000,
        max_output_points: int = 2000,
        horizontal_scale_s_per_div: float | None = 0.5,
        current_A_per_unit: float | None = None,
        voltage_V_per_unit: float = 1.0,
        wait_full_screen: bool = True,
    ):
        if download_points < 1 or max_output_points < 2:
            raise ValueError("Acquisition and output point counts must be positive")
        if horizontal_scale_s_per_div is not None and horizontal_scale_s_per_div <= 0:
            raise ValueError("Horizontal scale must be positive")
        if current_A_per_unit is not None and current_A_per_unit <= 0:
            raise ValueError("Current calibration factor must be positive")
        if voltage_V_per_unit <= 0:
            raise ValueError("Voltage calibration factor must be positive")
        self.resource_name = resource_name.strip()
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.sample_period_s = sample_period_s  # historical setting; instrument determines real XINC
        self.timeout_ms = timeout_ms
        self.current_channel = current_channel
        self.voltage_channel = voltage_channel
        self.power_channel = power_channel
        self.window_period_s = window_period_s
        self.download_points = download_points
        self.max_output_points = max_output_points
        self.horizontal_scale_s_per_div = horizontal_scale_s_per_div
        self.current_A_per_unit = current_A_per_unit
        self.voltage_V_per_unit = voltage_V_per_unit
        self.wait_full_screen = bool(wait_full_screen)
        self.scope = None
        self.resource_manager = None
        self.t0 = None
        self.sample = 0
        self.error = None
        self._started = False
        self.metadata = {"warnings": [], "channels": {}}

    def _query_optional(self, command: str) -> str | None:
        try:
            return self.scope.query(command).strip()
        except Exception as exc:
            self.metadata["warnings"].append(f"{command}: {exc!r}")
            return None

    def _save_metadata(self):
        (self.run_dir / "rigol_metadata.json").write_text(
            json.dumps(self.metadata, indent=2, default=str), encoding="utf-8"
        )

    def start(self, reference_t0: float | None = None) -> None:
        if pyvisa is None or np is None:
            raise RuntimeError("Rigol logging requires pyvisa and numpy")
        self.t0 = time.perf_counter() if reference_t0 is None else reference_t0
        self.metadata["host_setup_begin_perf_s"] = time.perf_counter()
        self.metadata["scope_time_reference"] = "oscilloscope trigger-relative; not aligned with host event timestamps"
        self.metadata["requested_horizontal_scale_s_per_div"] = self.horizontal_scale_s_per_div
        self.metadata["requested_memory_depth"] = self.download_points
        self.metadata["current_A_per_unit"] = self.current_A_per_unit
        self.metadata["voltage_V_per_unit"] = self.voltage_V_per_unit
        try:
            visa_library = r"C:\Windows\System32\visa64.dll"
            if Path(visa_library).exists():
                self.resource_manager = pyvisa.ResourceManager(visa_library)
            else:
                self.resource_manager = pyvisa.ResourceManager()
            self.scope = self.resource_manager.open_resource(self.resource_name)
            self.scope.timeout = self.timeout_ms
            self.metadata["instrument_id"] = self.scope.query("*IDN?").strip()
            self.scope.write("*CLS")
            self.metadata["previous_timebase_mode"] = self._query_optional(":TIM:MODE?")
            self.scope.write(":STOP")
            # Time/div alone DOES NOT exit roll mode. Explicitly select Y-T mode.
            self.scope.write(":TIM:MODE MAIN")
            actual_mode = (self._query_optional(":TIM:MODE?") or "").upper()
            self.metadata["timebase_mode"] = actual_mode
            if actual_mode != "MAIN":
                raise RuntimeError(f"Rigol must be in MAIN mode, got {actual_mode!r}; ROLL waveforms cannot be compared by normal trigger-time axes")
            self.scope.write(":ACQ:TYPE NORM")
            self.scope.write(":WAV:FORM BYTE")
            if self.horizontal_scale_s_per_div is not None:
                self.scope.write(f":TIM:SCAL {self.horizontal_scale_s_per_div}")
            # Configure depth BEFORE starting capture, not during it.
            self.scope.write(f":ACQ:MDEP {self.download_points}")
            self.scope.write(":TRIG:SWE AUTO")
            self.scope.query("*OPC?")
            self.metadata["horizontal_scale_s_per_div"] = self._query_optional(":TIM:SCAL?")
            self.metadata["memory_depth"] = self._query_optional(":ACQ:MDEP?")
            if self.metadata["memory_depth"] != str(self.download_points):
                self.metadata["warnings"].append(
                    f"Scope memory-depth readback {self.metadata['memory_depth']!r} differs from requested {self.download_points}"
                )
            self.metadata["sample_rate"] = self._query_optional(":ACQ:SRAT?")
            for channel in (self.current_channel, self.voltage_channel):
                self.metadata["channels"][channel] = {
                    "unit": self._query_optional(f":{channel}:UNIT?"),
                    "scale": self._query_optional(f":{channel}:SCAL?"),
                    "offset": self._query_optional(f":{channel}:OFFS?"),
                }
            self.scope.write(":RUN")
            # Timestamp at the RUN command, not at USB/VISA initialization.
            self.metadata["host_start_perf_s"] = time.perf_counter()
            self._started = True
            self._save_metadata()
        except Exception:
            self.close()
            raise

    def _capture_screen_image(self):
        """Save what the oscilloscope shows while stopped."""
        if self.scope is None:
            return
        old_timeout = self.scope.timeout
        try:
            self.scope.timeout = max(old_timeout, 10000)
            image = self.scope.query_binary_values(
                ":DISP:DATA? ON,OFF,PNG", datatype="B", container=bytes
            )
            if not bytes(image).startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Invalid PNG response from Rigol")
            (self.run_dir / "rigol_screen.png").write_bytes(bytes(image))
            self.metadata["screen_image"] = "rigol_screen.png"
        except Exception as exc:
            self.metadata["warnings"].append(f"Screen capture failed: {exc!r}")
        finally:
            self.scope.timeout = old_timeout

    def _download_display_waveform(self, channel: str):
        """Capture the 1200-point NORM display trace separately from RAW."""
        if self.scope is None:
            return
        try:
            self.scope.write(f":WAV:SOUR {channel}")
            self.scope.write(":WAV:MODE NORM")
            self.scope.write(":WAV:FORM BYTE")
            preamble = self.scope.query(":WAV:PRE?").strip().split(",")
            if len(preamble) < 10:
                raise ValueError(f"Malformed display preamble: {preamble}")
            count = min(int(float(preamble[2])), 1200)
            if count < 2:
                raise ValueError("Display preamble has fewer than two points")
            self.scope.write(":WAV:STAR 1")
            self.scope.write(f":WAV:STOP {count}")
            samples = np.asarray(self.scope.query_binary_values(
                ":WAV:DATA?", datatype="B", container=np.array
            ), dtype=float)
            if samples.size != count:
                raise ValueError(
                    f"NORM expected {count} points but received {samples.size}"
                )
            xinc, xorig, xref = map(float, preamble[4:7])
            yinc, yorig, yref = map(float, preamble[7:10])
            time_axis = (np.arange(count, dtype=float) - xref) * xinc + xorig
            displayed = (samples - yorig - yref) * yinc
            self.metadata["channels"][channel]["display_preamble"] = preamble
            with (self.run_dir / f"rigol_{channel.lower()}_display.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["scope_time_s", "displayed_value"])
                writer.writerows(zip(time_axis, displayed))
            return time_axis, displayed
        except Exception as exc:
            self.metadata["warnings"].append(
                f"NORM display trace failed for {channel}: {exc!r}"
            )

    def _download_waveform(self, channel: str):
        if self.scope is None:
            raise RuntimeError("Rigol not connected")
        self.scope.write(f":WAV:SOUR {channel}")
        self.scope.write(":WAV:MODE RAW")
        self.scope.write(":WAV:FORM BYTE")
        preamble_text = self.scope.query(":WAV:PRE?").strip()
        p = preamble_text.split(",")
        if len(p) < 10:
            raise ValueError(f"Invalid waveform preamble for {channel}: {preamble_text}")
        points = int(float(p[2]))
        xinc, xorig, xref = (float(v) for v in p[4:7])
        yinc, yorig, yref = (float(v) for v in p[7:10])
        if points < 2 or xinc <= 0 or yinc == 0:
            raise ValueError(f"Invalid waveform dimensions for {channel}: {preamble_text}")
        chunks = []
        original_timeout = self.scope.timeout
        self.scope.timeout = max(original_timeout, 10000)
        try:
            for first in range(1, points + 1, 250000):
                last = min(first + 249999, points)
                self.scope.write(f":WAV:STAR {first}")
                self.scope.write(f":WAV:STOP {last}")
                chunk = self.scope.query_binary_values(
                    ":WAV:DATA?", datatype="B",
                    is_big_endian=False, container=np.array,
                )
                chunks.append(np.asarray(chunk, dtype=np.uint8))
        finally:
            self.scope.timeout = original_timeout
        raw = np.concatenate(chunks)
        if raw.size != points:
            raise ValueError(
                f"{channel}: preamble requested {points} samples, downloaded {raw.size}"
            )
        # Rigol waveform preamble conversion: keep floating-point arithmetic.
        values = (raw.astype(float) - yorig - yref) * yinc
        times = (np.arange(points, dtype=float) - xref) * xinc + xorig
        self.metadata["channels"][channel]["preamble"] = p
        self.metadata["channels"][channel]["raw_points"] = points
        self.metadata["channels"][channel]["time_start_s"] = float(times[0])
        self.metadata["channels"][channel]["time_end_s"] = float(times[-1])
        self.metadata["channels"][channel]["sample_interval_s"] = xinc
        self.metadata["channels"][channel]["raw_byte_min"] = int(raw.min())
        self.metadata["channels"][channel]["raw_byte_max"] = int(raw.max())
        if raw.min() == 0 or raw.max() == 255:
            self.metadata["warnings"].append(
                f"{channel}: BYTE waveform reaches an ADC endpoint; check clipping"
            )
        return times, values

    def _save_channel(self, channel: str, times, values):
        name = f"rigol_{channel.lower()}_raw.csv"
        with (self.run_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["scope_time_s", "displayed_value"])
            writer.writerows(zip(times, values))

    @staticmethod
    def _current_factor(unit: str | None, manual_factor: float | None):
        if manual_factor is not None:
            return manual_factor
        normalized = (unit or "").strip().upper().replace('"', "")
        return 1.0 if normalized in {"A", "AMP", "AMPS", "AMPERE"} else None

    def _downsample(self, times, current, voltage, power):
        n = len(times)
        if n <= self.max_output_points:
            return times, current, voltage, power
        edges = np.linspace(0, n, self.max_output_points + 1, dtype=int)
        def reduced(a):
            return np.array([a[edges[i]:edges[i + 1]].mean()
                             for i in range(self.max_output_points)])
        return reduced(times), reduced(current), reduced(voltage), reduced(power)

    def _confirm_stopped(self, timeout_s: float = 5.0):
        """Do not download a moving waveform without verifying STOP."""
        deadline = time.perf_counter() + timeout_s
        last_status = None
        while time.perf_counter() < deadline:
            last_status = (self.scope.query(":TRIG:STAT?") or "").strip().upper()
            if last_status == "STOP":
                self.metadata["trigger_state_after_stop"] = last_status
                return
            time.sleep(0.1)
        self.metadata["trigger_state_after_stop"] = last_status
        raise TimeoutError(
            f"Rigol did not confirm STOP (last trigger status {last_status!r})"
        )

    def stop(self) -> dict:
        if self.scope is None:
            return {"resource": self.resource_name, "samples": 0,
                    "error": "Rigol acquisition was not started"}
        try:
            run_started = self.metadata.get("host_start_perf_s")
            if self.wait_full_screen and run_started is not None and self.horizontal_scale_s_per_div is not None:
                target_span_s = 12.0 * self.horizontal_scale_s_per_div
                remaining_s = target_span_s - (time.perf_counter() - run_started)
                if remaining_s > 0:
                    self.metadata["additional_capture_wait_s"] = remaining_s
                    time.sleep(remaining_s)
            self.scope.write(":STOP")
            self.metadata["host_stop_perf_s"] = time.perf_counter()
            self.scope.query("*OPC?")
            self._confirm_stopped()
            mode_after = (self._query_optional(":TIM:MODE?") or "").upper()
            self.metadata["timebase_mode_after_stop"] = mode_after
            if mode_after != "MAIN":
                raise RuntimeError(f"Scope changed to {mode_after!r}; expected MAIN")
            self.metadata["host_acquisition_duration_s"] = (
                self.metadata["host_stop_perf_s"] - self.metadata["host_start_perf_s"]
            )
            self.metadata["sample_rate_after_stop"] = self._query_optional(":ACQ:SRAT?")
            self._capture_screen_image()
            display_traces = {}
            for channel in (self.current_channel, self.voltage_channel):
                display_traces[channel] = self._download_display_waveform(channel)
            current_t, current_raw = self._download_waveform(self.current_channel)
            voltage_t, voltage_raw = self._download_waveform(self.voltage_channel)
            self._save_channel(self.current_channel, current_t, current_raw)
            self._save_channel(self.voltage_channel, voltage_t, voltage_raw)

            # The DS1202Z-E RAW channel BYTE data in actual experiments can
            # disagree with the displayed waveform (including reversed CH1
            # polarity). Preserve RAW/preambles for investigation, but DO NOT
            # derive the published electrical metrics from unverified RAW.
            display_i = display_traces.get(self.current_channel)
            display_v = display_traces.get(self.voltage_channel)
            if display_i is None or display_v is None:
                raise ValueError(
                    "Cannot validate Rigol displayed waveforms; refusing RAW-derived power"
                )
            di_t, di_values = display_i
            dv_t, dv_values = display_v
            lo = max(float(di_t[0]), float(dv_t[0]))
            hi = min(float(di_t[-1]), float(dv_t[-1]))
            mask = (di_t >= lo) & (di_t <= hi)
            if np.count_nonzero(mask) < 2:
                raise ValueError("Rigol display traces have no usable common interval")
            t = di_t[mask]
            displayed_current = di_values[mask]
            displayed_voltage = np.interp(t, dv_t, dv_values)

            self.metadata["raw_display_comparison"] = {}
            for channel, raw_t, raw_values in (
                (self.current_channel, current_t, current_raw),
                (self.voltage_channel, voltage_t, voltage_raw),
            ):
                display_t, display_values = display_traces[channel]
                overlapping = ((display_t >= raw_t[0]) &
                               (display_t <= raw_t[-1]))
                reference = display_values[overlapping]
                observed = np.interp(display_t[overlapping], raw_t, raw_values)
                comparison = {
                    "paired_points": int(reference.size),
                    "correlation": None,
                    "raw_preamble_conversion_verified": False,
                }
                if reference.size >= 10 and np.ptp(reference) > 0.1 and np.ptp(observed) > 0.1:
                    correlation = float(np.corrcoef(reference, observed)[0, 1])
                    comparison["correlation"] = (
                        correlation if np.isfinite(correlation) else None
                    )
                    if np.isfinite(correlation) and correlation < -0.7:
                        self.metadata["warnings"].append(
                            f"{channel}: RAW signal polarity disagrees with scope "
                            "display; RAW-derived electrical metrics are disabled"
                        )
                self.metadata["raw_display_comparison"][channel] = comparison

            unit = self.metadata["channels"][self.current_channel]["unit"]
            current_factor = self._current_factor(unit, self.current_A_per_unit)
            if current_factor is None:
                self.metadata["warnings"].append(
                    "Current channel is not confirmed in amperes; configure "
                    "rigol_current_A_per_unit for an external sensor"
                )
            current = (displayed_current * current_factor
                       if current_factor is not None
                       else np.full_like(displayed_current, np.nan))
            voltage = displayed_voltage * self.voltage_V_per_unit
            power = current * voltage
            self.metadata["power_trace_source"] = "NORM_DISPLAY"
            self.metadata["power_calibrated"] = current_factor is not None
            self.metadata["movement_only_energy_valid"] = False
            self.metadata["display_waveform_duration_s"] = float(t[-1] - t[0])
            acquired_s = self.metadata["host_acquisition_duration_s"]
            waveform_s = self.metadata["display_waveform_duration_s"]
            coverage = waveform_s / acquired_s if acquired_s > 0 else 0.0
            self.metadata["waveform_host_duration_ratio"] = coverage
            self.metadata["acquisition_duration_covered"] = coverage >= 0.9
            if not self.metadata["acquisition_duration_covered"]:
                self.metadata["warnings"].append(
                    f"Display waveform covers {waveform_s:.3f}s of {acquired_s:.3f}s "
                    f"host acquisition ({coverage:.1%}). Power data invalid."
                )
                power = np.full_like(power, np.nan)
            self.metadata["power_data_valid"] = bool(
                self.metadata["power_calibrated"]
                and self.metadata["acquisition_duration_covered"]
            )
            self.metadata["warnings"].append(
                "Power and energy use 1200-point NORM display data; "
                "not motion-only energy. RAW scaling remains unverified."
            )
            self.sample = int(t.size)
            if self.sample < 2:
                raise ValueError("Insufficient samples in display waveform window")
            t, current, voltage, power = self._downsample(t, current, voltage, power)
            with (self.run_dir / "rigol_scope.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["sample", "time_s", "current_A", "voltage_V", "power_W"])
                writer.writerows(
                    (i, float(x), float(a), float(v), float(p))
                    for i, (x, a, v, p) in enumerate(zip(t, current, voltage, power), 1)
                )
            self.metadata["preview_points"] = len(t)
            self._save_metadata()
            return {
                "resource": self.resource_name,
                "samples": self.sample,
                "error": (
                    "Rigol waveform duration shorter than acquisition duration"
                    if not self.metadata["acquisition_duration_covered"]
                    else None
                ),
                "warnings": self.metadata["warnings"],
                "power_trace_source": self.metadata["power_trace_source"],
                "power_calibrated": self.metadata["power_calibrated"],
                "power_data_valid": self.metadata["power_data_valid"],
            }
        except Exception as exc:
            self.error = repr(exc)
            self.metadata["error"] = self.error
            self._save_metadata()
            return {"resource": self.resource_name, "samples": self.sample,
                    "error": self.error}
        finally:
            self.close()

    def close(self):
        if self.scope is not None:
            try:
                self.scope.close()
            finally:
                self.scope = None
        if self.resource_manager is not None:
            try:
                self.resource_manager.close()
            finally:
                self.resource_manager = None
        self._started = False
