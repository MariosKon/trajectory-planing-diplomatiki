"""
UI界面主入口
"""

from ui import RobotUI

# 创建并运行机器人UI
if __name__ == "__main__":
    robot_ui = RobotUI(robot_ip="192.168.5.1")
    robot_ui.pack()
    robot_ui.mainloop()
