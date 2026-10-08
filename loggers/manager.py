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
                download_raw=cfg.rigol_download_raw,
                current_A_per_unit=cfg.rigol_current_A_per_unit,
                voltage_V_per_unit=cfg.rigol_voltage_V_per_unit,
            )
        if cfg.camera_url:
            self.camera = RTSPVideoRecorder(cfg.camera_url, run_dir)

    def event(self, name, details=""):
        if self.robot_started:
            self.robot.write_event(name, str(details))

    def start(self):
        """Start video and scope first; start robot feedback near the motion."""
        if self.camera is not None:
            if self.cfg.camera_pre_delay_s:
                time.sleep(self.cfg.camera_pre_delay_s)
            self.camera.start()
            self.camera_started = True

        scope_started = None
        if self.rigol is not None:
            self.rigol.start(self.robot.t0)
            self.rigol_started = True
            value = self.rigol.metadata.get("host_start_perf_s")
            if isinstance(value, (int, float)):
                scope_started = value

        # Guarantee at least the requested Rigol lead while starting robot
        # feedback only near the end of the waiting period.
        robot_pre_s = self.cfg.robot_logger_pre_delay_s
        rigol_lead_s = self.cfg.rigol_pre_delay_s if self.rigol_started else 0.0
        before_robot_s = max(0.0, rigol_lead_s - robot_pre_s)
        if scope_started is not None:
            remaining = max(0.0, before_robot_s -
                            (time.perf_counter() - scope_started))
        else:
            remaining = before_robot_s
        if remaining:
            time.sleep(remaining)

        self.robot.start()
        self.robot_started = True
        if not self.robot.first_packet.wait(5.0):
            raise TimeoutError("No robot feedback received")
        self.event("ROBOT_LOGGER_STARTED")
        if self.camera_started:
            self.event("CAMERA_STARTED", "Camera started before robot feedback")
        if self.rigol_started:
            self.event("RIGOL_STARTED", "Rigol started before robot feedback")

        # Wait until both the robot's requested pre-roll and the Rigol's
        # requested lead have elapsed. The lead is based on :RUN's timestamp.
        started_feedback = time.perf_counter()
        remaining_feedback = robot_pre_s
        remaining_scope = 0.0
        if scope_started is not None:
            remaining_scope = max(0.0, rigol_lead_s -
                                  (time.perf_counter() - scope_started))
        elif self.rigol_started:
            remaining_scope = rigol_lead_s
        remaining = max(remaining_feedback, remaining_scope)
        if remaining:
            time.sleep(remaining)
        robot_lead = time.perf_counter() - started_feedback
        self.event("ROBOT_PREMOTION_READY", f"lead_s={robot_lead:.6f}")
        print(f"[ROBOT LOG] Feedback active {robot_lead:.3f}s before motion", flush=True)
        if scope_started is not None:
            rigol_lead = time.perf_counter() - scope_started
            self.event("RIGOL_PREMOTION_READY", f"lead_s={rigol_lead:.6f}")
            print(f"[RIGOL] Armed {rigol_lead:.3f}s before motion command", flush=True)

    def stop(self):
        """Stop feedback promptly; keep camera recording through Rigol transfer.

        Errors from one device must not prevent finalizing the other devices.
        """
        result = {}

        # End robot feedback shortly after MOTION_END. Its timestamps are
        # already stored in events.csv; prolonged VISA transfer is not motion.
        if self.robot_started:
            try:
                if self.cfg.robot_logger_post_delay_s:
                    time.sleep(self.cfg.robot_logger_post_delay_s)
                self.event("ROBOT_LOGGER_STOPPING")
                result["robot"] = self.robot.stop()
            except Exception as exc:
                result["robot_error"] = repr(exc)
            finally:
                self.robot_started = False

        # Save oscilloscope data BEFORE ending camera recording. The camera
        # therefore continues recording fluid settling throughout the
        # acquisition remainder and data transfer.
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
            finally:
                self.rigol_started = False

        # This delay is deliberately applied AFTER Rigol.stop() returns.
        # It captures an additional tail even when display transfer is fast.
        if self.camera is not None and self.camera_started:
            try:
                if self.cfg.camera_stop_delay_s:
                    time.sleep(self.cfg.camera_stop_delay_s)
                result["camera"] = self.camera.stop()
            except Exception as exc:
                result["camera_error"] = repr(exc)
            finally:
                self.camera_started = False

        return result
