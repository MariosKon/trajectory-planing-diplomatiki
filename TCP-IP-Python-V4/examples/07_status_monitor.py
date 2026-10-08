# -*- coding: utf-8 -*-
"""
示例7: 完整状态监控

展示从Feedback数据包解析的所有字段
"""

import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dobot_sdk import DobotRobot, set_log_level


def print_status(status):
    """
    打印机器人完整状态信息
    
    Args:
        status: RobotStatus 对象
    """
    # 重点监听 RunningStatus
    running_status = status.running_status
    
    # RunningStatus 值含义（根据协议文档）
    # 0: 空闲
    # 1028: 运动中
    # 其他值根据实际情况定义
    
    status_text = "未知"
    status_icon = ""
    if running_status == 0:
        status_text = "空闲"
        status_icon = "[OK]"
    elif running_status == 1028:
        status_text = "运动中"
        status_icon = "[RUN]"
    else:
        status_text = f"状态码: {running_status}"
        status_icon = "[WARN]"
    
    print(f"\n{'='*60}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 运行状态
    print(f"\n【运行状态】")
    print(f"  RunningStatus: {status_icon} {status_text}")
    print(f"  机器人模式: {status.robot_mode.name}")
    print(f"  使能状态: {'已使能' if status.enable_status else '未使能'}")
    print(f"  抱闸状态: {'已松开' if status.brake_status else '已抱死'}")
    print(f"  错误状态: {'有错误' if status.error_status else '正常'}")
    print(f"  速度比例: {status.speed_scaling:.1f}%")
    print(f"  拖拽状态: {status.drag_status} (0:不在拖拽, 1:关节拖拽, 2:力控拖拽)")
    print(f"  机器人型号: {status.robot_type}")
    
    # 笛卡尔坐标
    print(f"\n【笛卡尔坐标】")
    print(f"  X: {status.tool_vector_actual.x:.2f} mm")
    print(f"  Y: {status.tool_vector_actual.y:.2f} mm")
    print(f"  Z: {status.tool_vector_actual.z:.2f} mm")
    print(f"  Rx: {status.tool_vector_actual.rx:.2f} °")
    print(f"  Ry: {status.tool_vector_actual.ry:.2f} °")
    print(f"  Rz: {status.tool_vector_actual.rz:.2f} °")
    
    # TCP速度
    print(f"\n【TCP速度】")
    print(f"  Vx: {status.tcp_speed_actual.x:.2f} mm/s")
    print(f"  Vy: {status.tcp_speed_actual.y:.2f} mm/s")
    print(f"  Vz: {status.tcp_speed_actual.z:.2f} mm/s")
    
    # 关节角度
    print(f"\n【关节角度】")
    joint_names = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6']
    for i, (name, angle) in enumerate(zip(joint_names, status.joint_state.q_actual)):
        print(f"  {name}: {angle:.2f} °")
    
    # 关节速度
    print(f"\n【关节速度】")
    for i, (name, speed) in enumerate(zip(joint_names, status.joint_state.qd_actual)):
        print(f"  {name}: {speed:.2f} °/s")
    
    # 电气信息
    print(f"\n【电气信息】")
    print(f"  电压: {status.voltage:.2f} V")
    print(f"  电流: {status.current:.2f} A")
    print(f"  负载: {status.load:.2f} kg")
    print(f"  负载中心: ({status.load_center_x:.1f}, {status.load_center_y:.1f}, {status.load_center_z:.1f}) mm")
    
    # 电机温度
    print(f"\n【电机温度】")
    for i, (name, temp) in enumerate(zip(joint_names, status.joint_state.temperatures)):
        print(f"  {name}: {temp:.1f} °C")
    
    # IO状态
    print(f"\n【IO状态】")
    print(f"  数字输入: {bin(status.digital_inputs)}")
    print(f"  数字输出: {bin(status.digital_outputs)}")
    print(f"  安全IO输入: {status.safety_io_in}")
    print(f"  安全IO输出: {status.safety_io_out}")
    
    # 速度/加速度比例
    print(f"\n【速度/加速度比例】")
    print(f"  关节速度: {status.velocity_ratio}%")
    print(f"  关节加速度: {status.acceleration_ratio}%")
    print(f"  笛卡尔位置速度: {status.xyz_velocity_ratio}%")
    print(f"  笛卡尔姿态速度: {status.r_velocity_ratio}%")
    print(f"  笛卡尔位置加速度: {status.xyz_acceleration_ratio}%")
    print(f"  笛卡尔姿态加速度: {status.r_acceleration_ratio}%")
    
    # 坐标系
    print(f"\n【坐标系】")
    print(f"  用户坐标系: {status.user_coordinate}")
    print(f"  工具坐标系: {status.tool_coordinate}")
    
    # 四元数
    print(f"\n【四元数】")
    print(f"  目标: [{status.target_quaternion.qw:.4f}, {status.target_quaternion.qx:.4f}, {status.target_quaternion.qy:.4f}, {status.target_quaternion.qz:.4f}]")
    print(f"  实际: [{status.actual_quaternion.qw:.4f}, {status.actual_quaternion.qx:.4f}, {status.actual_quaternion.qy:.4f}, {status.actual_quaternion.qz:.4f}]")
    
    # 安全状态
    print(f"\n【安全状态】")
    print(f"  安全状态: {status.get_safety_state_desc()}")
    print(f"  碰撞状态: {status.collision_state}")
    print(f"  小臂接近: {status.arm_approach_state}")
    print(f"  J4接近: {status.j4_approach_state}")
    print(f"  J5接近: {status.j5_approach_state}")
    print(f"  J6接近: {status.j6_approach_state}")
    
    # 六维力传感器
    print(f"\n【六维力传感器】")
    force_status = {0: '离线', 1: '在线', 2: '异常'}.get(status.six_force_online, '未知')
    print(f"  在线状态: {force_status}")
    if status.six_force_online == 1:
        print(f"  原始值: {[f'{v:.2f}' for v in status.six_force_value]}")
    
    # 末端按钮信号
    print(f"\n【末端按钮信号】")
    print(f"  拖拽按钮: {status.drag_button_signal}")
    print(f"  使能按钮: {status.enable_button_signal}")
    print(f"  录制按钮: {status.record_button_signal}")
    print(f"  复现按钮: {status.reappear_button_signal}")
    print(f"  夹爪按钮: {status.jaw_button_signal}")
    
    # 指令信息
    print(f"\n【指令信息】")
    print(f"  当前指令ID: {status.current_command_id}")
    print(f"  运行时间: {status.run_time // 1000} 秒")
    print(f"  队列运行: {status.run_queued_cmd}")
    print(f"  队列暂停: {status.pause_cmd_flag}")
    
    # 模式
    print(f"\n【模式】")
    print(f"  手动/自动: {status.auto_manual_mode}")
    print(f"  U盘导出: {status.export_status}")
    
    # 抖动检测
    print(f"\n【抖动检测】")
    print(f"  Z轴抖动位移: {status.vibration_dis_z:.4f} mm")
    
    print(f"\n{'='*60}")
    print("按 Ctrl+C 停止监听")


def main():
    # 设置日志级别（可选）
    set_log_level("INFO")
    
    # 机器人IP地址
    ROBOT_IP = "192.168.1.100"
    
    print(f"正在连接机器人 {ROBOT_IP}...")
    
    # 创建机器人对象，设置超时时间
    robot = DobotRobot(
        ROBOT_IP,
        connect_timeout=10.0,
        receive_timeout=15.0
    )
    
    try:
        # 连接机器人
        robot.Connect()
        print("连接成功！")
        
        # 请求控制权
        robot.robot_control.RequestControl()
        
        # 清除错误
        robot.robot_control.ClearError()
        
        # 启动反馈监控
        robot.StartFeedbackMonitor(callback=print_status)
        
        print("\n开始监听机器人状态...")
        print("按 Ctrl+C 停止监听\n")
        
        # 持续监听
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n用户停止监听")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止监控并断开连接
        robot.StopFeedbackMonitor()
        robot.Disconnect()
        print("已断开连接")


if __name__ == "__main__":
    main()