"""
示例3: 错误码监控和状态查询

演示如何获取机器人状态、错误码等信息
"""

from dobot_sdk import DobotRobot
import time


def parse_error_response(response):
    """解析错误码响应"""
    # 响应格式: "ErrorID,{[id,...,id]},GetErrorID();"
    if "ErrorID" in response:
        start = response.find("{") + 1
        end = response.find("}")
        if start > 0 and end > start:
            error_codes_str = response[start:end]
            # 去除内部的方括号
            error_codes_str = error_codes_str.strip("[]")
            if error_codes_str.strip():
                return [int(x.strip()) for x in error_codes_str.split(",") if x.strip()]
    return []


def main():
    ROBOT_IP = "192.168.1.100"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("3. 错误码监控和状态查询")
            print("=" * 50)
            
            # ========== 获取错误码 ==========
            print("\n--- 获取错误码 ---")
            response = robot.robot_control.GetErrorID()
            print(f"原始响应: {response}")
            
            error_codes = parse_error_response(response)
            if error_codes:
                print(f"\n发现 {len(error_codes)} 个错误码:")
                for code in error_codes:
                    print(f"  - 错误码: {code}")
                    print(f"    请查阅官方文档获取详细说明")
            else:
                print("✅ 无错误码")
            
            # ========== 获取机器人模式 ==========
            print("\n--- 获取机器人模式 ---")
            mode = robot.robot_control.RobotMode()
            print(f"机器人模式: {mode}")
            
            # ========== 获取当前位姿 ==========
            print("\n--- 获取当前笛卡尔坐标 ---")
            pose = robot.robot_control.GetPose()
            print(f"当前位姿: {pose}")
            
            # ========== 获取关节角度 ==========
            print("\n--- 获取当前关节角度 ---")
            angles = robot.robot_control.GetAngle()
            print(f"关节角度: {angles}")
            
            # ========== 清除报警演示 ==========
            print("\n--- 清除报警演示 ---")
            # 注意：只有在有错误时才需要清除
            if error_codes:
                print("清除报警...")
                robot.robot_control.ClearError()
                # 再次检查
                response = robot.robot_control.GetErrorID()
                error_codes = parse_error_response(response)
                if not error_codes:
                    print("✅ 报警已清除")
            
            # ========== 运动学计算演示 ==========
            print("\n--- 运动学计算 ---")
            # 正解：关节角度 -> 笛卡尔坐标
            print("正解运算 (关节->笛卡尔)...")
            joints = [0, 0, 0, 0, 90, 0]
            forward_result = robot.robot_control.PositiveKin(joints)
            print(f"输入关节: {joints}")
            print(f"正解结果: {forward_result}")
            
            # 可达性检查
            print("\n--- 直线运动可达性检查 (CheckOddMovL) ---")
            # CheckOddMovL仅支持关节变量，需要提供起点和终点关节角度
            joints_start = [0, 0, 90, 0, 0, 0]
            joints_end = [90, 30, 0, 0, 0, 0]
            result = robot.robot_control.CheckOddMovL(joints_start, joints_end)
            print(f"检查直线运动: {joints_start} -> {joints_end}")
            print(f"结果: {result}")
            
            print("\n--- 圆弧运动可达性检查 (CheckOddMovC) ---")
            # CheckOddMovC仅支持关节变量，需要提供起点、中间点和终点关节角度
            joints_via = [60, 30, 0, 0, 0, 0]
            result = robot.robot_control.CheckOddMovC(joints_start, joints_via, joints_end)
            print(f"检查圆弧运动: {joints_start} -> {joints_via} -> {joints_end}")
            print(f"结果: {result}")
            
            print("\n" + "=" * 50)
            print("✅ 错误监控示例完成")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
