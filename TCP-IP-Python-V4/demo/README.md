# Demo 演示程序

本目录包含适配新SDK的机器人控制演示程序。

## 文件结构

```
demo/
├── DobotDemo.py      # 机器人控制核心类
├── main.py           # 基础演示入口
├── ui.py             # 图形化控制界面
├── main_UI.py        # UI界面入口
├── z_Cnv_test.py     # 传送带跟踪测试
├── z_servo_test.py   # 伺服动态跟随测试
└── README.md         # 说明文档
```

## 功能说明

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `main.py` | 基础连接和状态监控 | `python main.py` |
| `main_UI.py` | 图形化机器人控制界面 | `python main_UI.py` |
| `z_Cnv_test.py` | 传送带跟踪功能演示 | `python z_Cnv_test.py` |
| `z_servo_test.py` | ServoP动态轨迹跟随演示 | `python z_servo_test.py` |

## 使用前准备

1. **安装依赖**：确保已安装项目依赖
   ```bash
   pip install -r requirements.txt
   ```

2. **配置机器人IP**：修改各文件中的 `ROBOT_IP` 变量为实际机器人IP地址

3. **运行权限**：确保机器人已进入TCP控制模式

## 快速开始

### 方式一：命令行基础演示
```bash
cd demo
python main.py
```

### 方式二：图形化界面控制
```bash
cd demo
python main_UI.py
```

## 注意事项

1. 运行前请确保机器人已正确连接网络
2. 首次使用需请求TCP控制模式
3. 建议在安全区域内测试运动功能
4. 传送带测试需要硬件支持
