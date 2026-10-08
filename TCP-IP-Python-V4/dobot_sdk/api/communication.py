# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""通讯相关模块 - Modbus 和总线寄存器控制"""

from typing import List, Union
from ..core.connection import DobotConnection


class Communication:
    """通讯模块 - 处理 Modbus 和总线寄存器通信"""

    def __init__(self, connection: DobotConnection):
        self.connection = connection

    def _send_cmd(self, command: str) -> str:
        """发送命令并接收响应"""
        return self.connection.send_receive_text(command)

    # ==================== Modbus 主站创建 ====================

    def ModbusCreate(self, ip: str, port: int, slave_id: int, is_rtu: int = 0) -> str:
        """
        创建 Modbus 主站

        Args:
            ip: 从站 IP 地址
            port: 从站端口
            slave_id: 从站 ID
            is_rtu: 是否为RTU 模式 (0-TCP, 1-RTU)，默认0

        Returns:
            str: ErrorID,{index},ModbusCreate(ip,port,slave_id,isRTU);
                 index 为返回的主站索引，后续调用其他Modbus 指令时使用
        """
        cmd = f'ModbusCreate("{ip}",{port},{slave_id},{is_rtu})'
        return self._send_cmd(cmd)

    def ModbusRTUCreate(self, slave_id: int, baud: int, 
                          parity: str = "E", data_bit: int = 8, 
                          stop_bit: int = 1) -> str:
        """
        创建基于 RS485 接口的 Modbus 主站

        Args:
            slave_id: 从站 ID
            baud: RS485 接口的波特率
            parity: 奇偶校验位("O"-奇校验, "E"-偶校验, "N"-无校验，默认"E")
            data_bit: 数据位长度，默认 8
            stop_bit: 停止位长度，默认 1

        Returns:
            str: ErrorID,{index},ModbusRTUCreate(slave_id,baud,parity,data_bit,stop_bit);
        """
        if parity not in ["O", "E", "N"]:
            raise ValueError("parity 必须为'O', 'E' 或 'N'")
        
        cmd = f'ModbusRTUCreate({slave_id},{baud},"{parity}",{data_bit},{stop_bit})'
        return self._send_cmd(cmd)

    def ModbusClose(self, index: int) -> str:
        """
        与 Modbus 从站断开连接，释放主站

        Args:
            index: 创建主站时返回的主站索引
        """
        return self._send_cmd(f"ModbusClose({index})")

    # ==================== 触点寄存器====================

    def GetInBits(self, index: int, addr: int, count: int) -> str:
        """
        读取 Modbus 从站触点寄存器（离散输入）地址的值

        Args:
            index: 创建主站时返回的主站索引
            addr: 触点寄存器起始地址
            count: 连续读取触点寄存器的值的数量，取值范围：[1, 16]

        Returns:
            str: ErrorID,{value1,value2,...,valuen},GetInBits(index,addr,count);
        """
        if not 1 <= count <= 16:
            raise ValueError("count 取值范围必须是 [1, 16]")
        
        cmd = f"GetInBits({index},{addr},{count})"
        return self._send_cmd(cmd)

    # ==================== 输入寄存器====================

    def GetInRegs(self, index: int, addr: int, count: int, val_type: str = "U16") -> str:
        """
        按照指定的数据类型，读取 Modbus 从站输入寄存器地址的值

        Args:
            index: 创建主站时返回的主站索引
            addr: 输入寄存器起始地址
            count: 连续读取输入寄存器的值的数量，取值范围：[1, 4]
            val_type: 读取的数据格式
                      U16（6位无符号整数（2个字节，占用1个寄存器）；
                      U32（32位无符号整数（个字节，占用2个寄存器）；
                      F32（2位单精度浮点数（4个字节，占用2个寄存器）；
                      F64（4位双精度浮点数（8个字节，占用4个寄存器）；
                      默认值为 U16

        Returns:
            str: ErrorID,{value1,value2,...,valuen},GetInRegs(index,addr,count,valType);
        """
        if not 1 <= count <= 4:
            raise ValueError("count 取值范围必须是 [1, 4]")
        if val_type not in ["U16", "U32", "F32", "F64"]:
            raise ValueError("val_type 必须为'U16', 'U32', 'F32' 或 'F64'")
        
        cmd = f'GetInRegs({index},{addr},{count},"{val_type}")'
        return self._send_cmd(cmd)

    # ==================== 线圈寄存器====================

    def GetCoils(self, index: int, addr: int, count: int) -> str:
        """
        读取 Modbus 从站线圈寄存器地址的值

        Args:
            index: 创建主站时返回的主站索引
            addr: 线圈寄存器起始地址
            count: 连续读取线圈寄存器的值的数量，取值范围：[1, 16]

        Returns:
            str: ErrorID,{value1,value2,...,valuen},GetCoils(index,addr,count);
        """
        if not 1 <= count <= 16:
            raise ValueError("count 取值范围必须是 [1, 16]")
        
        cmd = f"GetCoils({index},{addr},{count})"
        return self._send_cmd(cmd)

    def SetCoils(self, index: int, addr: int, count: int, val_tab: Union[List[int], str]) -> str:
        """
        将指定的值写入线圈寄存器指定的地址

        Args:
            index: 创建主站时返回的主站索引
            addr: 线圈寄存器起始地址
            count: 连续写入线圈寄存器的值的数量，取值范围：[1, 16]
            val_tab: 要写入的值，数量与count 相同

        Returns:
            str: ErrorID,{},SetCoils(index,addr,count,valTab);
        """
        if not 1 <= count <= 16:
            raise ValueError("count 取值范围必须是 [1, 16]")
        
        if isinstance(val_tab, list):
            val_str = "{" + ",".join(str(v) for v in val_tab) + "}"
        else:
            val_str = val_tab
        
        cmd = f"SetCoils({index},{addr},{count},{val_str})"
        return self._send_cmd(cmd)

    def SetSingleCoil(self, index: int, addr: int, value: int) -> str:
        """
        写入单个线圈寄存器（V4.6.6新增指令）

        Args:
            index: 创建主站时返回的主站索引
            addr: 线圈寄存器地址
            value: 要写入的值，0或1

        Returns:
            str: ErrorID,{},SetSingleCoil(index,addr,value);
        """
        if value not in [0, 1]:
            raise ValueError("value 必须是 0 或 1")
        
        cmd = f"SetSingleCoil({index},{addr},{value})"
        return self._send_cmd(cmd)

    # ==================== 保持寄存器====================

    def GetHoldRegs(self, index: int, addr: int, count: int, val_type: str = "U16") -> str:
        """
        按照指定的数据类型，读取 Modbus 从站保持寄存器地址的值

        Args:
            index: 创建主站时返回的主站索引，最多支持个设备，取值范围：[0,4]
            addr: 保持寄存器起始地址
            count: 连续读取保持寄存器的值的数量
            val_type: 读取的数据类型
                      U16（6位无符号整数（2个字节，占用1个寄存器）；
                      U32（32位无符号整数（个字节，占用2个寄存器）；
                      F32（2位单精度浮点数（4个字节，占用2个寄存器）；
                      F64（4位双精度浮点数（8个字节，占用4个寄存器）；
                      默认值为 U16

        Returns:
            str: ErrorID,{value1,value2,...,valuen},GetHoldRegs(index,addr,count,valType);
        """
        if not 0 <= index <= 4:
            raise ValueError("index 取值范围必须是 [0, 4]")
        if val_type not in ["U16", "U32", "F32", "F64"]:
            raise ValueError("val_type 必须为'U16', 'U32', 'F32' 或 'F64'")
        
        cmd = f'GetHoldRegs({index},{addr},{count},"{val_type}")'
        return self._send_cmd(cmd)

    def SetHoldRegs(self, index: int, addr: int, count: int, 
                      val_tab: Union[List[int], str], val_type: str = "U16") -> str:
        """
        将指定的值以指定的数据类型写入Modbus 从站保持寄存器指定的地址

        Args:
            index: 创建主站时返回的主站索引，最多支持个设备，取值范围：[0,4]
            addr: 保持寄存器起始地址
            count: 连续写入保持寄存器的值的数量，取值范围：[1, 4]
            val_tab: 要写入的值，数量与count 相同
            val_type: 写入的数据类型
                      U16（6位无符号整数（2个字节，占用1个寄存器）；
                      U32（32位无符号整数（个字节，占用2个寄存器）；
                      F32（2位单精度浮点数（4个字节，占用2个寄存器）；
                      F64（4位双精度浮点数（8个字节，占用4个寄存器）；
                      默认值为 U16

        Returns:
            str: ErrorID,{},SetHoldRegs(index,addr,count,valTab,valType);
        """
        if not 0 <= index <= 4:
            raise ValueError("index 取值范围必须是 [0, 4]")
        if not 1 <= count <= 4:
            raise ValueError("count 取值范围必须是 [1, 4]")
        if val_type not in ["U16", "U32", "F32", "F64"]:
            raise ValueError("val_type 必须为'U16', 'U32', 'F32' 或 'F64'")
        
        if isinstance(val_tab, list):
            val_str = "{" + ",".join(str(v) for v in val_tab) + "}"
        else:
            val_str = val_tab
        
        cmd = f'SetHoldRegs({index},{addr},{count},{val_str},"{val_type}")'
        return self._send_cmd(cmd)

    def SetSingleHoldReg(self, index: int, addr: int, value: int) -> str:
        """
        写入单个保持寄存器（V4.6.6新增指令）

        Args:
            index: 创建主站时返回的主站索引，取值范围：[0, 4]
            addr: 保持寄存器地址
            value: 要写入的值

        Returns:
            str: ErrorID,{},SetSingleHoldReg(index,addr,value);
        """
        if not 0 <= index <= 4:
            raise ValueError("index 取值范围必须是 [0, 4]")
        
        cmd = f"SetSingleHoldReg({index},{addr},{value})"
        return self._send_cmd(cmd)

    # ==================== 总线寄存器- 输入寄存器====================

    def GetInputBool(self, address: int) -> str:
        """
        获取输入寄存器指定地址的bool 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 63]

        Returns:
            str: ErrorID,{value},GetInputBool(address);
                 value 表示指定的寄存器地址的值，为0 或 1
        """
        if not 0 <= address <= 63:
            raise ValueError("address 取值范围必须是 [0, 63]")
        
        return self._send_cmd(f"GetInputBool({address})")

    def GetInputInt(self, address: int) -> str:
        """
        获取输入寄存器指定地址的int 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 23]

        Returns:
            str: ErrorID,{value},GetInputInt(address);
                 value 表示指定的寄存器地址的值，为整型数（int32）
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"GetInputInt({address})")

    def GetInputFloat(self, address: int) -> str:
        """
        获取输入寄存器指定地址的float 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 23]

        Returns:
            str: ErrorID,{value},GetInputFloat(address);
                 value 表示指定的寄存器地址的值，为单精度浮点数（float）
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"GetInputFloat({address})")

    # ==================== 总线寄存器- 输出寄存器====================

    def GetOutputBool(self, address: int) -> str:
        """
        获取输出寄存器指定地址的bool 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 63]

        Returns:
            str: ErrorID,{value},GetOutputBool(address);
                 value 表示指定的寄存器地址的值，为0 或 1
        """
        if not 0 <= address <= 63:
            raise ValueError("address 取值范围必须是 [0, 63]")
        
        return self._send_cmd(f"GetOutputBool({address})")

    def GetOutputInt(self, address: int) -> str:
        """
        获取输出寄存器指定地址的int 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 23]

        Returns:
            str: ErrorID,{value},GetOutputInt(address);
                 value 表示指定的寄存器地址的值，为整型数（int32）
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"GetOutputInt({address})")

    def GetOutputFloat(self, address: int) -> str:
        """
        获取输出寄存器指定地址的float 类型的数据

        Args:
            address: 寄存器地址，取值范围：[0, 23]

        Returns:
            str: ErrorID,{value},GetOutputFloat(address);
                 value 表示指定的寄存器地址的值，为单精度浮点数（float）
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"GetOutputFloat({address})")

    def SetOutputBool(self, address: int, value: int) -> str:
        """
        设置输出寄存器指定地址的 bool 值

        Args:
            address: 寄存器地址，取值范围：[0, 63]
            value: 要设置的值，0 或 1

        Returns:
            str: ErrorID,{},SetOutputBool(address,value);
        """
        if not 0 <= address <= 63:
            raise ValueError("address 取值范围必须是 [0, 63]")
        if value not in [0, 1]:
            raise ValueError("value 必须为0 或 1")
        
        return self._send_cmd(f"SetOutputBool({address},{value})")

    def SetOutputInt(self, address: int, value: int) -> str:
        """
        设置输出寄存器指定地址的 int 值

        Args:
            address: 寄存器地址，取值范围：[0, 23]
            value: 要设置的 int32 值

        Returns:
            str: ErrorID,{},SetOutputInt(address,value);
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"SetOutputInt({address},{value})")

    def SetOutputFloat(self, address: int, value: float) -> str:
        """
        设置输出寄存器指定地址的 float 值

        Args:
            address: 寄存器地址，取值范围：[0, 23]
            value: 要设置的 float 值

        Returns:
            str: ErrorID,{},SetOutputFloat(address,value);
        """
        if not 0 <= address <= 23:
            raise ValueError("address 取值范围必须是 [0, 23]")
        
        return self._send_cmd(f"SetOutputFloat({address},{value})")


