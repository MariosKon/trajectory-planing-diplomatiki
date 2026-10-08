"""
传送带测试

演示传送带跟踪功能的使用
"""

import sys
import os

# 添加父目录到路径，以便导入dobot_sdk
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dobot_sdk import DobotRobot
from dobot_sdk import CoordinateType
import time


def main():
    # 修改为实际机器人IP
    ROBOT_IP = "192.168.5.1"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("传送带测试")
            print("=" * 50)
            
            # 初始化
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot(load=1.0)
            
            # 查询机器人模式
            mode_response = robot.robot_control.RobotMode()
            print(f"机器人模式: {mode_response}")
            
            while True:
                # 初始化传送带
                print("\n初始化传送带...")
                robot.plugins.CnvInit(1)
                
                # 移动至拍照/等待位
                print("移动至等待位...")
                robot.motion.MovJ(
                    [-29.3427, -386.0646, 248.1024, 180.0000, -0.0000, -154.3856],
                    CoordinateType.CARTESIAN,
                    user=0, tool=0
                )
                time.sleep(3)
                
                # 轮询检测传送带是否有物体到位
                print("\n等待物体进入抓取区域...")
                while True:
                    cnv_status = robot.plugins.GetCnvObject(0)
                    print(f"传送带状态: {cnv_status}")
                    
                    # 解析返回状态
                    try:
                        # 响应格式类似: "GetCnvObject,{status},GetCnvObject();"
                        start = cnv_status.find("{") + 1
                        end = cnv_status.find("}")
                        if start > 0 and end > start:
                            status_values = cnv_status[start:end].split(",")
                            if len(status_values) > 3:
                                object_detected = int(status_values[3])
                                if object_detected == 1:
                                    print("检测到物体!")
                                    break
                    except Exception as e:
                        print(f"解析状态失败: {e}")
                    
                    time.sleep(0.2)
                
                # 启动同步跟随
                print("\n启动传送带同步...")
                robot.plugins.StartSyncCnv()
                
                # 执行传送带跟随运动
                print("执行传送带跟随运动...")
                robot.plugins.CnvMovL([0, 0, 0, 0, 0, 153])
                time.sleep(2)
                
                # 触发吸盘或夹具 (DO6)
                print("触发吸盘...")
                robot.io.DO(6, 1)
                
                # 下降抓取
                print("下降抓取...")
                robot.plugins.CnvMovL([0, 0, -50, 0, 0, 153])
                time.sleep(3)
                
                # 停止同步
                print("停止传送带同步...")
                robot.plugins.StopSyncCnv()
                
                # 查询机器人模式
                mode_response = robot.robot_control.RobotMode()
                print(f"机器人模式: {mode_response}")
                
                # 停止运动
                robot.robot_control.Stop()
                
                # 移动至放置位置
                print("移动至放置位置...")
                robot.motion.MovL(
                    [212.5693, -395.0977, 209.9998, 179.9999, -0.0001, -154.3857],
                    CoordinateType.CARTESIAN,
                    user=0, tool=0
                )
                time.sleep(3)
                
                # 释放吸盘
                robot.io.DO(6, 0)
                
                # 返回待机位
                print("返回待机位...")
                robot.motion.MovJ(
                    [-29.3427, -386.0646, 248.1024, 180.0000, -0.0000, -154.3856],
                    CoordinateType.CARTESIAN,
                    user=0, tool=0
                )
                time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
