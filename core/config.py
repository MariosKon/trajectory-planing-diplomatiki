from dataclasses import dataclass, field
from pathlib import Path
import json

@dataclass
class Config:
    robot_ip: str = "192.168.5.1"
    home: list[float] = field(default_factory=lambda:
        [32, 40, 91, 48, 122, -180]
    )
    start: list[float] = field(default_factory=lambda:
        [-600, -400, 250, -90, 0, 90]
    )
    target: list[float] = field(default_factory=lambda:
        [-600, 400, 250, -90, 0, 90]
    )
    servo_time_s: float = 0.03
    aheadtime: float = 20.0
    gain: float = 500.0  # Legacy/ServoJ fallback
    servop_aheadtime: float = 20.0
    servop_gain: float = 300.0
    motion_timeout_s: float = 60.0
    settle_s: float = 3.0
    slow_speed: int = 50
    slow_acceleration: int = 50
    tool_index: int | None = None
    tool_pose: list[float] = field(default_factory=lambda: [0.0]*6)
    payload_kg: float | None = None
    rigol_resource: str | None = None
    rigol_current_channel: str = "CHAN1"
    rigol_voltage_channel: str = "CHAN2"
    rigol_horizontal_scale_s_per_div: float | None = 0.5
    rigol_memory_depth: int = 60000
    rigol_preview_points: int = 1200
    rigol_download_raw: bool = False
    rigol_current_A_per_unit: float | None = None
    rigol_voltage_V_per_unit: float = 1.0
    camera_url: str | None = None
    camera_pre_delay_s: float = 2.0
    camera_stop_delay_s: float = 2.0
    robot_logger_pre_delay_s: float = 0.5
    robot_logger_post_delay_s: float = 1.0
    rigol_pre_delay_s: float = 1.5
    rigol_stop_delay_s: float = 1.0

    @classmethod
    def load(cls, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        config = cls(**data)
        config.validate()
        return config

    def validate(self):
        for name in ("home", "start", "target", "tool_pose"):
            if len(getattr(self, name)) != 6:
                raise ValueError(f"{name} requires six values")
        if not 0.004 <= self.servo_time_s <= 3600:
            raise ValueError("Invalid servo time")
        if not 20 <= self.aheadtime <= 100:
            raise ValueError("Invalid aheadtime")
        if not 200 <= self.gain <= 1000:
            raise ValueError("Invalid gain")
        if not 20 <= self.servop_aheadtime <= 100:
            raise ValueError("Invalid ServoP aheadtime")
        if not 200 <= self.servop_gain <= 1000:
            raise ValueError("Invalid ServoP gain")
        if self.motion_timeout_s <= 0:
            raise ValueError("Invalid timeout")
        if self.settle_s < 0:
            raise ValueError("Invalid settle time")
        if self.tool_index is not None and not 0 <= self.tool_index <= 50:
            raise ValueError("Invalid tool index")
        if self.payload_kg is not None and self.payload_kg < 0:
            raise ValueError("Invalid payload")
        if self.rigol_horizontal_scale_s_per_div is not None and self.rigol_horizontal_scale_s_per_div <= 0:
            raise ValueError("Rigol timebase must be positive")
        if not isinstance(self.rigol_download_raw, bool):
            raise ValueError('rigol_download_raw must be true or false')
        if self.robot_logger_pre_delay_s < 0 or self.robot_logger_post_delay_s < 0:
            raise ValueError("Robot logger delays must be >= 0")
        if self.rigol_pre_delay_s < 0:
            raise ValueError("rigol_pre_delay_s must be >= 0")
        if self.camera_stop_delay_s < 0:
            raise ValueError('camera_stop_delay_s must be >= 0')
        if self.rigol_memory_depth < 2 or self.rigol_preview_points < 2:
            raise ValueError("Rigol point counts must be >= 2")
        if self.rigol_current_A_per_unit is not None and self.rigol_current_A_per_unit <= 0:
            raise ValueError("Invalid current calibration")
        if self.rigol_voltage_V_per_unit <= 0:
            raise ValueError("Invalid voltage calibration")
