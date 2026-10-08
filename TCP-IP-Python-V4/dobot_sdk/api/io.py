# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""IO相关模块 - 数字IO、模拟IO、末端IO控制"""

from typing import List, Union
from ..core.connection import DobotConnection


class IO:
    """IO模块 - 处理所有IO相关指令"""

    def __init__(self, connection: DobotConnection):
        self.connection = connection

    def _send_cmd(self, command: str) -> str:
        """发送命令并接收响应"""
        return self.connection.send_receive_text(command)

    # ==================== 数字输出端口 ====================

    def DO(self, index: int, status: int, time: float = None) -> str:
        """
        设置数字输出端口状态（队列指令）
        Args:
            index: DO端口索引 (1-based)
            status: 状态(0=Off, 1=On)
            time: 输出持续时间(秒)。当status=1时有效，到达时间后自动变为0。

        Returns:
            str: ErrorID,{ResultID},DO(index,status,time);
        """
        if status not in [0, 1]:
            raise ValueError("DO状态必须是0或1")
        if time is not None:
            return self._send_cmd(f"DO({index},{status},{time:.3f})")
        return self._send_cmd(f"DO({index},{status})")

    def DOInstant(self, index: int, status: int) -> str:
        """
        设置数字输出端口状态（立即指令）
        Args:
            index: DO端口索引 (1-based)
            status: 状态(0=Off, 1=On)

        Returns:
            str: ErrorID,{},DOInstant(index,status);
        """
        if status not in [0, 1]:
            raise ValueError("DO状态必须是0或1")
        return self._send_cmd(f"DOInstant({index},{status})")

    def GetDO(self, index: int) -> str:
        """
        获取数字输出端口状态（立即指令）
        Args:
            index: DO端口索引 (1-based)

        Returns:
            str: ErrorID,{status},GetDO(index);
        """
        return self._send_cmd(f"GetDO({index})")

    def DOGroup(self, *index_value_pairs) -> str:
        """
        设置多个数字输出端口状态（队列指令）
        Args:
            *index_value_pairs: 端口索引和状态的成对参数，如 DOGroup(4,1,6,0,2,1,7,0)

        Returns:
            str: ErrorID,{ResultID},DOGroup(index1,value1,index2,value2,...);
        """
        if len(index_value_pairs) % 2 != 0:
            raise ValueError("DOGroup参数必须是偶数个（index与value成对）")
        params = []
        for i in range(0, len(index_value_pairs), 2):
            index = index_value_pairs[i]
            value = index_value_pairs[i + 1]
            if not isinstance(index, int):
                raise ValueError("DOGroup的index必须是int类型")
            if value not in [0, 1]:
                raise ValueError("DOGroup的value必须是0或1")
            params.append(str(index))
            params.append(str(value))
        return self._send_cmd(f"DOGroup({','.join(params)})")

    def DOGroupDEC(self, indices: Union[List[int], str], value: int) -> str:
        """
        通过赋值十进制设置多个数字输出端口状态（队列指令）
        Args:
            indices: 端口索引列表，如[1,2,3,4,5] 或字符串 "{1,2,3,4,5}"
            value: 十进制值
        Returns:
            str: ErrorID,{ResultID},DOGroupDEC({index1,index2,...,indexN},value);
        """
        if isinstance(indices, list):
            indices_str = "{" + ",".join(str(i) for i in indices) + "}"
        else:
            indices_str = indices
        return self._send_cmd(f"DOGroupDEC({indices_str},{value})")

    def GetDOGroup(self, *indices) -> str:
        """
        获取多个数字输出端口状态（立即指令）
        Args:
            *indices: 要读取的DO端口编号，如 GetDOGroup(1,2)

        Returns:
            str: ErrorID,{status1,status2,...},GetDOGroup(index1,index2,...);
        """
        params = ",".join(str(i) for i in indices)
        return self._send_cmd(f"GetDOGroup({params})")

    def GetDOGroupDEC(self, indices: Union[List[int], str]) -> str:
        """
        获取多个数字输出端口当前状态，返回值为十进制数（立即指令）

        Args:
            indices: 端口索引列表，如[1,2,3] 或字符串 "{1,2,3}"

        Returns:
            str: ErrorID,{value},GetDOGroupDEC({index1,...,indexN});
        """
        if isinstance(indices, list):
            indices_str = "{" + ",".join(str(i) for i in indices) + "}"
        else:
            indices_str = indices
        return self._send_cmd(f"GetDOGroupDEC({indices_str})")

    # ==================== 数字输入端口 ====================

    def DI(self, index: int) -> str:
        """
        获取DI端口的状态（立即指令）
        Args:
            index: DI端口索引 (1-based)

        Returns:
            str: ErrorID,{status},DI(index);
        """
        return self._send_cmd(f"DI({index})")

    def DIGroup(self, *indices) -> str:
        """
        获取多个DI端口的状态（立即指令）
        Args:
            *indices: 要读取的DI端口编号，如 DIGroup(4,6,2,7)

        Returns:
            str: ErrorID,{status1,status2,...},DIGroup(index1,index2,...);
        """
        params = ",".join(str(i) for i in indices)
        return self._send_cmd(f"DIGroup({params})")

    def DIGroupDEC(self, indices: Union[List[int], str]) -> str:
        """
        获取多个DI端口的状态，返回值为十进制数（队列指令）

        Args:
            indices: 端口索引列表，如[1,2] 或字符串 "{1,2}"

        Returns:
            str: ErrorID,{value},DIGroupDEC({index1,index2,...,indexN});
        """
        if isinstance(indices, list):
            indices_str = "{" + ",".join(str(i) for i in indices) + "}"
        else:
            indices_str = indices
        return self._send_cmd(f"DIGroupDEC({indices_str})")

    # ==================== 模拟输出端口 ====================

    def AO(self, index: int, value: float) -> str:
        """
        设置模拟输出端口的值（队列指令）
        Args:
            index: AO端口索引 (1-based)
            value: 模拟值(0.0-10.0V)

        Returns:
            str: ErrorID,{ResultID},AO(index,value);
        """
        return self._send_cmd(f"AO({index},{value:.2f})")

    def AOInstant(self, index: int, value: float) -> str:
        """
        设置模拟输出端口的值（立即指令）
        Args:
            index: AO端口索引 (1-based)
            value: 模拟值(0.0-10.0V)

        Returns:
            str: ErrorID,{},AOInstant(index,value);
        """
        return self._send_cmd(f"AOInstant({index},{value:.2f})")

    def GetAO(self, index: int) -> str:
        """
        获取模拟输出端口的值（立即指令）
        Args:
            index: AO端口索引 (1-based)

        Returns:
            str: ErrorID,{value},GetAO(index);
        """
        return self._send_cmd(f"GetAO({index})")

    # ==================== 模拟输入端口 ====================

    def AI(self, index: int) -> str:
        """
        获取AI端口的值（立即指令）
        Args:
            index: AI端口索引 (1-based)

        Returns:
            str: ErrorID,{value},AI(index);
        """
        return self._send_cmd(f"AI({index})")

    # ==================== 末端数字输出端口 ====================

    def ToolDO(self, index: int, status: int) -> str:
        """
        设置末端数字输出端口状态（队列指令）
        Args:
            index: 末端DO端口索引 (0-1)
            status: 状态(0=Off, 1=On)

        Returns:
            str: ErrorID,{ResultID},ToolDO(index,status);
        """
        if status not in [0, 1]:
            raise ValueError("DO状态必须是0或1")
        return self._send_cmd(f"ToolDO({index},{status})")

    def ToolDOInstant(self, index: int, status: int) -> str:
        """
        设置末端数字输出端口状态（立即指令）
        Args:
            index: 末端DO端口索引 (0-1)
            status: 状态(0=Off, 1=On)

        Returns:
            str: ErrorID,{},ToolDOInstant(index,status);
        """
        if status not in [0, 1]:
            raise ValueError("DO状态必须是0或1")
        return self._send_cmd(f"ToolDOInstant({index},{status})")

    def GetToolDO(self, index: int) -> str:
        """
        获取末端数字输出端口状态（立即指令）
        Args:
            index: 末端DO端口索引 (0-1)

        Returns:
            str: ErrorID,{status},GetToolDO(index);
        """
        return self._send_cmd(f"GetToolDO({index})")

    # ==================== 末端数字输入端口 ====================

    def ToolDI(self, index: int) -> str:
        """
        获取末端DI端口的状态（立即指令）
        Args:
            index: 末端DI端口索引
        Returns:
            str: ErrorID,{status},ToolDI(index);
        """
        return self._send_cmd(f"ToolDI({index})")

    # ==================== 末端模拟输入端口 ====================

    def ToolAI(self, index: int) -> str:
        """
        获取末端AI端口的值（立即指令）
        Args:
            index: 末端AI端口索引
        Returns:
            str: ErrorID,{value},ToolAI(index);
        """
        return self._send_cmd(f"ToolAI({index})")

    # ==================== 末端工具设置 ====================

    def SetTool485(self, baud: int, parity: str = "N", stopbit: int = 1, identify: int = None) -> str:
        """
        设置末端485通信格式（立即指令）

        Args:
            baud: 波特率
            parity: 校验位("O"=奇校验, "E"=偶校验, "N"=无校验) 默认"N"
            stopbit: 停止位 默认1
            identify: 辨识参数（可选）
        Returns:
            str: ErrorID,{},SetTool485(baud,parity,stopbit[,identify]);
        """
        if identify is not None:
            return self._send_cmd(f'SetTool485({baud},"{parity}",{stopbit},{identify})')
        return self._send_cmd(f'SetTool485({baud},"{parity}",{stopbit})')

    def SetToolPower(self, status: int) -> str:
        """
        设置末端工具供电状态（立即指令）
        Args:
            status: 供电状态(0-关闭, 1-开启)

        Returns:
            str: ErrorID,{},SetToolPower(status);
        """
        if status not in [0, 1]:
            raise ValueError("状态必须是0或1")
        return self._send_cmd(f"SetToolPower({status})")

    def SetToolMode(self, mode: int, type: int = None, identify: int = None) -> str:
        """
        设置末端复用端子的模式（立即指令）
        Args:
            mode: 模式值
            type: 类型值（可选）
            identify: 辨识参数（可选）
        Returns:
            str: ErrorID,{},SetToolMode(mode[,type[,identify]]);
        """
        params = [str(mode)]
        if type is not None:
            params.append(str(type))
            if identify is not None:
                params.append(str(identify))
        return self._send_cmd(f"SetToolMode({','.join(params)})")