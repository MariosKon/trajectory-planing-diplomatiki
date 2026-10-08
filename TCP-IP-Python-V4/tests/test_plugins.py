"""
插件模块测试（力控和传送带）
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dobot_sdk import DobotRobot


def test_plugins_methods():
    """测试插件模块方法"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试力控方法
    assert hasattr(robot.plugins, 'FCForceMode')
    assert hasattr(robot.plugins, 'FCSetDeviation')
    assert hasattr(robot.plugins, 'FCSetForceLimit')
    assert hasattr(robot.plugins, 'FCSetMass')
    assert hasattr(robot.plugins, 'FCSetStiffness')
    assert hasattr(robot.plugins, 'FCSetDamping')
    assert hasattr(robot.plugins, 'FCOff')
    assert hasattr(robot.plugins, 'FCSetForce')
    assert hasattr(robot.plugins, 'SetFCCollision')
    assert hasattr(robot.plugins, 'FCCollisionSwitch')
    print("力控方法存在")
    
    # 测试传送带方法
    assert hasattr(robot.plugins, 'CnvInit')
    assert hasattr(robot.plugins, 'GetCnvObject')
    assert hasattr(robot.plugins, 'StartSyncCnv')
    assert hasattr(robot.plugins, 'CnvMovL')
    assert hasattr(robot.plugins, 'CnvMovC')
    assert hasattr(robot.plugins, 'StopSyncCnv')
    assert hasattr(robot.plugins, 'SetCnvPointOffset')
    assert hasattr(robot.plugins, 'SetCnvTimeCompensation')
    print("传送带方法存在")
    
    del robot
    print("插件模块方法测试通过！")


def test_plugins_command_generation():
    """测试插件指令生成"""
    robot = DobotRobot("192.168.1.100")
    
    # 测试力控模式设置
    result = robot.plugins.FCForceMode([1,1,1,0,0,0], [0,0,0,0,0,0])
    assert result is not None
    print(f"FCForceMode([1,1,1,0,0,0], [0,0,0,0,0,0]): {result}")
    
    # 测试力关闭
    result = robot.plugins.FCOff()
    assert result is not None
    print(f"FCOff(): {result}")
    
    # 测试传送带初始化
    result = robot.plugins.CnvInit(1)
    assert result is not None
    print(f"CnvInit(1): {result}")
    
    del robot
    print("插件指令生成测试通过！")


if __name__ == "__main__":
    print("运行插件模块测试...\n")
    
    test_plugins_methods()
    print()
    
    test_plugins_command_generation()
    print()
    
    print("=" * 50)
    print("插件模块所有测试通过！")
