# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
机器人状态数据模型
"""

from dataclasses import dataclass, field
from typing import List
from enum import IntEnum


class RobotMode(IntEnum):
    """机器人运行模式
    
    参考TCP/IP文档定义
    """
    UNKNOWN = 0         # 未知/未初始化（Feedback数据包可能返回）
    INIT = 1           # 初始化状态
    BRAKE_OPEN = 2     # 有任意关节抱闸松开
    POWEROFF = 3       # 下电状态
    DISABLED = 4       # 未使能（无抱闸松开）
    ENABLE = 5         # 使能且空闲
    BACKDRIVE = 6      # 拖拽模式
    RUNNING = 7        # 运行状态（工程、TCP队列运动等）
    SINGLE_MOVE = 8    # 单次运动状态（点动、RunTo等）
    ERROR = 9          # 报警状态
    PAUSE = 10         # 暂停状态
    JOG = 11           # 点动状态


@dataclass
class JointState:
    """关节状态"""
    q_actual: List[float] = field(default_factory=lambda: [0.0] * 6)  # 实际角度
    q_target: List[float] = field(default_factory=lambda: [0.0] * 6)  # 目标角度
    qd_actual: List[float] = field(default_factory=lambda: [0.0] * 6)  # 实际速度
    qd_target: List[float] = field(default_factory=lambda: [0.0] * 6)  # 目标速度
    qdd_target: List[float] = field(default_factory=lambda: [0.0] * 6)  # 目标加速度
    i_actual: List[float] = field(default_factory=lambda: [0.0] * 6)  # 实际电流
    i_target: List[float] = field(default_factory=lambda: [0.0] * 6)  # 目标电流
    m_actual: List[float] = field(default_factory=lambda: [0.0] * 6)  # 实际扭矩
    m_target: List[float] = field(default_factory=lambda: [0.0] * 6)  # 目标扭矩
    temperatures: List[float] = field(default_factory=lambda: [0.0] * 6)  # 电机温度
    joint_modes: List[float] = field(default_factory=lambda: [0.0] * 6)  # 关节控制模式
    voltages: List[float] = field(default_factory=lambda: [0.0] * 6)  # 关节电压


@dataclass
class CartesianPose:
    """笛卡尔位姿"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    
    def to_list(self) -> List[float]:
        """转换为列表"""
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]


@dataclass
class Quaternion:
    """四元数 [qw, qx, qy, qz]"""
    qw: float = 0.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    
    def to_list(self) -> List[float]:
        """转换为列表"""
        return [self.qw, self.qx, self.qy, self.qz]


@dataclass
class RobotStatus:
    """
    机器人完整状态
    
    从Feedback数据包解析得到（1440字节）
    """
    # 基本状态
    robot_mode: RobotMode = RobotMode.INIT
    speed_scaling: float = 0.0  # 速度比例 0-100
    enable_status: bool = False  # 使能状态
    brake_status: bool = False  # 抱闸状态
    error_status: bool = False  # 错误状态
    running_status: int = 0  # 运行状态（字节位置: 1028，0表示空闲，非0表示运动中）
    drag_status: int = 0  # 拖拽状态（0:不在拖拽，1:关节拖拽，2:力控拖拽）
    jog_status: int = 0  # 点动状态
    robot_type: int = 0  # 机器人型号
    
    # IO状态
    digital_inputs: int = 0  # 数字输入（64位）
    digital_outputs: int = 0  # 数字输出（64位）
    safety_io_in: int = 0  # 安全IO输入
    safety_io_out: int = 0  # 安全IO输出
    
    # 时间信息
    timestamp: int = 0  # Unix时间戳（ms）
    run_time: int = 0  # 开机运行时间（ms）
    
    # 电气信息
    voltage: float = 0.0  # 机器人电压
    current: float = 0.0  # 机器人电流
    
    # 程序状态
    program_state: float = 0.0  # 脚本运行状态
    
    # 当前指令ID
    current_command_id: int = 0
    
    # 关节状态
    joint_state: JointState = field(default_factory=JointState)
    
    # 笛卡尔位姿
    tool_vector_actual: CartesianPose = field(default_factory=CartesianPose)
    tool_vector_target: CartesianPose = field(default_factory=CartesianPose)
    tcp_speed_actual: CartesianPose = field(default_factory=CartesianPose)  # TCP实际速度
    tcp_speed_target: CartesianPose = field(default_factory=CartesianPose)  # TCP目标速度
    
    # 力信息
    actual_tcp_force: List[float] = field(default_factory=lambda: [0.0] * 6)  # TCP各轴受力（六维力计算）
    tcp_force: List[float] = field(default_factory=lambda: [0.0] * 6)  # TCP力值（关节电流计算）
    
    # 负载信息
    load: float = 0.0  # 末端负载重量（kg）
    load_center_x: float = 0.0  # 负载X偏心（mm）
    load_center_y: float = 0.0  # 负载Y偏心（mm）
    load_center_z: float = 0.0  # 负载Z偏心（mm）
    
    # 坐标系
    user_coordinate: int = 0  # 用户坐标系编号
    tool_coordinate: int = 0  # 工具坐标系编号
    user_value: List[float] = field(default_factory=lambda: [0.0] * 6)  # 用户坐标系坐标值
    tool_value: List[float] = field(default_factory=lambda: [0.0] * 6)  # 工具坐标系坐标值
    
    # 四元数
    target_quaternion: Quaternion = field(default_factory=Quaternion)  # 目标四元数
    actual_quaternion: Quaternion = field(default_factory=Quaternion)  # 实际四元数
    
    # 速度/加速度比例
    velocity_ratio: int = 0  # 关节速度比例（0-100）
    acceleration_ratio: int = 0  # 关节加速度比例（0-100）
    xyz_velocity_ratio: int = 0  # 笛卡尔位置速度比例（0-100）
    r_velocity_ratio: int = 0  # 笛卡尔姿态速度比例（0-100）
    xyz_acceleration_ratio: int = 0  # 笛卡尔位置加速度比例（0-100）
    r_acceleration_ratio: int = 0  # 笛卡尔姿态加速度比例（0-100）
    
    # 队列状态
    run_queued_cmd: int = 0  # 算法队列运行标志
    pause_cmd_flag: int = 0  # 算法队列暂停标志
    
    # 手系
    hand_type: List[int] = field(default_factory=lambda: [0] * 4)  # 手系（备用参数）
    
    # 末端按钮信号
    drag_button_signal: int = 0  # 拖拽按钮信号
    enable_button_signal: int = 0  # 使能按钮信号
    record_button_signal: int = 0  # 录制按钮信号
    reappear_button_signal: int = 0  # 复现按钮信号
    jaw_button_signal: int = 0  # 夹爪控制信号
    
    # 六维力传感器
    six_force_online: int = 0  # 六维力在线状态（0:离线，1:在线，2:异常）
    six_force_value: List[float] = field(default_factory=lambda: [0.0] * 6)  # 六维力原始值
    
    # 安全状态
    collision_state: int = 0  # 碰撞状态
    arm_approach_state: int = 0  # 小臂安全皮肤接近暂停
    j4_approach_state: int = 0  # J4安全皮肤接近暂停
    j5_approach_state: int = 0  # J5安全皮肤接近暂停
    j6_approach_state: int = 0  # J6安全皮肤接近暂停
    safety_state: int = 0  # 安全状态（位掩码）
    
    # 抖动检测
    vibration_dis_z: float = 0.0  # Z轴抖动位移
    
    # 模式
    auto_manual_mode: int = 0  # 手动/自动模式
    export_status: int = 0  # U盘导出状态
    
    def is_ready(self) -> bool:
        """检查机器人是否就绪"""
        return (
            self.robot_mode == RobotMode.ENABLE and
            not self.error_status and
            self.enable_status
        )
    
    def has_error(self) -> bool:
        """检查是否有错误"""
        return self.robot_mode == RobotMode.ERROR or self.error_status
    
    def is_moving(self) -> bool:
        """检查机器人是否运动中
        
        RunningStatus 字节位置: 1028
        状态值说明:
        - 0: 空闲
        - 非0: 运动中（具体值需参考协议文档）
        """
        return self.running_status != 0
    
    def get_safety_state_desc(self) -> str:
        """获取安全状态描述"""
        states = []
        if self.safety_state & 0x01: states.append("急停")
        if self.safety_state & 0x02: states.append("防护性停止")
        if self.safety_state & 0x04: states.append("缩减模式")
        if self.safety_state & 0x08: states.append("非停止")
        if self.safety_state & 0x10: states.append("运动中")
        if self.safety_state & 0x20: states.append("系统急停")
        if self.safety_state & 0x40: states.append("用户急停")
        if self.safety_state & 0x80: states.append("安全原点")
        return ", ".join(states) if states else "正常"
