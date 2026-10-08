# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
错误码处理模块
提供通过HTTP接口获取机器人报警信息的功能
"""

import requests
import json
from typing import List, Dict, Optional, Any

# 支持的语言列表
SUPPORTED_LANGUAGES = [
    ("中文", "zh_cn"),
    ("English", "en"),
    ("日本语", "ja"),
    ("Deutsch", "de"),
    ("Español", "es"),
    ("Русский", "ru"),
    ("韩国语", "ko"),
    ("繁体中文", "zh_hant"),
    ("越南语", "vi"),
    ("法语", "fr")
]


class ErrorController:
    """
    错误控制器类
    
    通过HTTP接口获取机器人报警信息    
    示例:
        error_ctrl = ErrorController("192.168.1.100")
        error_info = error_ctrl.GetError("zh_cn")
        formatted_error = error_ctrl.GetErrorFormatted("zh_cn")
    """
    
    def __init__(self, ip: str):
        """
        初始化错误控制器
        
        Args:
            ip: 机器人IP地址
        """
        self.ip = ip
    
    def SetLanguage(self, language: str = "zh_cn") -> bool:
        """
        设置机器人语言
        
        Args:
            language: 语言代码，支持的语言
                     "zh_cn" - 简体中文                     "zh_hant" - 繁体中文  
                     "en" - 英语
                     "ja" - 日语
                     "de" - 德语
                     "vi" - 越南语                     "es" - 西班牙语
                     "fr" - 法语
                     "ko" - 韩语
                     "ru" - 俄语
        
        Returns:
            是否设置成功
        """
        try:
            language_url = f"http://{self.ip}:22000/interface/language"
            language_data = {"type": language}
            
            response = requests.post(language_url, json=language_data, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"设置语言失败: {e}")
            return False
    
    def GetError(self, language: str = "zh_cn") -> Dict[str, Any]:
        """
        获取机器人报警信息        
        Args:
            language: 语言设置，默认为"zh_cn"
        
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
        try:
            # 首先设置语言
            self.SetLanguage(language)
            
            # 获取报警信息
            alarm_url = f"http://{self.ip}:22000/protocol/getAlarm"
            response = requests.get(alarm_url, timeout=5)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # 如果返回空对象，转换为标准格式
                    if result == {} or result is None:
                        return {"errMsg": []}
                    return result
                except json.JSONDecodeError:
                    # 如果返回空响应或非JSON格式，视为无报警
                    return {"errMsg": []}
            else:
                print(f"获取报警信息失败: HTTP {response.status_code}")
                return {"errMsg": []}
                
        except requests.exceptions.RequestException as e:
            print(f"HTTP请求异常: {e}")
            return {"errMsg": []}
        except Exception as e:
            print(f"获取报警信息时发生未知错误 {e}")
            return {"errMsg": []}
    
    def GetErrorFormatted(self, language: str = "zh_cn") -> str:
        """
        获取格式化的机器人报警信息        
        Args:
            language: 语言设置
        
        Returns:
            str: 格式化的报警信息字符串        """
        error_info = self.GetError(language)
        return self._format_error_messages(error_info)
    
    def _format_error_messages(self, error_info: Dict[str, Any]) -> str:
        """
        格式化错误信息        
        Args:
            error_info: get_error() 返回的报警信息字符        
        Returns:
            str: 格式化的错误信息字符串        """
        err_msg_list = error_info.get("errMsg", [])
        
        if not err_msg_list:
            return "无报警信息"
        
        messages = []
        for err in err_msg_list:
            error_id = err.get("id", "未知")
            level = err.get("level", "")
            description = err.get("description", "")
            solution = err.get("solution", "")
            mode = err.get("mode", "")
            date = err.get("date", "")
            time = err.get("time", "")
            
            msg = f"错误码 {error_id}"
            if level:
                msg += f"\n级别: {level}"
            if description:
                msg += f"\n描述: {description}"
            if solution:
                msg += f"\n解决方案: {solution}"
            if mode:
                msg += f"\n模式: {mode}"
            if date and time:
                msg += f"\n时间: {date} {time}"
            
            messages.append(msg)
        
        return "\n\n".join(messages)
    
    # 向后兼容别名 (snake_case -> PascalCase)
    set_language = SetLanguage
    get_error = GetError
    get_error_formatted = GetErrorFormatted


def parse_error_ids(error_response: Optional[str]) -> List[int]:
    """
    解析错误码响应字符串（用于TCP接口的GetErrorID命令)    
    Args:
        error_response: 机器人返回的错误码响应，格式为"0,{[1537,2048,2049]},GetErrorID();"
    
    Returns:
        解析出的错误码列表    """
    if not error_response:
        return []
    
    # 如果是错误消息而不是错误码响应，返回空列表
    if isinstance(error_response, str):
        # 检查是否是错误消息（如 "Control Mode Is Not Tcp"）
        if not error_response.strip().startswith('0,'):
            print(f"收到错误消息而非错误码：{error_response}")
            return []
    
    try:
        # 移除末尾的";GetErrorID()"
        if error_response.endswith('GetErrorID();'):
            error_response = error_response[:-len('GetErrorID();')].strip()
        
        # 格式为,{[1537,2048,2049]}
        # 提取大括号内的列表部分        start = error_response.find('{[')
        end = error_response.find(']}')
        
        if start != -1 and end != -1:
            list_str = error_response[start+2:end]
            error_ids = [int(x.strip()) for x in list_str.split(',') if x.strip()]
            return error_ids
        else:
            # 尝试直接解析为整数
            return [int(error_response.strip())]
    except ValueError as e:
        # 解析失败，返回空列表
        print(f"解析错误码失败：{e}")
        return []
    except Exception as e:
        print(f"解析错误码失败：{e}")
        return []


# 保留原有的独立函数接口，向后兼容
def set_language(ip: str, language: str = "zh_cn") -> bool:
    """
    设置机器人语言（兼容旧接口）    
    Args:
        ip: 机器人IP地址
        language: 语言代码
    
    Returns:
        是否设置成功
    """
    return ErrorController(ip).SetLanguage(language)


def get_error(ip: str, language: str = "zh_cn") -> Dict[str, Any]:
    """
    获取机器人报警信息（兼容旧接口）
    
    Args:
        ip: 机器人IP地址
        language: 语言设置
    
    Returns:
        报警信息字典
    """
    return ErrorController(ip).GetError(language)


def format_error_messages_from_http(error_info: Dict[str, Any]) -> str:
    """
    格式化HTTP接口返回的错误信息（兼容旧接口）
    
    Args:
        error_info: get_error() 返回的报警信息字符    
    Returns:
        格式化的错误信息字符串    """
    err_msg_list = error_info.get("errMsg", [])
    
    if not err_msg_list:
        return "无报警信息"
    
    messages = []
    for err in err_msg_list:
        error_id = err.get("id", "未知")
        level = err.get("level", "")
        description = err.get("description", "")
        solution = err.get("solution", "")
        mode = err.get("mode", "")
        date = err.get("date", "")
        time = err.get("time", "")
        
        msg = f"错误码 {error_id}"
        if level:
            msg += f"\n级别: {level}"
        if description:
            msg += f"\n描述: {description}"
        if solution:
            msg += f"\n解决方案: {solution}"
        if mode:
            msg += f"\n模式: {mode}"
        if date and time:
            msg += f"\n时间: {date} {time}"
        
        messages.append(msg)
    
    return "\n\n".join(messages)