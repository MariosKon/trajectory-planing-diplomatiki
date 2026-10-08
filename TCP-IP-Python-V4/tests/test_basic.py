"""
基础功能测试
"""

import sys
import os

# 添加SDK路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot
from dobot_sdk.models import RobotStatus, RobotMode
from dobot_sdk import CoordinateType


def test_import():
    """测试导入"""
    print("导入成功")
    assert DobotRobot is not None
    print("DobotRobot类可用")
    assert CoordinateType is not None
    print("CoordinateType枚举可用")


def test_models():
    """测试数据模型"""
    # 测试RobotStatus
    status = RobotStatus()
    assert status.robot_mode == RobotMode.INIT
    assert status.speed_scaling == 0.0
    print("RobotStatus模型正常")
    
    # 测试RobotMode枚举
    assert RobotMode.ENABLE == 5
    assert RobotMode.ERROR == 9
    print("RobotMode枚举正常")


def test_robot_creation():
    """测试机器人对象创建"""
    robot = DobotRobot("192.168.1.100")
    assert robot.ip == "192.168.1.100"
    
    # 检查实际存在的模块
    assert robot.motion is not None
    print("motion模块可用")
    
    assert robot.io is not None
    print("io模块可用")
    
    assert robot.communication is not None
    print("communication模块可用")
    
    assert robot.plugins is not None
    print("plugins模块可用")
    
    assert robot.robot_control is not None
    print("robot_control模块可用")
    
    print("机器人对象创建成功")
    
    # 清理
    del robot


def test_coordinate_type():
    """测试CoordinateType枚举"""
    assert CoordinateType.JOINT == 0
    assert CoordinateType.CARTESIAN == 1
    assert CoordinateType.USER == 1
    assert CoordinateType.TOOL == 2
    print("CoordinateType枚举值正确")


if __name__ == "__main__":
    print("运行基础测试...\n")
    
    test_import()
    print()
    
    test_models()
    print()
    
    test_robot_creation()
    print()
    
    test_coordinate_type()
    print()
    
    print("=" * 50)
    print("所有测试通过！")
