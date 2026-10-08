"""
通信模块测试（Modbus）
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot


def test_communication_methods():
    """测试通信模块方法"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试Modbus方法
    assert hasattr(robot.communication, 'ModbusCreate')
    assert hasattr(robot.communication, 'ModbusRTUCreate')
    assert hasattr(robot.communication, 'ModbusClose')
    print("Modbus创建/关闭方法存在")
    
    # 测试输入寄存器方法
    assert hasattr(robot.communication, 'GetInBits')
    assert hasattr(robot.communication, 'GetInRegs')
    print("输入寄存器方法存在")
    
    # 测试线圈方法
    assert hasattr(robot.communication, 'GetCoils')
    assert hasattr(robot.communication, 'SetCoils')
    print("线圈方法存在")
    
    # 测试保持寄存器方法
    assert hasattr(robot.communication, 'GetHoldRegs')
    assert hasattr(robot.communication, 'SetHoldRegs')
    print("保持寄存器方法存在")
    
    del robot
    print("通信模块方法测试通过！")


def test_communication_command_generation():
    """测试通信指令生成"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试Modbus创建
    result = robot.communication.ModbusCreate("192.168.1.101", 502, 1)
    assert result is not None
    print(f"ModbusCreate('192.168.1.101', 502, 1): {result}")
    
    # 测试读取输入寄存器
    result = robot.communication.GetInRegs(1, 0, 10)
    assert result is not None
    print(f"GetInRegs(1, 0, 10): {result}")
    
    del robot
    print("通信指令生成测试通过！")


if __name__ == "__main__":
    print("运行通信模块测试...\n")
    
    test_communication_methods()
    print()
    
    test_communication_command_generation()
    print()
    
    print("=" * 50)
    print("通信模块所有测试通过！")
