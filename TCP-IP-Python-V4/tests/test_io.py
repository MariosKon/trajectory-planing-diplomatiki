"""
IO模块测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot


def test_io_methods():
    """测试IO模块方法"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试数字输出方法
    assert hasattr(robot.io, 'DO')
    assert hasattr(robot.io, 'DOInstant')
    print("数字输出方法存在")
    
    # 测试数字输入方法
    assert hasattr(robot.io, 'DI')
    print("数字输入方法存在")
    
    # 测试数字输出组方法
    assert hasattr(robot.io, 'DOGroup')
    assert hasattr(robot.io, 'DOGroupDEC')
    assert hasattr(robot.io, 'GetDOGroup')
    print("数字输出组方法存在")
    
    # 测试数字输入组方法
    assert hasattr(robot.io, 'DIGroup')
    assert hasattr(robot.io, 'DIGroupDEC')
    print("数字输入组方法存在")
    
    # 测试模拟输出方法
    assert hasattr(robot.io, 'AO')
    assert hasattr(robot.io, 'AOInstant')
    assert hasattr(robot.io, 'GetAO')
    assert hasattr(robot.io, 'AI')
    print("模拟输入输出方法存在")
    
    # 测试工具IO方法
    assert hasattr(robot.io, 'ToolDO')
    assert hasattr(robot.io, 'ToolDOInstant')
    assert hasattr(robot.io, 'ToolDI')
    assert hasattr(robot.io, 'ToolAI')
    print("工具IO方法存在")
    
    # 测试工具设置方法
    assert hasattr(robot.io, 'SetToolPower')
    assert hasattr(robot.io, 'SetToolMode')
    assert hasattr(robot.io, 'SetTool485')
    print("工具设置方法存在")
    
    del robot
    print("IO模块测试通过！")


def test_io_parameter_validation():
    """测试IO参数验证"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试 DO 方法
    result = robot.io.DO(1, 1)
    assert result is not None
    print(f"DO(1, 1): {result}")
    
    # 测试 DO 方法（关闭）
    result = robot.io.DO(1, 0)
    assert result is not None
    print(f"DO(1, 0): {result}")
    
    # 测试 DI 方法
    result = robot.io.DI(1)
    assert result is not None
    print(f"DI(1): {result}")
    
    del robot
    print("IO参数验证测试通过！")


if __name__ == "__main__":
    print("运行IO模块测试...\n")
    
    test_io_methods()
    print()
    
    test_io_parameter_validation()
    print()
    
    print("=" * 50)
    print("IO模块所有测试通过！")
