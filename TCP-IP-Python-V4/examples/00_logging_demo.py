# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
日志功能演示示例

展示如何使用SDK的日志记录功能
"""

import sys
sys.path.insert(0, '..')

from dobot_sdk import DobotRobot, CoordinateType, get_logger, set_log_level, get_log_directory


def main():
    # 设置日志级别为DEBUG（可选，默认为INFO）
    # 可选级别: DEBUG, INFO, WARNING, ERROR
    set_log_level("DEBUG")
    
    # 获取日志记录器（可用于自定义日志输出）
    logger = get_logger()
    
    # 获取日志目录路径
    log_dir = get_log_directory()
    print(f"日志文件将保存到: {log_dir}")
    
    # 创建机器人对象（这里使用示例IP，实际使用时替换为真实IP）
    robot = DobotRobot("192.168.1.100")
    
    try:
        # 连接机器人（日志会自动记录连接过程）
        robot.Connect()
        
        # 请求控制模式
        robot.robot_control.RequestControl()
        
        # 清除报警
        robot.robot_control.ClearError()
        
        # 使能机器人（日志会记录API调用）
        robot.robot_control.EnableRobot()
        
        # 设置速度（日志会记录API调用）
        robot.robot_control.SpeedFactor(50)
        
        # 运动指令（日志会记录发送的命令和响应）
        start_pose = [400, 0, 300, 180, 0, 0]
        robot.motion.MovL(start_pose, CoordinateType.CARTESIAN)
        
        # 停止机器人
        robot.robot_control.DisableRobot()
        
    except Exception as e:
        logger.error(f"操作失败: {e}", exc_info=True)
    finally:
        # 断开连接（日志会记录断开过程）
        robot.Disconnect()


if __name__ == "__main__":
    main()
