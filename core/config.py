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
    gain: float = 500.0
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
    camera_url: str | None = None
    camera_pre_delay_s: float = 2.0
    camera_stop_delay_s: float = 2.0
    rigol_pre_delay_s: float = 2.0
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
        if self.motion_timeout_s <= 0:
            raise ValueError("Invalid timeout")
        if self.settle_s < 0:
            raise ValueError("Invalid settle time")
        if self.tool_index is not None and not 0 <= self.tool_index <= 50:
            raise ValueError("Invalid tool index")
        if self.payload_kg is not None and self.payload_kg < 0:
            raise ValueError("Invalid payload")
