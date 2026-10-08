"""
示例2: 运动控制

演示各种运动指令的使用方法
"""

from dobot_sdk import DobotRobot
from dobot_sdk import CoordinateType
import time

def main():
    ROBOT_IP = "120.79.211.106"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("2. 运动控制示例")
            print("=" * 50)
            
            # 初始化
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot(load=1.0)
            robot.robot_control.SpeedFactor(30)
            
            # 启动状态监控
            robot.StartFeedbackMonitor()
            time.sleep(1)
            
            # ========== 关节运动 (MovJ) ==========
            print("\n--- 关节运动 (MovJ) ---")
            print("移动到安全位置...")
            safe_pose = [0, -30, -60, 0, 90, 0]
            robot.motion.MovJ(safe_pose, CoordinateType.JOINT)
            time.sleep(3)
            
            # ========== 笛卡尔运动 (MovJ) ==========
            print("\n--- 笛卡尔空间关节运动 (MovJ) ---")
            pose_a = [400, 0, 300, 180, 0, 0]
            print(f"移动到点位A: {pose_a}")
            robot.motion.MovJ(pose_a, CoordinateType.CARTESIAN)
            time.sleep(3)
            
            # ========== 直线运动 (MovL) ==========
            print("\n--- 直线运动 (MovL) ---")
            pose_b = [400, 100, 300, 180, 0, 0]
            print(f"直线移动到点位B: {pose_b}")
            robot.motion.MovL(pose_b, CoordinateType.CARTESIAN)
            time.sleep(3)
            
            # ========== 圆弧运动 (Arc) ==========
            print("\n--- 圆弧运动 (Arc) ---")
            pose_via = [450, 150, 300, 180, 0, 0]
            pose_c = [500, 100, 300, 180, 0, 0]
            print(f"圆弧运动: B -> Via -> C")
            robot.motion.Arc(pose_via, pose_c, CoordinateType.CARTESIAN)
            time.sleep(3)
            
            # ========== 整圆运动 (Circle) ==========
            print("\n--- 整圆运动 (Circle) ---")
            print(f"整圆运动: C -> Via -> B")
            robot.motion.Circle(pose_via, pose_b, count=1, coord_type=CoordinateType.CARTESIAN)
            time.sleep(4)
            
            # ========== 相对运动 ==========
            print("\n--- 相对运动 (RelMovLTool) ---")
            offset = [0, -50, 0, 0, 0, 0]
            print(f"相对偏移: {offset}")
            robot.motion.RelMovLTool(offset[0], offset[1], offset[2], offset[3], offset[4], offset[5])
            time.sleep(2)
            
            # ========== 获取当前状态 ==========
            print("\n--- 获取当前状态 ---")
            status = robot.GetStatus()
            if status:
                print(f"当前速度比例: {status.speed_scaling:.1f}%")
                print(f"当前位姿:")
                print(f"  X: {status.tool_vector_actual.x:.2f}")
                print(f"  Y: {status.tool_vector_actual.y:.2f}")
                print(f"  Z: {status.tool_vector_actual.z:.2f}")
            
            # 返回安全位置
            print("\n返回安全位置...")
            robot.motion.MovJ(safe_pose, CoordinateType.JOINT)
            time.sleep(3)
            
            # 停止监控
            robot.StopFeedbackMonitor()
            robot.robot_control.DisableRobot()
            
            print("\n" + "=" * 50)
            print("✅ 运动控制示例完成")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
