"""
示例5: 坐标系设置

演示用户坐标系和工具坐标系的设置与使用
"""

from dobot_sdk import DobotRobot
from dobot_sdk import CoordinateType
import time


def main():
    ROBOT_IP = "192.168.1.100"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("5. 坐标系设置示例")
            print("=" * 50)
            
            # 初始化
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot(load=1.0)
            robot.robot_control.SpeedFactor(30)
            
            # ========== 设置用户坐标系 ==========
            print("\n--- 设置用户坐标系 ---")
            
            # 创建用户坐标系1（相对于世界坐标系偏移）
            user_pose = [100, 50, 0, 0, 0, 0]  # X偏移100, Y偏移50
            print(f"设置用户坐标系1: {user_pose}")
            robot.robot_control.SetUser(1, user_pose)
            
            # 切换到用户坐标系1
            print("切换到用户坐标系1...")
            robot.robot_control.User(1)
            
            # 在用户坐标系下运动
            print("在用户坐标系1下移动到 (100, 0, 300)...")
            pose_in_user = [100, 0, 300, 180, 0, 0]
            robot.motion.MovJ(pose_in_user, CoordinateType.CARTESIAN)
            time.sleep(3)
            
            # 切换回世界坐标系
            print("切换回世界坐标系...")
            robot.robot_control.User(0)
            
            # ========== 设置工具坐标系 ==========
            print("\n--- 设置工具坐标系 ---")
            
            # 创建工具坐标系1（末端工具长度100mm）
            tool_pose = [0, 0, 100, 0, 0, 0]  # Z方向偏移100mm
            print(f"设置工具坐标系1: {tool_pose}")
            robot.robot_control.SetTool(1, tool_pose)
            
            # 切换到工具坐标系1
            print("切换到工具坐标系1...")
            robot.robot_control.Tool(1)
            
            # 在工具坐标系下运动
            print("在工具坐标系1下相对移动...")
            pose_in_tool = [400, 0, 300, 180, 0, 0]
            robot.motion.MovJ(pose_in_tool, CoordinateType.CARTESIAN)
            time.sleep(3)
            
            # 切换回默认工具坐标系
            print("切换回默认工具坐标系...")
            robot.robot_control.Tool(0)
            
            # ========== 设置负载参数 ==========
            print("\n--- 设置负载参数 ---")
            print("设置负载: 重量2kg, 重心(0, 0, 100)...")
            robot.robot_control.SetPayload(2.0, 0, 0, 100)
            
            # ========== 计算坐标系（三点法） ==========
            print("\n--- 计算坐标系演示 ---")
            print("注意: 实际使用CalcUser/CalcTool需要先示教点位")
            print("这里仅演示API调用方式")
            
            # 计算用户坐标系示例（需要先示教3个点）
            # robot.robot_control.CalcUser(1)  # 需要示教
            
            # 计算工具坐标系示例（需要先示教3个点）
            # robot.robot_control.CalcTool(1)  # 需要示教
            
            # ========== 获取当前坐标系信息 ==========
            print("\n--- 获取坐标系信息 ---")
            pose = robot.robot_control.GetPose()
            print(f"当前位姿: {pose}")
            
            # 返回安全位置
            print("\n返回安全位置...")
            safe_pose = [0, -30, -60, 0, 90, 0]
            robot.motion.MovJ(safe_pose, CoordinateType.JOINT)
            time.sleep(3)
            
            # 下使能
            robot.robot_control.DisableRobot()
            
            print("\n" + "=" * 50)
            print("✅ 坐标系设置示例完成")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
