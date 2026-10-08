"""
伺服控制测试

演示ServoP动态跟随功能，生成圆周运动轨迹
"""

import sys
import os

# 添加父目录到路径，以便导入dobot_sdk
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import time
from dobot_sdk import DobotRobot
from dobot_sdk import CoordinateType


def parse_dobot_response(response_str: str) -> tuple:
    """解析Dobot返回的字符串格式数据，提取各部分内容

    格式示例: 'part1,{1,2,3},part3'

    Args:
        response_str: 待解析的字符串

    Returns:
        tuple: (前缀部分, 数字列表, 后缀部分)，解析失败返回None
    """
    first_comma_idx = response_str.find(',')
    if first_comma_idx == -1:
        return None

    prefix = response_str[:first_comma_idx]
    remaining = response_str[first_comma_idx + 1:]

    if not remaining.startswith('{'):
        return None

    brace_depth = 1
    i = 1
    while i < len(remaining) and brace_depth > 0:
        if remaining[i] == '{':
            brace_depth += 1
        elif remaining[i] == '}':
            brace_depth -= 1
        i += 1

    if brace_depth != 0:
        return None

    middle_with_braces = remaining[:i]
    suffix = remaining[i + 1:] if i < len(remaining) else ""

    numbers_str = middle_with_braces[1:-1]
    number_list = [float(x.strip()) for x in numbers_str.split(',')]

    return prefix, number_list, suffix


def generate_circular_trajectory(radius: float, num_points: int) -> list:
    """生成圆周运动轨迹点

    Args:
        radius: 圆周半径(mm)
        num_points: 轨迹点数

    Returns:
        list: 轨迹点列表，每个点为[x, y, z, rx, ry, rz]
    """
    trajectory_points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        trajectory_points.append([x, y, 0, 0, 0, 0])
    return trajectory_points

def generate_circle_smooth(radius=50, total_points=300):
    points = []
    for i in range(total_points):
        s = i / (total_points - 1)
        angle = 2 * math.pi * (0.5 - 0.5 * math.cos(math.pi * s))
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append([x, y, 0, 0, 0, 0])
    return points

def execute_trajectory_at_frequency(robot, trajectory_points, frequency_hz: float):
    """以指定频率执行轨迹点序列

    Args:
        robot: DobotRobot实例
        trajectory_points: 轨迹点列表
        frequency_hz: 执行频率(Hz)
    """
    start_time = time.time()
    interval = 1.0 / frequency_hz

    for i, target_point in enumerate(trajectory_points):
        expected_time = start_time + (i + 1) * interval
        cycle_start = time.time()

        # 使用新SDK的ServoP接口
        robot.motion.ServoP(target_point)

        cycle_duration = time.time() - cycle_start
        current_time = time.time()
        delay_needed = expected_time - current_time

        if delay_needed > 0:
            time.sleep(delay_needed)
        else:
            print(f"周期 {i + 1} 超时 {-delay_needed:.3f} 秒")

def wait_for_robot_ready(robot, target_state=5.0, polling_interval=0.1):
    """等待机器人进入就绪状态

    Args:
        robot: DobotRobot实例
        target_state: 目标状态值
        polling_interval: 轮询间隔(秒)
    """
    while True:
        status_response = robot.robot_control.RobotMode()
        parsed = parse_dobot_response(status_response)

        if parsed is None:
            print("机器人状态解析失败")
            time.sleep(polling_interval)
            continue

        _, state_data, _ = parsed

        if state_data and state_data[0] == target_state:
            print(f"机器人已就绪，状态: {state_data}")
            break

        time.sleep(polling_interval)


def main():
    # 修改为实际机器人IP
    ROBOT_IP = "192.168.5.1"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("伺服控制测试 - 圆周轨迹跟随")
            print("=" * 50)
            
            # 初始化
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot(load=1.0)
            
            # 激活用户坐标系0
            robot.robot_control.User(0)
            
            # 获取当前位置
            pose_response = robot.robot_control.GetPose()
            parsed_pose = parse_dobot_response(pose_response)

            if parsed_pose is None:
                print("错误: 位置信息解析失败")
                return

            _, current_position, _ = parsed_pose
            print(f"当前位置: {current_position}")

            # 设置用户坐标系1（以当前位置为原点）
            set_user_result = robot.robot_control.SetUser(1, current_position)
            print(f"设置用户坐标系结果: {set_user_result}")

            # 切换到用户坐标系1
            robot.robot_control.User(1)

            # 移动到轨迹起始点（用户坐标系中的相对位置）
            start_point = [50, 0, 0, 0, 0, 0]
            print(f"\n移动到轨迹起始点: {start_point}")
            robot.motion.MovL(start_point, CoordinateType.CARTESIAN)
            time.sleep(3)

            # 等待机器人就绪
            wait_for_robot_ready(robot)

            # 生成圆周轨迹
            # trajectory_points = generate_circular_trajectory(radius=50, num_points=300)
            trajectory_points = generate_circle_smooth(radius=50, total_points=300)
            print(f"\n生成 {len(trajectory_points)} 个轨迹点")

            # 执行轨迹控制
            print("开始执行轨迹控制...")
            execute_trajectory_at_frequency(robot, trajectory_points, frequency_hz=33.0)

            print("\n轨迹执行完成")

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
