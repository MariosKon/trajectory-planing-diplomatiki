# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""Robot Control模块 - 状态查询、运动学计算、可达性检查、机器人控制"""

from typing import Tuple, Sequence
from ..core.connection import DobotConnection


class RobotControl:
    """Robot控制模块 - 状态查询、运动学计算、可达性检查、日志、脚本控制"""

    def __init__(self, connection: DobotConnection):
        self.connection = connection

    def _send_cmd(self, command: str) -> str:
        """发送命令并接收响应"""
        return self.connection.send_receive_text(command)

    # ==================== 控制模式与电源====================

    def RequestControl(self) -> str:
        """
        RequestControl请求将设备控制模式切换为TCP模式（立即指令）
        
        说明：
        - 只有在TCP模式下才可执行其他TCP指令
        - 仅当机器人处于未上电或下使能（且非暂停或松抱闸状态）时才可切换TCP模式
        - 调用此接口后，才能执行EnableRobot、运动指令等
        
        Returns:
            str: ErrorID,{},RequestControl();
        """
        return self._send_cmd("RequestControl()")

    def PowerOn(self) -> str:
        """PowerOn机器人上电（立即指令）"""
        return self._send_cmd("PowerOn()")

    def EnableRobot(self, load: float = 0.0, **kwargs) -> str:
        """
        EnableRobot使能机器人（立即指令）

        原型：EnableRobot(load,centerX,centerY,centerZ,isCheck)

        Args:
            load: 负载重量 (kg)
            centerX: 负载重心X坐标 (mm)
            centerY: 负载重心Y坐标 (mm)
            centerZ: 负载重心Z坐标 (mm)
            isCheck: 是否检查负载 (0=不检查, 1=检查)
        """
        if load == 0.0:
            cmd = "EnableRobot()"
        elif 'centerX' not in kwargs:
            cmd = f"EnableRobot({load:.6f})"
        else:
            cx = kwargs.get('centerX', 0.0)
            cy = kwargs.get('centerY', 0.0)
            cz = kwargs.get('centerZ', 0.0)
            check = kwargs.get('isCheck', 0)
            cmd = f"EnableRobot({load:.6f},{cx:.6f},{cy:.6f},{cz:.6f},{check})"
        return self._send_cmd(cmd)

    def DisableRobot(self) -> str:
        """DisableRobot下使能机器人（立即指令）"""
        return self._send_cmd("DisableRobot()")

    def ClearError(self) -> str:
        """ClearError清除机器人报警（立即指令）"""
        return self._send_cmd("ClearError()")

    # ==================== 运动控制 ====================

    def RunScript(self, script_name: str) -> str:
        """
        RunScript运行指定工程（立即指令）
        
        Args:
            script_name: 脚本文件名        """
        return self._send_cmd(f"RunScript(\"{script_name}\")")

    def Stop(self) -> str:
        """Stop停止运动（或正在运行的工程）（立即指令）"""
        return self._send_cmd("Stop()")

    def Pause(self) -> str:
        """Pause暂停运动（或正在运行的工程）（立即指令）"""
        return self._send_cmd("Pause()")

    def Continue(self) -> str:
        """Continue继续运动（或已暂停的工程）（立即指令）"""
        return self._send_cmd("Continue()")

    def EmergencyStop(self, mode: int) -> str:
        """
        EmergencyStop紧急停止机器人（立即指令）
        
        Args:
            mode: 急停操作模式。1表示按下急停,0表示松开急停。
        """
        if mode not in [0, 1]:
            raise ValueError("mode必须是0或1")
        return self._send_cmd(f"EmergencyStop({mode})")

    # ==================== 抱闸与拖拽====================

    def BrakeControl(self, axis_id: int, value: int) -> str:
        """
        BrakeControl控制指定关节的抱闸（立即指令）        
        Args:
            axis_id: 关节编号 (1-6)
            value: 0-抱闸, 1-松闸
        """
        if not 1 <= axis_id <= 6:
            raise ValueError("关节编号必须在1-6之间")
        if value not in [0, 1]:
            raise ValueError("value必须是0或1")
        return self._send_cmd(f"BrakeControl({axis_id},{value})")

    def StartDrag(self) -> str:
        """StartDrag机器人进入关节拖拽模式（立即指令）"""
        return self._send_cmd("StartDrag()")

    def StopDrag(self) -> str:
        """StopDrag机器人退出拖拽模式（立即指令）"""
        return self._send_cmd("StopDrag()")

    def DragSensitivity(self, index: int, value: int) -> str:
        """
        DragSensitivity设置拖拽灵敏度（立即指令）
        
        Args:
            index: 轴序号, 取值范围: [0,6]。0表示所有轴设置为相同的灵敏度。1~6分别表示设置J1~J6轴的灵敏度。
            value: 拖拽灵敏度, 值越小, 拖拽时的阻力越大。取值范围: [1, 90]。
        """
        if not 0 <= index <= 6:
            raise ValueError("轴序号必须在0-6之间")
        if not 1 <= value <= 90:
            raise ValueError("拖拽灵敏度必须在1-90之间")
        return self._send_cmd(f"DragSensitivity({index},{value})")

    # ==================== 速度与加速度设置 ====================

    def SpeedFactor(self, factor: int) -> str:
        """
        SpeedFactor设置全局速度比例（立即指令）
        
        Args:
            factor: 速度比例 (1-100)
        """
        if not 1 <= factor <= 100:
            raise ValueError("速度比例必须在1-100之间")
        return self._send_cmd(f"SpeedFactor({factor})")

    def AccJ(self, acc: int) -> str:
        """
        AccJ设置关节运动方式的加速度比例（立即指令）
        
        Args:
            acc: 加速度比例 (1-100)
        """
        if not 1 <= acc <= 100:
            raise ValueError("加速度比例必须在1-100之间")
        return self._send_cmd(f"AccJ({acc})")

    def AccL(self, acc: int) -> str:
        """
        AccL设置直线和弧线运动方式的加速度比例（立即指令）
        
        Args:
            acc: 加速度比例 (1-100)
        """
        if not 1 <= acc <= 100:
            raise ValueError("加速度比例必须在0-100之间")
        return self._send_cmd(f"AccL({acc})")

    def VelJ(self, vel: int) -> str:
        """
        VelJ设置关节运动方式的速度比例（立即指令）
        
        Args:
            vel: 速度比例 (1-100)
        """
        if not 1 <= vel <= 100:
            raise ValueError("速度比例必须在0-100之间")
        return self._send_cmd(f"VelJ({vel})")

    def VelL(self, vel: int) -> str:
        """
        VelL设置直线和弧线运动方式的速度比例（立即指令）
        
        Args:
            vel: 速度比例 (1-100)
        """
        if not 1 <= vel <= 100:
            raise ValueError("速度比例必须在0-100之间")
        return self._send_cmd(f"VelL({vel})")

    def CP(self, value: int) -> str:
        """
        CP设置平滑过渡比例（立即指令）
        
        Args:
            value: 平滑过渡比例 (0-100)
        """
        if not 0 <= value <= 100:
            raise ValueError("平滑过渡比例必须在0-100之间")
        return self._send_cmd(f"CP({value})")

    # ==================== 坐标系设置====================

    def User(self, index: int) -> str:
        """
        User设置全局用户坐标系（队列指令）        
        Args:
            index: 用户坐标系编号(0-50)
        """
        if not 0 <= index <= 50:
            raise ValueError("用户坐标系编号必须在0-50之间")
        return self._send_cmd(f"User({index})")

    def SetUser(self, index: int, pose: Sequence[float], type: int = None) -> str:
        """
        SetUser修改指定的用户坐标系（立即指令）
        
        Args:
            index: 用户坐标系编号(1-50)
            pose: 6个坐标参数[x,y,z,rx,ry,rz]
            type: 是否使坐标系改动全局生效。0: 该命令修改的坐标系仅在当前工程运行中生效。1: 该命令修改的坐标系将会被控制器保存。
        """
        if not 1 <= index <= 50:
            raise ValueError("用户坐标系编号必须在1-50之间")
        if len(pose) != 6:
            raise ValueError("pose需要6个参数")
        pose_str = "{" + ",".join([f"{v:.6f}" for v in pose]) + "}"
        if type is not None:
            if type not in [0, 1]:
                raise ValueError("type必须是0或1")
            return self._send_cmd(f"SetUser({index},{pose_str},{type})")
        return self._send_cmd(f"SetUser({index},{pose_str})")

    def CalcUser(self, index: int, matrix_direction: int, offset: Sequence[float]) -> str:
        """
        CalcUser计算用户坐标系（立即指令）
        Args:
            index: 用户坐标系编号(0-50)
            matrix_direction: 计算方向 (1-左乘，坐标系沿基坐标系偏转; 0-右乘，坐标系沿自身偏转)
            offset: 偏移值 [x,y,z,rx,ry,rz]
        """
        if not 0 <= index <= 50:
            raise ValueError("用户坐标系编号必须在0-50之间")
        if matrix_direction not in [0, 1]:
            raise ValueError("matrix_direction 必须是0或1")
        if len(offset) != 6:
            raise ValueError("offset需要6个参数")
        offset_str = "{" + ",".join([f"{v:.6f}" for v in offset]) + "}"
        return self._send_cmd(f"CalcUser({index},{matrix_direction},{offset_str})")

    def Tool(self, index: int) -> str:
        """
        Tool设置全局工具坐标系（队列指令）        
        Args:
            index: 工具坐标系编号(0-50)
        """
        if not 0 <= index <= 50:
            raise ValueError("工具坐标系编号必须在0-50之间")
        return self._send_cmd(f"Tool({index})")

    def SetTool(self, index: int, pose: Sequence[float], type: int = None) -> str:
        """
        SetTool修改指定的工具坐标系（立即指令）
        
        Args:
            index: 工具坐标系编号(1-50)
            pose: 6个坐标参数[x,y,z,rx,ry,rz]
            type: 是否使坐标系改动全局生效。0: 该命令修改的坐标系仅在当前工程运行中生效。1: 该命令修改的坐标系将会被控制器保存。
        """
        if not 1 <= index <= 50:
            raise ValueError("工具坐标系编号必须在1-50之间")
        if len(pose) != 6:
            raise ValueError("pose需要6个参数")
        pose_str = "{" + ",".join([f"{v:.6f}" for v in pose]) + "}"
        if type is not None:
            if type not in [0, 1]:
                raise ValueError("type必须是0或1")
            return self._send_cmd(f"SetTool({index},{pose_str},{type})")
        return self._send_cmd(f"SetTool({index},{pose_str})")

    def CalcTool(self, index: int, matrix_direction: int, offset: Sequence[float]) -> str:
        """
        CalcTool计算工具坐标系（立即指令）
        Args:
            index: 工具坐标系编号(0-50)
            matrix_direction: 计算方向 (1-左乘，坐标系沿法兰坐标系偏转; 0-右乘，坐标系沿自身偏转)
            offset: 偏移值 [x,y,z,rx,ry,rz]
        """
        if not 0 <= index <= 50:
            raise ValueError("工具坐标系编号必须在0-50之间")
        if matrix_direction not in [0, 1]:
            raise ValueError("matrix_direction 必须是0或1")
        if len(offset) != 6:
            raise ValueError("offset需要6个参数")
        offset_str = "{" + ",".join([f"{v:.6f}" for v in offset]) + "}"
        return self._send_cmd(f"CalcTool({index},{matrix_direction},{offset_str})")

    # ==================== 负载设置 ====================

    def SetPayload(self, load_or_name, *args, **kwargs) -> str:
        """
        SetPayload设置机械臂末端负载（队列指令）

        支持两种调用方式（与文档完全一致）：
        方式一：SetPayload(load, x, y, z)
        方式二：SetPayload(name)

        同时保持向后兼容：SetPayload(load, center=[x,y,z])

        Args:
            load_or_name:
                - float: 负载重量 (kg) → 方式一
                - str: 预设负载参数组名称 → 方式二
            x (可选, float): 末端负载X轴偏心坐标 (mm)
            y (可选, float): 末端负载Y轴偏心坐标 (mm)
            z (可选, float): 末端负载Z轴偏心坐标 (mm)
            center (可选, Sequence[float]): 向后兼容，负载重心[x,y,z]
            preset_name (可选, str): 向后兼容，若传入则忽略前两者，等效于方式二
        """
        center = kwargs.get('center', None)
        preset_name = kwargs.get('preset_name', None)

        if isinstance(load_or_name, str):
            return self._send_cmd(f'SetPayload("{load_or_name}")')

        if preset_name is not None:
            return self._send_cmd(f'SetPayload("{preset_name}")')

        load = float(load_or_name)

        x = y = z = None
        if len(args) == 3:
            x, y, z = args
        elif len(args) == 1 and isinstance(args[0], (list, tuple)):
            if len(args[0]) != 3:
                raise ValueError("center列表需要3个参数[x,y,z]")
            x, y, z = args[0]
        elif center is not None:
            if len(center) != 3:
                raise ValueError("center需要3个参数[x,y,z]")
            x, y, z = center
        elif len(args) != 0:
            raise ValueError("位置参数只支持 SetPayload(load, x, y, z) 三参数形式 或 SetPayload(load, [x,y,z]) 列表形式")

        if x is not None and y is not None and z is not None:
            return self._send_cmd(f"SetPayload({load:.6f},{float(x):.6f},{float(y):.6f},{float(z):.6f})")
        return self._send_cmd(f"SetPayload({load:.6f})")

    # ==================== 碰撞检测设置====================

    def SetCollisionLevel(self, level: int) -> str:
        """
        SetCollisionLevel设置碰撞检测等级（队列指令）        
        Args:
            level: 碰撞检测等级(0-5)，0为关闭碰撞检测，1~5数字越大灵敏度越高
        """
        if not 0 <= level <= 5:
            raise ValueError("碰撞检测等级必须在0-5之间")
        return self._send_cmd(f"SetCollisionLevel({level})")

    def SetBackDistance(self, distance: float) -> str:
        """
        SetBackDistance设置碰撞回退距离（队列指令）
        
        Args:
            distance: 碰撞回退距离 (mm)，取值范围 [0, 50]
        """
        if not 0 <= distance <= 50:
            raise ValueError("distance 必须在0到50之间(单位mm)")
        return self._send_cmd(f"SetBackDistance({distance:.6f})")

    def SetPostCollisionMode(self, mode: int) -> str:
        """
        SetPostCollisionMode设置碰撞后处理方式（队列指令）
        Args:
            mode: 碰撞后处理模式
                  0: 下使能并停止运动  （V4.6.6官方文档定义 ✅）
                  1: 暂停运动          （V4.6.6官方文档定义 ✅）
                  2: 忽略碰撞继续运动  （⚠️ 扩展模式，部分固件支持，V4.6.6官方文档未定义）
        """
        if mode not in [0, 1, 2]:
            raise ValueError("碰撞后处理模式必须是0、1或2")
        return self._send_cmd(f"SetPostCollisionMode({mode})")

    # ==================== 安全皮肤与安全区域====================

    def EnableSafeSkin(self, status: int) -> str:
        """
        EnableSafeSkin开启或关闭安全皮肤功能（队列指令）
        
        Args:
            status: 0-关闭, 1-开启        """
        if status not in [0, 1]:
            raise ValueError("状态必须是0或1")
        return self._send_cmd(f"EnableSafeSkin({status})")

    def SetSafeSkin(self, part: int, sensitivity: int) -> str:
        """
        SetSafeSkin设置安全皮肤各个部位的灵敏度（队列指令）
        
        Args:
            part: 安全皮肤部位编号。3=小臂，4~6=J4~J6
            sensitivity: 灵敏度等级 [0, 3]。0=关闭，1=低，2=中，3=高
        """
        if not (part == 3 or 4 <= part <= 6):
            raise ValueError("part 只能是 3(小臂) 或 4~6 (J4~J6)")
        if not 0 <= sensitivity <= 3:
            raise ValueError("sensitivity 必须在0到3之间")
        return self._send_cmd(f"SetSafeSkin({part},{sensitivity})")

    def SetSafeWallEnable(self, index: int, status: int) -> str:
        """
        SetSafeWallEnable开启或关闭指定的安全墙（队列指令）
        
        Args:
            index: 安全墙编号            status: 0-关闭, 1-开启        """
        if status not in [0, 1]:
            raise ValueError("状态必须是0或1")
        return self._send_cmd(f"SetSafeWallEnable({index},{status})")

    def SetWorkZoneEnable(self, index: int, status: int) -> str:
        """
        SetWorkZoneEnable开启或关闭指定的安全区域（队列指令）        
        Args:
            index: 安全区域编号
            status: 0-关闭, 1-开启        """
        if status not in [0, 1]:
            raise ValueError("状态必须是0或1")
        return self._send_cmd(f"SetWorkZoneEnable({index},{status})")

    # ==================== 状态查询====================

    def RobotMode(self) -> str:
        """RobotMode获取机器人当前状态（立即指令）"""
        return self._send_cmd("RobotMode()")

    def GetPose(self, user: int = None, tool: int = None) -> str:
        """
        GetPose获取机器人当前位姿在指定坐标系下的笛卡尔坐标（立即指令）
        
        Args:
            user: 用户坐标系索引(0-50)
            tool: 工具坐标系索引(0-50)
        """
        has_coord = user is not None or tool is not None
        if has_coord and (user is None or tool is None):
            raise ValueError("user 和 tool 参数必须同时设置或都不设置")

        if has_coord:
            if not (0 <= user <= 50):
                raise ValueError("user 必须在0-50 之间")
            if not (0 <= tool <= 50):
                raise ValueError("tool 必须在0-50 之间")
            return self._send_cmd(f"GetPose(user={user},tool={tool})")
        else:
            return self._send_cmd("GetPose()")

    def GetAngle(self) -> str:
        """GetAngle获取机器人当前位姿的关节坐标（立即指令）"""
        return self._send_cmd("GetAngle()")

    def GetErrorID(self) -> str:
        """GetErrorID获取机器人当前报错的错误码（立即指令）"""
        return self._send_cmd("GetErrorID()")

    def GetScrName(self) -> str:
        """GetScrName获取当前机器人正在运行的脚本名称（立即指令）"""
        return self._send_cmd("GetScrName()")

    # ==================== 运动学计算====================

    def PositiveKin(self, joints: Sequence[float], user: int = -1, tool: int = -1) -> str:
        """
        PositiveKin进行正解运算（立即指令）
        
        Args:
            joints: 6个关节角度[j1,j2,j3,j4,j5,j6] (°)
            user: 用户坐标系编号。默认为-1，表示当前用户坐标系。
            tool: 工具坐标系编号。默认为-1，表示当前工具坐标系。
        """
        if len(joints) != 6:
            raise ValueError("需要6个关节角度")
        joint_str = ",".join([f"{j:.6f}" for j in joints])
        if user != -1 and tool != -1:
            return self._send_cmd(f"PositiveKin({joint_str},user={user},tool={tool})")
        return self._send_cmd(f"PositiveKin({joint_str})")

    def InverseKin(self, pose: Sequence[float], use_joint_near: int = 0, joint_near: Sequence[float] = None, user: int = -1, tool: int = -1) -> str:
        """
        InverseKin进行逆解运算（立即指令）
        
        Args:
            pose: 6个笛卡尔坐标 [x,y,z,rx,ry,rz]
            use_joint_near: 是否使用关节接近度约束。0: 不使用。1: 使用。
            joint_near: 关节接近度参考值 [j1,j2,j3,j4,j5,j6]。当useJointNear为1时生效。
            user: 用户坐标系编号。默认为-1，表示当前用户坐标系。
            tool: 工具坐标系编号。默认为-1，表示当前工具坐标系。
        """
        if len(pose) != 6:
            raise ValueError("需要6个位姿参数")
        pose_str = ",".join([f"{p:.6f}" for p in pose])
        params = [pose_str]
        if use_joint_near != 0:
            params.append(f"useJointNear={use_joint_near}")
            if joint_near is not None:
                if len(joint_near) != 6:
                    raise ValueError("joint_near需要6个关节角度")
                joint_near_str = "jointNear={" + ",".join([f"{j:.6f}" for j in joint_near]) + "}"
                params.append(joint_near_str)
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        return self._send_cmd(f"InverseKin({','.join(params)})")

    # ==================== 可达性检测====================

    def CheckOddMovL(self, p1: Sequence[float], p2: Sequence[float],
                     point_type: str = "joint",
                     user: int = -1, tool: int = -1,
                     a: float = -1, v: float = -1,
                     cp: float = None, r: float = None) -> str:
        """
        CheckOddMovL检查直线运动的点位可达性（立即指令）
        
        Args:
            p1: 起点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            p2: 终点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            point_type: 点位类型 "joint"（关节）或 "pose"（笛卡尔）
            user: 用户坐标系编号。-1 表示不指定
            tool: 工具坐标系编号。-1 表示不指定
            a: 加速度。-1 表示使用默认值
            v: 速度。-1 表示使用默认值
            cp: 连续度（与 r 二选一）
            r: 融合半径（与 cp 二选一，单位mm）
        """
        if len(p1) != 6:
            raise ValueError("p1需要6个值")
        if len(p2) != 6:
            raise ValueError("p2需要6个值")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type 只能是 'joint' 或 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        params = [f"{point_type}={{{p_values1}}}", f"{point_type}={{{p_values2}}}"]
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        elif r is not None:
            params.append(f"r={r:.6f}")
        return self._send_cmd(f"CheckOddMovL({','.join(params)})")

    def CheckOddMovJ(self, p1: Sequence[float], p2: Sequence[float],
                     point_type: str = "joint",
                     a: float = -1, v: float = -1,
                     cp: float = None) -> str:
        """
        CheckOddMovJ检查关节运动的点位可达性（立即指令）
        
        Args:
            p1: 起点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            p2: 终点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            point_type: 点位类型 "joint"（关节）或 "pose"（笛卡尔）
            a: 加速度。-1 表示使用默认值
            v: 速度。-1 表示使用默认值
            cp: 连续度
        """
        if len(p1) != 6:
            raise ValueError("p1需要6个值")
        if len(p2) != 6:
            raise ValueError("p2需要6个值")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type 只能是 'joint' 或 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        params = [f"{point_type}={{{p_values1}}}", f"{point_type}={{{p_values2}}}"]
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        return self._send_cmd(f"CheckOddMovJ({','.join(params)})")

    def CheckOddMovC(self, p1: Sequence[float], p2: Sequence[float], p3: Sequence[float],
                     point_type: str = "joint",
                     user: int = -1, tool: int = -1,
                     a: float = -1, v: float = -1,
                     cp: float = None, r: float = None) -> str:
        """
        CheckOddMovC检查圆弧运动的点位可达性（立即指令）
        
        Args:
            p1: 起点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            p2: 中间点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            p3: 终点 [j1,j2,j3,j4,j5,j6] 或 [x,y,z,rx,ry,rz]
            point_type: 点位类型 "joint"（关节）或 "pose"（笛卡尔）
            user: 用户坐标系编号。-1 表示不指定
            tool: 工具坐标系编号。-1 表示不指定
            a: 加速度。-1 表示使用默认值
            v: 速度。-1 表示使用默认值
            cp: 连续度（与 r 二选一）
            r: 融合半径（与 cp 二选一，单位mm）
        """
        if len(p1) != 6:
            raise ValueError("p1需要6个值")
        if len(p2) != 6:
            raise ValueError("p2需要6个值")
        if len(p3) != 6:
            raise ValueError("p3需要6个值")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type 只能是 'joint' 或 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        p_values3 = ",".join([f"{j:.6f}" for j in p3])
        params = [f"{point_type}={{{p_values1}}}",
                  f"{point_type}={{{p_values2}}}",
                  f"{point_type}={{{p_values3}}}"]
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        elif r is not None:
            params.append(f"r={r:.6f}")
        return self._send_cmd(f"CheckOddMovC({','.join(params)})")

    # ==================== 托盘相关 ====================

    def CreateTray(self, name: str, dimensions: Sequence[int],
                    points: list) -> str:
        """
        CreateTray创建托盘（立即指令）
        支持一维、二维、三维托盘。

        原型（与文档完全一致）：
        CreateTray(Trayname, {Count}, {P1},{P2}) -- 一维托盘
        CreateTray(Trayname, {row,col}, {P1},{P2},{P3},{P4}) -- 二维托盘
        CreateTray(Trayname, {row,col,layer}, {P1},{P2},{P3},{P4},{P5},{P6},{P7},{P8}) -- 三维托盘

        Args:
            name: 托盘名称（最长32字节字符串，不允许纯数字或纯空格）
            dimensions: 维度参数
                - 一维: [count] 点位数量[2,50]
                - 二维: [row, col] 行数和列数
                - 三维: [row, col, layer] 行数、列数、层数
            points: 端点列表，每个端点为[x,y,z,rx,ry,rz]格式，每个点位作为独立参数
                - 一维: 2个端点 [p1, p2]
                - 二维: 4个端点 [p1, p2, p3, p4]
                - 三维: 8个端点 [p1, p2, p3, p4, p5, p6, p7, p8]
        """
        dims = ",".join([str(d) for d in dimensions])
        point_strs = []
        for p in points:
            if len(p) != 6:
                raise ValueError(f"每个点位需要6个值[x,y,z,rx,ry,rz]，当前传入{len(p)}个")
            point_strs.append("{pose = {" + ",".join([f"{v:.6f}" for v in p]) + "}}")
        cmd = f"CreateTray({name},{{{dims}}}," + ",".join(point_strs) + ")"
        return self._send_cmd(cmd)

    def GetTrayPoint(self, trayname: str, index: int) -> str:
        """
        GetTrayPoint获取托盘点（立即指令）
        
        Args:
            trayname: 托盘名称（字符串，与 CreateTray 创建时的 name 对应）
            index: 托盘点位序号（从第几个开始，1-based）
        """
        if not trayname or not trayname.strip():
            raise ValueError("trayname 不能为空")
        if index < 1:
            raise ValueError("index 必须大于等于 1")
        return self._send_cmd(f"GetTrayPoint({trayname},{index})")

    # ==================== 日志导出 ====================

    def LogExportUSB(self, log_range: int = None) -> str:
        """
        LogExportUSB将机器人日志导出至U盘（立即指令）

        Args:
            log_range: 日志导出范围。
                0: 导出 logs/all 和 logs/user
                1: 导出 logs 文件夹所有内容
        """
        if log_range is not None:
            if log_range not in [0, 1]:
                raise ValueError("log_range必须是0或1")
            return self._send_cmd(f"LogExportUSB({log_range})")
        return self._send_cmd("LogExportUSB()")

    def GetExportStatus(self) -> str:
        """GetExportStatus获取日志导出状态（立即指令）"""
        return self._send_cmd("GetExportStatus()")