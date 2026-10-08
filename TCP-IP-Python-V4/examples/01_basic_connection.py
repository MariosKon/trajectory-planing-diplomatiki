"""
示例1: 基础连接和使能

演示如何连接机器人、使能、设置参数并安全关闭
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dobot_sdk import DobotRobot
import time


def main():
    # 机器人IP地址（根据实际情况修改）
    ROBOT_IP = "192.168.5.1"
    
    # 使用上下文管理器（推荐方式）
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("1. 连接成功")
            print("=" * 50)
            
            # 请求TCP控制模式
            print("请求TCP控制模式...")
            response = robot.robot_control.RequestControl()
            print(f"响应: {response}")
            
            # 清除报警（如果有）
            print("清除报警...")
            robot.robot_control.ClearError()
            
            # 使能机器人（设置1kg负载）
            print("使能机器人...")
            response = robot.robot_control.EnableRobot(load=1.0)
            print(f"响应: {response}")
            
            # 设置全局速度比例
            speed = 50
            print(f"设置全局速度为 {speed}%...")
            robot.robot_control.SpeedFactor(speed)
            
            # 获取机器人状态
            print("\n获取机器人状态...")
            mode = robot.robot_control.RobotMode()
            print(f"机器人模式: {mode}")
            
            # 等待2秒
            print(f"\n等待 {2} 秒...")
            time.sleep(2)
            
            # 下使能机器人
            print("\n下使能机器人...")
            response = robot.robot_control.DisableRobot()
            print(f"响应: {response}")
            
            print("\n" + "=" * 50)
            print("✅ 基础连接示例完成")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
