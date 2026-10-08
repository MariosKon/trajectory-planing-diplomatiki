import time
from .robot_logger import RawFeedbackLogger
from .rigol_logger import RigolScopeLogger
from .camera_logger import RTSPVideoRecorder

class LoggingManager:
    def __init__(self, cfg, run_dir):
        self.cfg = cfg
        self.robot = RawFeedbackLogger(cfg.robot_ip, run_dir)
        self.rigol = None
        self.camera = None
        self.robot_started = False
        self.rigol_started = False
        self.camera_started = False

        if cfg.rigol_resource:
            self.rigol = RigolScopeLogger(
                cfg.rigol_resource,
                run_dir,
                current_channel=cfg.rigol_current_channel,
                voltage_channel=cfg.rigol_voltage_channel,
                horizontal_scale_s_per_div=cfg.rigol_horizontal_scale_s_per_div,
                download_points=cfg.rigol_memory_depth,
                max_output_points=cfg.rigol_preview_points,
                current_A_per_unit=cfg.rigol_current_A_per_unit,
                voltage_V_per_unit=cfg.rigol_voltage_V_per_unit,
            )
        if cfg.camera_url:
            self.camera = RTSPVideoRecorder(cfg.camera_url, run_dir)

    def event(self, name, details=""):
        if self.robot_started:
            self.robot.write_event(name, str(details))

    def start(self):
        self.robot.start()
        self.robot_started = True
        if not self.robot.first_packet.wait(5.0):
            raise TimeoutError("No robot feedback received")
        self.event("ROBOT_LOGGER_STARTED")

        if self.camera is not None:
            if self.cfg.camera_pre_delay_s:
                time.sleep(self.cfg.camera_pre_delay_s)
            self.camera.start()
            self.camera_started = True
            self.event("CAMERA_STARTED")

        if self.rigol is not None:
            self.rigol.start(self.robot.t0)
            self.rigol_started = True
            self.event("RIGOL_STARTED")
            if self.cfg.rigol_pre_delay_s:
                time.sleep(self.cfg.rigol_pre_delay_s)

    def stop(self):
        result = {}

        if self.camera is not None and self.camera_started:
            try:
                if self.cfg.camera_stop_delay_s:
                    time.sleep(self.cfg.camera_stop_delay_s)
                result["camera"] = self.camera.stop()
            except Exception as exc:
                result["camera_error"] = repr(exc)
            self.camera_started = False

        # Save only useful robot feedback, not the potentially long
        # USB waveform transfer that follows. MOTION_END was logged by runner.
        if self.robot_started:
            try:
                result["robot"] = self.robot.stop()
            except Exception as exc:
                result["robot_error"] = repr(exc)
            self.robot_started = False

        if self.rigol is not None:
            try:
                if self.rigol_started:
                    if self.cfg.rigol_stop_delay_s:
                        time.sleep(self.cfg.rigol_stop_delay_s)
                    result["rigol"] = self.rigol.stop()
                elif self.rigol.scope is not None:
                    self.rigol.close()
            except Exception as exc:
                result["rigol_error"] = repr(exc)
            self.rigol_started = False

        return result
