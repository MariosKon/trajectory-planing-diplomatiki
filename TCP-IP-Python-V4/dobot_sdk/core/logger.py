# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
日志记录模块
提供SDK统一的日志记录功能，支持跨平台运行（Windows/Ubuntu）
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime


class DobotLogger:
    """
    越疆机器人SDK日志记录器
    
    特性:
        - 支持多日志级别: DEBUG, INFO, WARNING, ERROR
        - 同时输出到控制台和日志文件
        - 日志文件自动轮转（最多保留5个文件，每个最大10MB）
        - 跨平台兼容（Windows/Ubuntu）
        - 结构化日志格式
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_level: str = "INFO", log_dir: Optional[str] = None):
        """
        初始化日志记录器
        
        Args:
            log_level: 日志级别，可选 "DEBUG", "INFO", "WARNING", "ERROR"
            log_dir: 日志文件目录，默认为SDK安装目录下的logs文件夹
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        # 获取日志目录
        if log_dir is None:
            # 默认日志目录: SDK安装目录/logs
            sdk_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.log_dir = os.path.join(sdk_dir, 'logs')
        else:
            self.log_dir = log_dir
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 日志文件名格式: dobot_sdk_20260615.log
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = os.path.join(self.log_dir, f"dobot_sdk_{today}.log")
        
        # 创建日志记录器
        self.logger = logging.getLogger("dobot_sdk")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.propagate = False
        
        # 移除已存在的处理器，避免重复
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # 文件处理器（带轮转）
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,              # 最多保留5个备份
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 日志格式
        log_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
        )
        console_handler.setFormatter(log_format)
        file_handler.setFormatter(log_format)
        
        # 添加处理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """获取日志记录器实例"""
        return self.logger
    
    @property
    def log_directory(self) -> str:
        """获取日志文件目录"""
        return self.log_dir


# 全局日志装饰器
def log_api_call(func):
    """
    装饰器：记录API调用日志
    
    自动记录：
        - 调用的函数名
        - 传入的参数
        - 返回值
        - 执行时间
        - 异常信息（如果发生）
    """
    import time
    
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("dobot_sdk")
        start_time = time.time()
        
        # 获取调用信息
        class_name = ""
        if len(args) > 0 and hasattr(args[0], '__class__'):
            class_name = args[0].__class__.__name__ + "."
        
        func_name = class_name + func.__name__
        
        # 格式化参数
        args_str = []
        for i, arg in enumerate(args[1:], 1):  # 跳过self
            args_str.append(f"arg{i}={arg!r}")
        for k, v in kwargs.items():
            args_str.append(f"{k}={v!r}")
        
        args_str = ", ".join(args_str)
        
        # 记录调用信息
        logger.info(f"API调用: {func_name}({args_str})")
        
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000
            
            # 记录返回值（限制长度）
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            
            logger.debug(f"API返回: {func_name} -> {result_str} (耗时: {elapsed:.2f}ms)")
            
            return result
        
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"API异常: {func_name} -> {type(e).__name__}: {str(e)} (耗时: {elapsed:.2f}ms)", exc_info=True)
            raise
    
    return wrapper


def get_logger() -> logging.Logger:
    """便捷函数：获取全局日志记录器"""
    return DobotLogger().get_logger()


def set_log_level(log_level: str):
    """
    设置全局日志级别
    
    Args:
        log_level: "DEBUG", "INFO", "WARNING", "ERROR"
    """
    logger = DobotLogger(log_level=log_level).get_logger()
    logger.setLevel(getattr(logging, log_level.upper()))
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)


def get_log_directory() -> str:
    """获取日志文件存储目录"""
    return DobotLogger().log_directory
