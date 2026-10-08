# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
报警信息数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class ErrorInfo:
    """
    单条报警信息
    
    从GetError接口返回的数据解析得到
    """
    id: int
    level: int
    description: str
    solution: str
    mode: str
    date: str
    time: str
    
    @property
    def timestamp_str(self) -> str:
        """获取完整时间戳字符串"""
        return f"{self.date} {self.time}"
    
    def __str__(self) -> str:
        return (
            f"Error ID: {self.id}\n"
            f"Level: {self.level}\n"
            f"Description: {self.description}\n"
            f"Solution: {self.solution}\n"
            f"Time: {self.timestamp_str}"
        )


@dataclass
class ErrorReport:
    """
    报警报告
    
    包含所有当前报警信息
    """
    errors: List[ErrorInfo]
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def has_errors(self) -> bool:
        """是否有报警"""
        return len(self.errors) > 0
    
    @property
    def error_count(self) -> int:
        """报警数量"""
        return len(self.errors)
    
    def get_critical_errors(self) -> List[ErrorInfo]:
        """获取严重级别的报警（level >= 5）"""
        return [e for e in self.errors if e.level >= 5]
    
    def __str__(self) -> str:
        if not self.has_errors:
            return "✅ 机器人状态正常，无报警信息"
        
        result = f"⚠️  发现 {self.error_count} 个报警\n"
        result += "=" * 50 + "\n"
        
        for i, error in enumerate(self.errors, 1):
            result += f"报警 {i}:\n"
            result += f"  ID: {error.id}\n"
            result += f"  级别: {error.level}\n"
            result += f"  描述: {error.description}\n"
            result += f"  解决方案: {error.solution}\n"
            result += f"  时间: {error.timestamp_str}\n"
            result += "-" * 30 + "\n"
        
        return result
