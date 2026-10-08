"""
DobotDemo - 机器人控制类
"""

import sys
import os

# 添加父目录到路径，以便导入dobot_sdk
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dobot_sdk import DobotRobot
import threading
from time import sleep
import re


class DobotDemo:
    def __init__(self, ip):
        self.ip = ip
        self.robot = None
        self.feedData = None
        self.__globalLockValue = threading.Lock()
        
        # 初始化反馈数据结构
        class item:
            def __init__(self):
                self.robotMode = -1
                self.robotCurrentCommandID = 0
                self.MessageSize = -1
                self.DigitalInputs = -1
                self.DigitalOutputs = -1
                self.robotCurrentCommandID = -1

        self.feedData = item()

    def start(self):
        """启动机器人并使能"""
        try:
            # 使用新SDK的上下文管理器
            self.robot = DobotRobot(self.ip)
            self.robot.Connect()
            
            # 请求TCP控制模式
            self.robot.robot_control.RequestControl()
            
            # 清除报警
            self.robot.robot_control.ClearError()
            
            # 使能机器人
            response = self.robot.robot_control.EnableRobot()
            if "Failed" in response:
                print("使能失败: 检查29999端口是否被占用")
                return
            print("使能成功")

            # 启动状态反馈线程
            self.robot.StartFeedbackMonitor(callback=self._feed_callback)
            sleep(1)

            # 定义两个目标点
            point_a = [146.3759, -283.4321, 332.3956, 177.7879, -1.8540, 147.5821]
            point_b = [146.3759, -283.4321, 432.3956, 177.7879, -1.8540, 147.5821]

            # 走点循环
            from dobot_sdk import CoordinateType
            while True:
                status = self.robot.GetStatus()
                if status:
                    self.feedData.DigitalInputs = status.digital_inputs
                    self.feedData.DigitalOutputs = status.digital_outputs
                    self.feedData.robotMode = status.robot_mode.value
                    self.feedData.robotCurrentCommandID = status.current_command_id
                
                print(f"DI: {self.feedData.DigitalInputs} 2DI: {bin(self.feedData.DigitalInputs)} --16: {hex(self.feedData.DigitalInputs)}")
                print(f"DO: {self.feedData.DigitalOutputs} 2DO: {bin(self.feedData.DigitalOutputs)} --16: {hex(self.feedData.DigitalOutputs)}")
                print(f"robomode {self.feedData.robotMode}")
                sleep(2)

        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()

    def _feed_callback(self, status):
        """状态反馈回调函数"""
        with self.__globalLockValue:
            self.feedData.robotMode = status.robot_mode.value
            self.feedData.DigitalInputs = status.digital_inputs
            self.feedData.DigitalOutputs = status.digital_outputs
            self.feedData.robotCurrentCommandID = status.current_command_id

    def RunPoint(self, point_list):
        """走点指令（使用新SDK）"""
        from dobot_sdk import CoordinateType
        
        # 执行关节运动
        response = self.robot.motion.MovJ(point_list, CoordinateType.CARTESIAN)
        print(f"MovJ: {response}")
        
        # 解析指令ID
        currentCommandID = self.parseResultId(response)[1]
        print(f"指令 ID: {currentCommandID}")
        
        # 等待运动完成
        while True:
            print(f"当前模式: {self.feedData.robotMode}")
            if self.feedData.robotMode == 5 and self.feedData.robotCurrentCommandID == currentCommandID:
                print("运动结束")
                break
            sleep(0.1)

    def parseResultId(self, valueRecv):
        """解析返回值"""
        if "Not Tcp" in valueRecv:
            print("Control Mode Is Not Tcp")
            return [1]
        return [int(num) for num in re.findall(r'-?\d+', valueRecv)] or [2]

    def __del__(self):
        """析构函数"""
        if self.robot:
            try:
                self.robot.StopFeedbackMonitor()
                self.robot.Disconnect()
            except Exception:
                pass
