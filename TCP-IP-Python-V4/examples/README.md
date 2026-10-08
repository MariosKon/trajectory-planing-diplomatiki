# 示例代码说明

本目录包含DOBOT SDK的示例代码，按功能分类：

## 示例列表

| 序号 | 文件 | 功能描述 |
|:---:|------|----------|
| 00 | `00_logging_demo.py` | 日志系统演示 |
| 01 | `01_basic_connection.py` | 基础连接和使能 |
| 02 | `02_motion_control.py` | 运动控制（关节/直线/圆弧/整圆） |
| 03 | `03_error_monitor.py` | 错误码监控和状态查询 |
| 04 | `04_io_control.py` | IO控制（数字/模拟/末端IO） |
| 05 | `05_coordinate_system.py` | 坐标系设置（用户/工具坐标系） |
| 06 | `06_force_and_conveyor.py` | 力控和传送带 |
| 07 | `07_status_monitor.py` | 状态监控 |
| 08 | `08_multi_thread_control.py` | 多线程控制 |

## 运行示例

```bash
# 运行基础连接示例
python examples/01_basic_connection.py

# 运行运动控制示例
python examples/02_motion_control.py

# 运行错误监控示例
python examples/03_error_monitor.py

# 运行IO控制示例
python examples/04_io_control.py

# 运行坐标系设置示例
python examples/05_coordinate_system.py

# 运行力控和传送带示例
python examples/06_force_and_conveyor.py

# 运行状态监控示例
python examples/07_status_monitor.py

# 运行多线程控制示例
python examples/08_multi_thread_control.py
```

## 使用注意事项

1. **修改IP地址**：每个示例文件开头都有 `ROBOT_IP` 变量，请根据实际机器人IP修改
2. **安全第一**：运行运动示例前，请确保机器人周围有足够安全空间
3. **TCP模式**：确保机器人已切换到TCP/IP控制模式
4. **依赖安装**：确保已安装必要依赖
   ```bash
   pip install numpy requests
   ```

## 示例结构说明

所有示例遵循统一的结构模式：

```python
from dobot_sdk import DobotRobot

def main():
    ROBOT_IP = "192.168.1.100"
    
    try:
        with DobotRobot(ROBOT_IP) as robot:
            # 1. 请求控制模式
            robot.robot_control.RequestControl()
            
            # 2. 清除报警
            robot.robot_control.ClearError()
            
            # 3. 使能机器人
            robot.robot_control.EnableRobot(load=1.0)
            
            # 4. 执行操作...
            # ...
            
            # 5. 下使能
            robot.robot_control.DisableRobot()
            
    except Exception as e:
        print(f"错误: {e}")
```

## 模块说明

| 模块 | 说明 |
|------|------|
| `robot.robot_control` | 基础控制（使能、模式、坐标系、状态查询） |
| `robot.motion` | 运动控制（MovJ/MovL/Arc/Circle等） |
| `robot.io` | IO控制（数字/模拟输入输出） |
| `robot.communication` | 通信控制（寄存器操作） |
| `robot.plugins` | 插件模块（力控、传送带） |
