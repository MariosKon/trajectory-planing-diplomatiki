"""
运动控制模块测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot
from dobot_sdk import CoordinateType


def test_motion_methods():
    """测试运动控制方法"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试MovJ方法
    assert hasattr(robot.motion, 'MovJ')
    print("MovJ方法存在")
    
    # 测试MovL方法
    assert hasattr(robot.motion, 'MovL')
    print("MovL方法存在")
    
    # 测试Arc方法
    assert hasattr(robot.motion, 'Arc')
    print("Arc方法存在")
    
    # 测试Circle方法
    assert hasattr(robot.motion, 'Circle')
    print("Circle方法存在")
    
    # 测试相对运动方法
    assert hasattr(robot.motion, 'RelMovL')
    assert hasattr(robot.motion, 'RelMovLTool')
    assert hasattr(robot.motion, 'RelMovLUser')
    print("相对运动方法存在")
    
    # 测试运动类型设置方法（这些接口统一由 robot_control 模块提供）
    assert hasattr(robot.robot_control, 'SpeedFactor')
    assert hasattr(robot.robot_control, 'AccJ')
    assert hasattr(robot.robot_control, 'AccL')
    print("速度/加速度设置方法存在 (robot_control 模块)")
    
    # 注意：原 motion 模块下的 ToolVoltage 接口在手臂二开md文档中不存在，已移除
    print("工具电压相关检查：文档无此接口，已跳过")
    
    # 测试伺服控制方法
    assert hasattr(robot.motion, 'ServoJ')
    assert hasattr(robot.motion, 'ServoP')
    print("伺服控制方法存在")
    
    # 测试Jog控制方法
    assert hasattr(robot.motion, 'MoveJog')
    print("Jog控制方法存在")
    
    del robot
    print("运动控制方法测试通过！")


def test_motion_command_generation():
    """测试运动指令生成"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试MovJ指令生成
    result = robot.motion.MovJ([400, 0, 300, 180, 0, 0], CoordinateType.CARTESIAN)
    assert result is not None
    print(f"MovJ指令: {result}")
    
    # 测试MovL指令生成
    result = robot.motion.MovL([400, 100, 300, 180, 0, 0], CoordinateType.CARTESIAN)
    assert result is not None
    print(f"MovL指令: {result}")
    
    # 测试相对运动（展开6个独立offset参数，按文档规范）
    result = robot.motion.RelMovLTool(50, 0, 0, 0, 0, 0)
    assert result is not None
    print(f"相对运动指令: {result}")
    
    # 测试关节运动
    result = robot.motion.MovJ([0, -30, -60, 0, 90, 0], CoordinateType.JOINT)
    assert result is not None
    print(f"关节运动指令: {result}")
    
    del robot
    print("运动指令生成测试通过！")


def test_coordinate_type_enum():
    """测试坐标系类型枚举"""
    assert CoordinateType.JOINT == 0
    assert CoordinateType.CARTESIAN == 1
    assert CoordinateType.USER == 1
    assert CoordinateType.TOOL == 2
    assert CoordinateType.CARTESIAN.name == 'CARTESIAN'
    assert CoordinateType.JOINT.name == 'JOINT'
    assert CoordinateType.USER.name == 'USER'
    assert CoordinateType.TOOL.name == 'TOOL'
    print("坐标系类型枚举测试通过！")


if __name__ == "__main__":
    print("运行运动控制模块测试...\n")
    
    test_motion_methods()
    print()
    
    test_motion_command_generation()
    print()
    
    test_coordinate_type_enum()
    print()
    
    print("=" * 50)
    print("运动控制模块所有测试通过！")
