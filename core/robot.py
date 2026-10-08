import time

def response_code(response):
    try:
        return int(str(response).split(",", 1)[0].strip())
    except (ValueError, TypeError):
        return None

def check_response(response):
    code = response_code(response)
    if code is not None and code != 0:
        raise RuntimeError(f"Robot rejected command: {response}")
    return response

def robot_mode(robot):
    response = robot.robot_control.RobotMode()
    try:
        return int(
            response.split("{", 1)[1].split("}", 1)[0].split(",")[0]
        )
    except (ValueError, IndexError):
        raise RuntimeError(f"Unexpected RobotMode: {response}")

def wait_for_motion(robot, timeout_s=60.0, poll_s=0.1):
    deadline = time.perf_counter() + timeout_s
    idle_count = 0
    while time.perf_counter() < deadline:
        mode = robot_mode(robot)
        if mode == 9:
            raise RuntimeError("Robot entered error mode")
        if mode == 5:
            idle_count += 1
            if idle_count >= 2:
                return
        else:
            idle_count = 0
        time.sleep(poll_s)
    raise TimeoutError("Robot motion timeout")

def slow_move(robot, target, coordinate_type, cfg, speed=None, acceleration=None):
    response = check_response(robot.motion.MovJ(
        target, coordinate_type,
        a=acceleration or cfg.slow_acceleration,
        v=speed or cfg.slow_speed,
    ))
    wait_for_motion(robot, cfg.motion_timeout_s)
    return response
