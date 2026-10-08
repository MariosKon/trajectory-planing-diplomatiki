"""
机器人控制模块测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot


def test_robot_control_methods():
    """测试机器人控制方法"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试请求控制方法
    assert hasattr(robot.robot_control, 'RequestControl')
    assert hasattr(robot.robot_control, 'EnableRobot')
    print("控制请求方法存在")
    
    # 测试使能控制方法
    assert hasattr(robot.robot_control, 'EnableRobot')
    assert hasattr(robot.robot_control, 'DisableRobot')
    print("使能控制方法存在")
    
    # 测试错误处理方法
    assert hasattr(robot.robot_control, 'ClearError')
    assert hasattr(robot.robot_control, 'GetErrorID')
    print("错误处理方法存在")
    
    # 测试状态查询方法
    assert hasattr(robot.robot_control, 'GetPose')
    assert hasattr(robot.robot_control, 'GetAngle')
    assert hasattr(robot.robot_control, 'RobotMode')
    print("状态查询方法存在")
    
    # 测试速度设置方法
    assert hasattr(robot.robot_control, 'SpeedFactor')
    print("速度设置方法存在")
    
    # 测试坐标系计算方法
    assert hasattr(robot.robot_control, 'CalcUser')
    assert hasattr(robot.robot_control, 'CalcTool')
    print("坐标系计算方法存在")
    
    # 测试碰撞检测方法
    assert hasattr(robot.robot_control, 'SetCollisionLevel')
    print("碰撞检测方法存在")
    
    del robot
    print("机器人控制方法测试通过！")


def test_robot_control_parameter_validation():
    """测试机器人控制参数验证"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试enable_robot方法
    result = robot.robot_control.EnableRobot(load=1.0)
    assert result is not None
    print(f"enable_robot(load=1.0): {result}")
    
    # 测试speed_factor方法
    result = robot.robot_control.SpeedFactor(50)
    assert result is not None
    print(f"SpeedFactor(50): {result}")
    
    # 测试set_collision_level方法（参数范围0-5）
    result = robot.robot_control.SetCollisionLevel(3)
    assert result is not None
    print(f"SetCollisionLevel(3): {result}")
    
    # 测试calc_user方法
    result = robot.robot_control.CalcUser(0, 1, [0, 0, 0, 0, 0, 0])
    assert result is not None
    print(f"CalcUser(0, 1, [0,0,0,0,0,0]): {result}")
    
    del robot
    print("机器人控制参数验证测试通过！")


if __name__ == "__main__":
    print("运行机器人控制模块测试...\n")
    
    test_robot_control_methods()
    print()
    
    test_robot_control_parameter_validation()
    print()
    
    print("=" * 50)
    print("机器人控制模块所有测试通过！")
