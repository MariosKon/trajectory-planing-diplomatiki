# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
自定义异常类
"""


class DobotError(Exception):
    """Dobot SDK基础异常"""
    pass


class ConnectionError(DobotError):
    """连接异常"""
    def __init__(self, message="连接失败", ip=None, port=None):
        self.ip = ip
        self.port = port
        super().__init__(f"{message} (IP: {ip}, Port: {port})")


class ProtocolError(DobotError):
    """协议异常"""
    def __init__(self, message="协议错误", command=None):
        self.command = command
        super().__init__(f"{message} (Command: {command})")


class RobotError(DobotError):
    """机器人异常"""
    def __init__(self, message="机器人错误", error_code=None):
        self.error_code = error_code
        super().__init__(f"{message} (Code: {error_code})")


class TimeoutError(DobotError):
    """超时异常"""
    pass
