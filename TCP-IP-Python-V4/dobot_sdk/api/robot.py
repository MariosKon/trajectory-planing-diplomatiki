# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
机器人主控制器
整合所有模块，提供统一的控制接口"""

import threading
import time
import logging
from typing import Optional, Callable
from ..core.connection import DobotConnection
from ..protocol.feedback import FeedbackParser
from ..models.status import RobotStatus
from .motion import Motion, CoordinateType
from .io import IO
from .communication import Communication
from .plugins import Plugins
from .robot_control import RobotControl
from .error_controller import ErrorController

logger = logging.getLogger("dobot_sdk")


class DobotRobot:
    """
    越疆机器人控制主类
    示例:
        with DobotRobot("192.168.1.100") as robot:
            robot.robot_control.EnableRobot()
            pose = [400, 0, 300, 180, 0, 0]
            robot.motion.MovJ(pose, CoordinateType.CARTESIAN)
    """

    def __init__(self, ip: str,
                 dashboard_port: int = 29999,
                 feedback_port: int = 30004,
                 feedback_port_30005: int = None,
                 feedback_port_30006: int = None,
                 connect_timeout: float = 5.0,
                 receive_timeout: float = 10.0):
        """
        初始化机器人对象

        Args:
            ip: 机器人IP地址
            dashboard_port: Dashboard端口 (默认29999)
            feedback_port: Feedback端口 (默认30004)
                              - 30004: 实时反馈，每8ms
                              - 30005: 配置反馈，每200ms
                              - 30006: 配置反馈，每1000ms
            feedback_port_30005: 可选的第二个反馈端口(默认None)
            feedback_port_30006: 可选的第三个反馈端口(默认None)
            connect_timeout: 连接超时时间（秒），默认5秒
            receive_timeout: 接收超时时间（秒），默认10秒
        """
        self.ip = ip
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout

        # 连接 - Dashboard
        self._dashboard_conn = DobotConnection(ip, dashboard_port)
        self._dashboard_conn.set_timeout(connect_timeout, receive_timeout)
        
        # 连接 - Feedback 端口
        self._feedback_conn = DobotConnection(ip, feedback_port)
        self._feedback_conn.set_timeout(connect_timeout, receive_timeout)
        
        # 可选的额外反馈端口连接
        self._feedback_conn_30005 = None
        if feedback_port_30005:
            self._feedback_conn_30005 = DobotConnection(ip, feedback_port_30005)
            self._feedback_conn_30005.set_timeout(connect_timeout, receive_timeout)
        
        self._feedback_conn_30006 = None
        if feedback_port_30006:
            self._feedback_conn_30006 = DobotConnection(ip, feedback_port_30006)
            self._feedback_conn_30006.set_timeout(connect_timeout, receive_timeout)

        # 协议解析器（仅Feedback需要）
        self._feedback_parser = FeedbackParser()

        # 5个模块
        self.motion = Motion(self._dashboard_conn)                    # 运动模块
        self.io = IO(self._dashboard_conn)                            # IO模块
        self.communication = Communication(self._dashboard_conn)       # 通讯模块
        self.plugins = Plugins(self._dashboard_conn)                  # 插件模块
        self.robot_control = RobotControl(self._dashboard_conn)      # Robot控制模块
        self.error = ErrorController(ip)                              # 错误控制模块

        # 状态监控
        self._latest_status: Optional[RobotStatus] = None
        self._feedback_thread: Optional[threading.Thread] = None
        self._feedback_running = False
        self._callback: Optional[Callable] = None
        
        # 连接状态回调
        self._connection_callback: Optional[Callable[[bool], None]] = None

    def SetTimeout(self, connect_timeout: float = None, receive_timeout: float = None):
        """
        设置超时时间
        
        Args:
            connect_timeout: 连接超时时间（秒）
            receive_timeout: 接收超时时间（秒）
        """
        self._dashboard_conn.set_timeout(connect_timeout, receive_timeout)
        self._feedback_conn.set_timeout(connect_timeout, receive_timeout)
        if self._feedback_conn_30005:
            self._feedback_conn_30005.set_timeout(connect_timeout, receive_timeout)
        if self._feedback_conn_30006:
            self._feedback_conn_30006.set_timeout(connect_timeout, receive_timeout)
        
        if connect_timeout is not None:
            self._connect_timeout = connect_timeout
        if receive_timeout is not None:
            self._receive_timeout = receive_timeout

    def EnableAutoReconnect(self, enable: bool = True, callback: Callable[[bool], None] = None):
        """
        启用/禁用自动重连功能
        
        Args:
            enable: 是否启用自动重连
            callback: 连接状态变化回调函数，接收一个布尔参数表示连接状态
                      True: 连接成功，False: 连接断开
        """
        self._connection_callback = callback
        
        def connection_status_handler(is_connected: bool):
            logger.info(f"机器人连接状态变化: {'已连接' if is_connected else '已断开'}")
            if self._connection_callback:
                try:
                    self._connection_callback(is_connected)
                except Exception as e:
                    logger.error(f"连接状态回调执行失败: {str(e)}")
        
        self._dashboard_conn.enable_auto_reconnect(enable, connection_status_handler)
        self._feedback_conn.enable_auto_reconnect(enable, connection_status_handler)
        if self._feedback_conn_30005:
            self._feedback_conn_30005.enable_auto_reconnect(enable, connection_status_handler)
        if self._feedback_conn_30006:
            self._feedback_conn_30006.enable_auto_reconnect(enable, connection_status_handler)
        
        logger.info(f"自动重连{'已启用' if enable else '已禁用'}")

    def Connect(self, timeout: float = None):
        """
        连接到机器人

        Args:
            timeout: 连接超时时间（秒），默认为初始化时设置的值
        """
        actual_timeout = timeout if timeout is not None else self._connect_timeout
        
        logger.info(f"正在连接到机器人 {self.ip}...")
        self._dashboard_conn.connect(actual_timeout)
        self._feedback_conn.connect(actual_timeout)
        
        # 连接可选的额外反馈端口
        if self._feedback_conn_30005:
            self._feedback_conn_30005.connect(actual_timeout)
        if self._feedback_conn_30006:
            self._feedback_conn_30006.connect(actual_timeout)
            
        logger.info(f"机器人连接成功: {self.ip}")
    
    @property
    def IsConnected(self) -> bool:
        """
        检查机器人连接状态
        
        Returns:
            bool: True表示已连接，False表示未连接
        """
        return (self._dashboard_conn.is_connected and 
                self._feedback_conn.is_connected and
                (not self._feedback_conn_30005 or self._feedback_conn_30005.is_connected) and
                (not self._feedback_conn_30006 or self._feedback_conn_30006.is_connected))

    def Disconnect(self):
        """断开连接"""
        self.StopFeedbackMonitor()
        self._dashboard_conn.disconnect()
        self._feedback_conn.disconnect()
        
        # 断开可选的额外反馈端口
        if self._feedback_conn_30005:
            self._feedback_conn_30005.disconnect()
        if self._feedback_conn_30006:
            self._feedback_conn_30006.disconnect()
            
        logger.info(f"机器人已断开连接: {self.ip}")

    def GetStatus(self) -> Optional[RobotStatus]:
        """
        获取最新机器人状态
        Returns:
            RobotStatus: 机器人状态，如果未启动监控则返回None
        """
        return self._latest_status

    def StartFeedbackMonitor(self, callback: Callable = None):
        """
        启动状态反馈监控线程
        Args:
            callback: 状态更新回调函数，接收RobotStatus参数
        """
        if self._feedback_running:
            return

        self._callback = callback
        self._feedback_running = True

        self._feedback_thread = threading.Thread(
            target=self._feedback_loop,
            daemon=True
        )
        self._feedback_thread.start()
        logger.info("状态监控已启动")

    def StopFeedbackMonitor(self):
        """停止状态反馈监控"""
        self._feedback_running = False
        if self._feedback_thread:
            self._feedback_thread.join(timeout=2.0)
            self._feedback_thread = None
        logger.info("状态监控已停止")

    def _feedback_loop(self):
        """反馈数据接收循环"""
        while self._feedback_running:
            try:
                # 接收原始字节
                raw = self._feedback_conn.receive_bytes(144000)

                # 处理可能的粘包
                if len(raw) > 1440:
                    raw = self._feedback_conn.receive_bytes(144000)

                if len(raw) < 1440:
                    time.sleep(0.01)
                    continue

                # 截取1440字节
                packet = raw[:1440]

                # 解析
                status = self._feedback_parser.parse(packet)
                if status:
                    self._latest_status = status

                    # 调用回调
                    if self._callback:
                        try:
                            self._callback(status)
                        except Exception as e:
                            logger.error(f"回调错误: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"反馈错误: {e}", exc_info=True)
                time.sleep(0.1)

    def __enter__(self):
        """上下文管理器入口"""
        self.Connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.Disconnect()
        return False

    def GetError(self, language: str = "zh_cn") -> dict:
        """
        获取机器人报警信息（通过HTTP接口）        
        Args:
            language: 语言设置，支持的语言
                     "zh_cn" - 简体中文                     "zh_hant" - 繁体中文  
                     "en" - 英语
                     "ja" - 日语
                     "de" - 德语
                     "vi" - 越南语                     "es" - 西班牙语
                     "fr" - 法语
                     "ko" - 韩语
                     "ru" - 俄语
        
        Returns:
            dict: 报警信息字典，格式如下：
            {
                "errMsg": [
                    {
                        "id": xxx,
                        "level": xxx,
                        "description": "xxx",
                        "solution": "xxx",
                        "mode": "xxx",
                        "date": "xxxx",
                        "time": "xxxx"
                    }
                ]
            }
            如果没有报警，返回{"errMsg": []}
        """
        return self.error.GetError(language)

    def GetErrorFormatted(self, language: str = "zh_cn") -> str:
        """
        获取格式化的机器人报警信息（通过HTTP接口获取        
        Args:
            language: 语言设置
        
        Returns:
            str: 格式化的报警信息字符串        """
        return self.error.GetErrorFormatted(language)

    def __del__(self):
        """析构函数"""
        self.Disconnect()

    # 向后兼容别名 (snake_case -> PascalCase
    set_timeout = SetTimeout
    enable_auto_reconnect = EnableAutoReconnect
    connect = Connect
    disconnect = Disconnect
    get_status = GetStatus
    start_feedback_monitor = StartFeedbackMonitor
    stop_feedback_monitor = StopFeedbackMonitor
    get_error = GetError
    get_error_formatted = GetErrorFormatted
    @property
    def is_connected(self):
        return self.IsConnected
