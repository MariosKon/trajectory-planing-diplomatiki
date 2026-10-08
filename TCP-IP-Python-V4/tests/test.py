from dobot_sdk import DobotRobot,CoordinateType
# from dobot_sdk.api.motion import CoordinateType
import time

with DobotRobot("192.168.5.1") as robot:
    robot.robot_control.RequestControl()
    robot.robot_control.EnableRobot()

    # p1=[-200, -70, 400, -180, 0, -180]
    # p2=[-200, -100, 400, -180, 0, -180]
    p1=[-200, -70, 400, -180, 0, -180]
    p2=[-8.7346, -27.2151, 83.8642, 33.3090, -89.7513, -98.6253]   

    # 笛卡尔空间运动
    robot.motion.MovJ(
        pose=p1,
        coord_type=CoordinateType.CARTESIAN
    )
    robot.motion.MovJ(
        pose=p2,
        coord_type=CoordinateType.JOINT
    )    

    # 直线运动
    robot.motion.MovL(
        pose=p1,
        coord_type=CoordinateType.CARTESIAN
    )    
    robot.motion.MovL(
        pose=p2,
        coord_type=CoordinateType.JOINT
    )

        # 数字输出
    robot.io.DO(4, 1)    # 打开DO4
    time.sleep(10)
    robot.io.DO(4, 0)   # 关闭DO4

    # 读取输入
    di_status = robot.io.DI(6)  # 读取DI1
    print(di_status)