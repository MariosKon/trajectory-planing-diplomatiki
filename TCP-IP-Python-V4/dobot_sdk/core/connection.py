# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
TCP连接管理器

提供通用的TCP连接功能，支持自动重连和连接状态监听
"""

import socket
import threading
import logging
import time
from typing import Optional, Callable
from .exceptions import ConnectionError

logger = logging.getLogger("dobot_sdk")


class DobotConnection:
    """
    TCP连接管理器
    
    负责建立和维护与机器人的TCP连接，支持：
    - 接收超时设置
    - 自动重连机制
    - 指数退避重连策略
    - 连接状态变化回调
    """
    
    def __init__(self, ip: str, port: int, buffer_size: int = 144000):
        """
        初始化连接
        
        Args:
            ip: 机器人IP地址
            port: 端口号(29999或30004)
            buffer_size: 接收缓冲区大小
        """
        self.ip = ip
        self.port = port
        self.buffer_size = buffer_size
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
        
        # 超时设置
        self._connect_timeout = 5.0      # 连接超时（秒）
        self._receive_timeout = 10.0     # 接收超时（秒）
        
        # 自动重连设置
        self._auto_reconnect = False     # 是否启用自动重连
        self._reconnect_running = False  # 重连线程是否运行
        self._reconnect_thread = None    # 重连线程
        self._reconnect_callback = None  # 连接状态回调函数
        
        # 指数退避参数
        self._min_reconnect_delay = 1    # 最小重连延迟（秒）
        self._max_reconnect_delay = 30   # 最大重连延迟（秒）
        self._reconnect_attempts = 0     # 当前重连尝试次数
        
        # 验证端口
        if port not in [29999, 30004, 30005, 30006]:
            raise ValueError(f"Invalid port: {port}. Must be 29999, 30004, 30005, or 30006")
    
    def set_timeout(self, connect_timeout: float = None, receive_timeout: float = None):
        """
        设置超时时间
        
        Args:
            connect_timeout: 连接超时时间（秒），默认5秒
            receive_timeout: 接收超时时间（秒），默认10秒
        """
        if connect_timeout is not None:
            self._connect_timeout = connect_timeout
        if receive_timeout is not None:
            self._receive_timeout = receive_timeout
    
    def enable_auto_reconnect(self, enable: bool = True, callback: Callable[[bool], None] = None):
        """
        启用/禁用自动重连
        
        Args:
            enable: 是否启用自动重连
            callback: 连接状态变化回调函数，接收一个布尔参数表示连接状态
        """
        self._auto_reconnect = enable
        self._reconnect_callback = callback
        
        if enable and not self._reconnect_running and not self._connected:
            self._start_reconnect_loop()
    
    def _start_reconnect_loop(self):
        """启动重连循环线程"""
        if self._reconnect_running:
            return
        
        self._reconnect_running = True
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True
        )
        self._reconnect_thread.start()
        logger.info(f"自动重连已启动: {self.ip}:{self.port}")
    
    def _stop_reconnect_loop(self):
        """停止重连循环线程"""
        self._reconnect_running = False
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2.0)
            self._reconnect_thread = None
        self._reconnect_attempts = 0
        logger.info(f"自动重连已停止: {self.ip}:{self.port}")
    
    def _reconnect_loop(self):
        """重连循环，使用指数退避策略"""
        while self._reconnect_running:
            try:
                # 计算指数退避延迟
                delay = min(
                    self._min_reconnect_delay * (2 ** self._reconnect_attempts),
                    self._max_reconnect_delay
                )
                
                logger.info(f"等待 {delay:.1f} 秒后尝试重连: {self.ip}:{self.port}")
                time.sleep(delay)
                
                if not self._reconnect_running:
                    break
                
                # 尝试重新连接
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self._connect_timeout)
                self._socket.connect((self.ip, self.port))
                
                # 设置接收缓冲区和超时
                self._socket.setsockopt(
                    socket.SOL_SOCKET, 
                    socket.SO_RCVBUF, 
                    self.buffer_size
                )
                self._socket.settimeout(self._receive_timeout)
                
                self._connected = True
                self._reconnect_attempts = 0  # 重置重连计数
                
                logger.info(f"TCP重连成功: {self.ip}:{self.port}")
                
                # 调用连接成功回调
                if self._reconnect_callback:
                    try:
                        self._reconnect_callback(True)
                    except Exception as e:
                        logger.error(f"连接成功回调执行失败: {str(e)}")
                
                # 重连成功，退出重连循环
                self._stop_reconnect_loop()
                
            except socket.timeout:
                self._reconnect_attempts += 1
                logger.warning(f"重连超时 ({self._reconnect_attempts}次): {self.ip}:{self.port}")
                
            except socket.error as e:
                self._reconnect_attempts += 1
                logger.warning(f"重连失败 ({self._reconnect_attempts}次): {self.ip}:{self.port} - {str(e)}")
                
            except Exception as e:
                self._reconnect_attempts += 1
                logger.error(f"重连异常 ({self._reconnect_attempts}次): {self.ip}:{self.port} - {str(e)}")
    
    def connect(self, timeout: float = None):
        """
        建立TCP连接
        
        Args:
            timeout: 连接超时时间（秒），默认为初始化时设置的值
            
        Raises:
            ConnectionError: 连接失败时抛出
        """
        actual_timeout = timeout if timeout is not None else self._connect_timeout
        
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(actual_timeout)
            self._socket.connect((self.ip, self.port))
            
            # 设置接收缓冲区和超时
            self._socket.setsockopt(
                socket.SOL_SOCKET, 
                socket.SO_RCVBUF, 
                self.buffer_size
            )
            self._socket.settimeout(self._receive_timeout)
            
            self._connected = True
            self._reconnect_attempts = 0  # 重置重连计数
            
            logger.info(f"TCP连接成功: {self.ip}:{self.port}")
            
            # 调用连接成功回调
            if self._reconnect_callback:
                try:
                    self._reconnect_callback(True)
                except Exception as e:
                    logger.error(f"连接成功回调执行失败: {str(e)}")
            
        except socket.timeout:
            logger.error(f"TCP连接超时: {self.ip}:{self.port}")
            self._trigger_disconnect_callback()
            raise ConnectionError("连接超时", ip=self.ip, port=self.port)
        except socket.error as e:
            logger.error(f"TCP连接失败: {self.ip}:{self.port} - {str(e)}")
            self._trigger_disconnect_callback()
            raise ConnectionError(f"连接失败: {str(e)}", ip=self.ip, port=self.port)
    
    def _trigger_disconnect_callback(self, force: bool = False):
        """
        触发连接断开回调
        
        Args:
            force: 是否强制触发回调（不检查连接状态）
        """
        if self._reconnect_callback and (force or self._connected):
            try:
                self._reconnect_callback(False)
            except Exception as e:
                logger.error(f"连接断开回调执行失败: {str(e)}")
    
    def disconnect(self):
        """关闭连接"""
        # 停止自动重连
        self._stop_reconnect_loop()
        
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                logger.info(f"TCP连接已断开: {self.ip}:{self.port}")
            except Exception as e:
                logger.warning(f"TCP断开连接时发生错误: {str(e)}")
            finally:
                self._socket = None
                self._connected = False
                # 强制触发断开回调（用户主动断开）
                self._trigger_disconnect_callback(force=True)
    
    def send_text(self, text: str):
        """
        发送文本命令（Dashboard用）
        
        Args:
            text: 要发送的命令字符串
        """
        if not self._connected or not self._socket:
            raise ConnectionError("未连接到机器人")
        
        try:
            # 直接编码发送，添加换行符
            command = text if text.endswith('\n') else text + '\n'
            self._socket.send(command.encode('utf-8'))
            logger.debug(f"发送命令: {text.strip()}")
        except Exception as e:
            self._connected = False
            logger.error(f"发送命令失败: {text.strip()} - {str(e)}")
            self._trigger_disconnect_callback()
            
            # 如果启用了自动重连，启动重连循环
            if self._auto_reconnect and not self._reconnect_running:
                self._start_reconnect_loop()
            
            raise ConnectionError(f"发送失败 {str(e)}")
    
    def receive_text(self, buffer_size: int = 1024) -> str:
        """
        接收文本响应（Dashboard用）
        
        Args:
            buffer_size: 接收缓冲区大小
            
        Returns:
            str: 接收到的字符串
        """
        if not self._connected or not self._socket:
            raise ConnectionError("未连接到机器人")
        
        try:
            data = self._socket.recv(buffer_size)
            if not data:
                raise ConnectionError("连接已关闭")
            
            response = data.decode('utf-8').strip()
            logger.debug(f"接收响应: {response}")
            return response
        except socket.timeout:
            self._connected = False
            logger.error(f"接收响应超时: {self.ip}:{self.port}")
            self._trigger_disconnect_callback()
            
            # 如果启用了自动重连，启动重连循环
            if self._auto_reconnect and not self._reconnect_running:
                self._start_reconnect_loop()
            
            raise ConnectionError("接收超时")
        except Exception as e:
            self._connected = False
            logger.error(f"接收响应失败: {str(e)}")
            self._trigger_disconnect_callback()
            
            # 如果启用了自动重连，启动重连循环
            if self._auto_reconnect and not self._reconnect_running:
                self._start_reconnect_loop()
            
            raise ConnectionError(f"接收失败: {str(e)}")
    
    def receive_bytes(self, buffer_size: int = 144000) -> bytes:
        """
        接收原始字节（Feedback用）
        
        Args:
            buffer_size: 接收缓冲区大小
            
        Returns:
            bytes: 接收到的原始字节
        """
        if not self._connected or not self._socket:
            raise ConnectionError("未连接到机器人")
        
        try:
            data = self._socket.recv(buffer_size)
            if not data:
                raise ConnectionError("连接已关闭")
            
            logger.debug(f"接收字节数据: {len(data)} bytes")
            return data
        except socket.timeout:
            self._connected = False
            logger.error(f"接收字节数据超时: {self.ip}:{self.port}")
            self._trigger_disconnect_callback()
            
            # 如果启用了自动重连，启动重连循环
            if self._auto_reconnect and not self._reconnect_running:
                self._start_reconnect_loop()
            
            raise ConnectionError("接收超时")
        except Exception as e:
            self._connected = False
            logger.error(f"接收字节数据失败: {str(e)}")
            self._trigger_disconnect_callback()
            
            # 如果启用了自动重连，启动重连循环
            if self._auto_reconnect and not self._reconnect_running:
                self._start_reconnect_loop()
            
            raise ConnectionError(f"接收失败: {str(e)}")
    
    def send_receive_text(self, text: str, recv_size: int = 1024) -> str:
        """
        发送并接收响应（线程安全）
        
        Args:
            text: 发送的字符串
            recv_size: 接收缓冲区大小
            
        Returns:
            str: 接收到的响应
        """
        with self._lock:
            self.send_text(text)
            return self.receive_text(recv_size)
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected
    
    @property
    def reconnect_enabled(self) -> bool:
        """检查是否启用了自动重连"""
        return self._auto_reconnect
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
    
    def __del__(self):
        """析构函数"""
        self.disconnect()
