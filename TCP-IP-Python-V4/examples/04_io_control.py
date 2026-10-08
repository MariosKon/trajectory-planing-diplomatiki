"""
示例4: IO控制

演示数字IO、模拟IO和末端IO的使用方法
"""

from dobot_sdk import DobotRobot
import time


def main():
    ROBOT_IP = "192.168.1.100"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("4. IO控制示例")
            print("=" * 50)
            
            # 初始化
            robot.robot_control.RequestControl()
            robot.robot_control.ClearError()
            robot.robot_control.EnableRobot(load=1.0)
            
            # ========== 数字输出控制 ==========
            print("\n--- 数字输出控制 (DO) ---")
            
            # 方式1: 使用 DO(index, status)
            print("打开DO1...")
            robot.io.DO(1, 1)
            time.sleep(1)
            
            print("关闭DO1...")
            robot.io.DO(1, 0)
            time.sleep(1)
            
            # 方式2: 使用 do（队列指令）
            print("设置DO2为ON...")
            robot.io.DO(2, 1)
            time.sleep(1)
            
            print("设置DO2为OFF...")
            robot.io.DO(2, 0)
            time.sleep(1)
            
            # 方式3: 使用 DOInstant（立即指令）
            print("使用立即指令设置DO3...")
            robot.io.DOInstant(3, 1)
            time.sleep(1)
            robot.io.DOInstant(3, 0)
            time.sleep(1)
            
            # ========== 数字输入读取 ==========
            print("\n--- 数字输入读取 (DI) ---")
            for i in range(1, 5):
                di_status = robot.io.DI(i)
                print(f"DI{i} 状态: {di_status}")
            
            # ========== 数字输出状态读取 ==========
            print("\n--- 数字输出状态读取 (DO) ---")
            for i in range(1, 4):
                do_status = robot.io.GetDO(i)
                print(f"DO{i} 状态: {do_status}")
            
            # ========== 模拟输出控制 ==========
            print("\n--- 模拟输出控制 (AO) ---")
            print("设置AO1为25%...")
            robot.io.AO(1, 25)
            time.sleep(2)
            
            print("设置AO1为75%...")
            robot.io.AO(1, 75)
            time.sleep(2)
            
            print("设置AO1为0%...")
            robot.io.AO(1, 0)
            time.sleep(1)
            
            # ========== 模拟输入读取 ==========
            print("\n--- 模拟输入读取 (AI) ---")
            for i in range(1, 3):
                ai_value = robot.io.AI(i)
                print(f"AI{i} 值: {ai_value}")
            
            # ========== 末端IO控制 ==========
            print("\n--- 末端IO控制 (Tool IO) ---")
            
            # 设置末端DO
            print("设置末端DO1为ON...")
            robot.io.ToolDO(1, 1)
            time.sleep(1)
            
            print("设置末端DO1为OFF...")
            robot.io.ToolDO(1, 0)
            time.sleep(1)
            
            # 读取末端DI
            print("读取末端DI...")
            tool_di_status = robot.io.ToolDI(1)
            print(f"末端DI 状态: {tool_di_status}")
            
            # 设置末端工具供电（开启）
            print("\n开启末端工具供电...")
            robot.io.SetToolPower(1)  # 1 = 开启
            
            # ========== 批量IO操作 ==========
            print("\n--- 批量IO操作 ---")
            print("设置 DO1~DO4 全部为ON...")
            robot.io.DOGroup(1, 1, 2, 1, 3, 1, 4, 1)
            time.sleep(2)
            
            print("设置 DO1~DO4 全部为OFF...")
            robot.io.DOGroup(1, 0, 2, 0, 3, 0, 4, 0)
            time.sleep(1)
            
            # 下使能
            robot.robot_control.DisableRobot()
            
            print("\n" + "=" * 50)
            print("✅ IO控制示例完成")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
