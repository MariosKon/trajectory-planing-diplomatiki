# -*- coding: utf-8 -*-
import sys
import time
import threading
import queue
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dobot_sdk import DobotRobot, CoordinateType, set_log_level
set_log_level('ERROR')  # 只显示ERROR级别日志


class RobotController:
    def __init__(self, ip):
        self.ip = ip
        self.robot = None
        self.running = False
        
        self.status_queue = queue.Queue(maxsize=10)
        self.monitor_thread = None
        self.latest_status = None
        self.status_lock = threading.Lock()
        self.last_printed_state = None  # 记录上次打印的状态
        
        # 状态统计
        self.status_combinations = {}
        self.abnormal_events = []
        self.motion_start_time = None
        self.total_motion_count = 0
    
    def _monitor_loop(self):
        """监听线程：持续接收并处理机器人状态反馈"""
        print("[INFO] 监听线程已启动，开始接收状态反馈...")
        while self.running:
            try:
                if not self.status_queue.empty():
                    status = self.status_queue.get(timeout=0.1)
                    with self.status_lock:
                        self.latest_status = status
                    self._process_status(status)
                time.sleep(0.005)  # 5ms间隔，降低CPU占用
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n[ERR] 监听线程异常: {str(e)}")
                break
        print("\n[INFO] 监听线程已停止")
    
    def _process_status(self, status):
        """处理状态数据，检测异常"""
        rs = status.running_status
        rm = status.robot_mode.value if hasattr(status.robot_mode, 'value') else status.robot_mode
        
        # 统计状态组合
        key = (rs, rm)
        self.status_combinations[key] = self.status_combinations.get(key, 0) + 1
        
        # 检测异常：运行模式下应该运动但实际空闲
        is_abnormal = (rm == 7 and rs == 0)
        if is_abnormal:
            self.abnormal_events.append({'time': time.time(), 'rs': rs, 'rm': rm})
        
        # 打印实时状态（仅状态变化时打印）
        self._print_status(status)
    
    def _print_status(self, status):
        """打印实时状态信息"""
        rs = status.running_status
        rm = status.robot_mode.value if hasattr(status.robot_mode, 'value') else status.robot_mode
        
        # 状态描述映射
        mode_desc = {
            1: "初始化",
            2: "手动",
            3: "自动",
            4: "远程",
            5: "空闲",
            6: "拖拽",
            7: "运行",
            9: "错误",
            10: "暂停",
            11: "点动"
        }
        
        # 只在状态变化时打印
        current_state = (rs, rm)
        if current_state != self.last_printed_state:
            self.last_printed_state = current_state
            status_text = "运动中" if rs != 0 else "空闲"
            status_color = "[RUN]" if rs != 0 else "[IDLE]"
            mode_text = mode_desc.get(rm, f"未知({rm})")
            pos = status.tool_vector_actual
            print(f"{status_color} RS:{status_text} | RM:{mode_text} | 速度:{status.speed_scaling:.0f}% | X:{pos.x:.1f} Y:{pos.y:.1f} Z:{pos.z:.1f}")
    
    def _wait_for_motion_complete(self, timeout=30):
        """等待运动完成"""
        print(f"[WAIT] 等待运动完成")
        start = time.time()
        
        # 等待运动开始
        while time.time() - start < 5:
            with self.status_lock:
                if self.latest_status and self.latest_status.running_status != 0:
                    break
            time.sleep(0.05)
        
        # 等待运动结束
        while time.time() - start < timeout:
            with self.status_lock:
                if self.latest_status and self.latest_status.running_status == 0:
                    # 获取关节角
                    q = self.latest_status.q_actual if self.latest_status else [0]*6
                    elapsed = time.time() - start
                    print(f"[OK] 运动完成: {elapsed:.2f}s | 关节角: J1={q[0]:.4f} J2={q[1]:.4f} J3={q[2]:.4f}")
                    return True
            time.sleep(0.05)
        
        return False
    
    def execute_point_by_point(self):
        """逐点运动测试 - 对比RS和RM状态的精度"""
        points = [
            [200, -200, 300, 180, 0, -180],
            [200, -200, 400, 180, 0, -180],
            [300, -200, 400, 180, 0, -180],
            [300, -100, 400, 180, 0, -180],
            [200, -200, 300, 180, 0, -180],
        ]
        
        print(f"\n逐点运动测试: {len(points)}个点")
        
        # 保存每个点在RM=7和RM=5状态下的关节角
        point_data = {tuple(p[:3]): {'rm7': [], 'rm5': []} for p in points}
        
        for idx, point in enumerate(points, 1):
            print(f"  [{idx}/{len(points)}] -> {point[:3]}")
            try:
                self.robot.motion.MovL(point, CoordinateType.CARTESIAN)
                self.total_motion_count += 1
                result = self._wait_for_motion_complete_with_joints(15)
                if result:
                    rm7_joints, rm5_joints = result
                    point_data[tuple(point[:3])]['rm7'].extend(rm7_joints)
                    if rm5_joints:
                        point_data[tuple(point[:3])]['rm5'].append(rm5_joints[-1])
                time.sleep(0.3)
            except Exception as e:
                print(f"    [ERR] {str(e)}")
                break
        
        # 对比精度
        print("\n" + "="*60)
        print("RS vs RM 精度对比")
        print("="*60)
        print(f"{'点':<15} {'RM=7时J1范围':<18} {'RM=5时J1范围':<18} {'结论'}")
        print("-"*60)
        
        for pos, data in point_data.items():
            rm7 = data['rm7']
            rm5 = data['rm5']
            
            if len(rm7) >= 2:
                rm7_j1 = [j[0] for j in rm7]
                rm7_range = f"{min(rm7_j1):.4f}~{max(rm7_j1):.4f}"
                rm7_diff = max(rm7_j1) - min(rm7_j1)
            else:
                rm7_range = "数据不足"
                rm7_diff = 0
            
            if len(rm5) >= 1:
                rm5_j1 = [j[0] for j in rm5]
                rm5_range = f"{min(rm5_j1):.4f}~{max(rm5_j1):.4f}"
                rm5_diff = max(rm5_j1) - min(rm5_j1) if len(rm5) > 1 else 0
            else:
                rm5_range = "数据不足"
                rm5_diff = 0
            
            conclusion = "RM=5更稳定" if rm7_diff > rm5_diff else "相近"
            print(f"{str(pos):<15} {rm7_range:<18} {rm5_range:<18} {conclusion}")
        
        print("\n完成: {0}次运动".format(self.total_motion_count))
    
    def _wait_for_motion_complete_with_joints(self, timeout=30):
        """等待运动完成，对比RS和RM状态的关节角精度"""
        start = time.time()
        
        # 等待运动开始
        while time.time() - start < 5:
            with self.status_lock:
                if self.latest_status and self.latest_status.running_status != 0:
                    break
            time.sleep(0.05)
        
        # 收集不同状态下的关节角
        rs0_rm7_joints = []  # RS=0, RM=7 状态
        rm5_joints = []      # RM=5 状态
        
        motion_ended = False
        while time.time() - start < timeout:
            with self.status_lock:
                if self.latest_status:
                    rs = self.latest_status.running_status
                    rm = self.latest_status.robot_mode
                    q = self.latest_status.joint_state.q_actual
                    
                    # 记录 RM=7 时 RS=0 的关节角（过渡状态）
                    if rs == 0 and rm == 7:
                        rs0_rm7_joints.append(q.copy())
                        motion_ended = True
                    
                    # 记录 RM=5 的关节角（稳定状态）
                    if rm == 5 and rs == 0:
                        rm5_joints.append(q.copy())
                        elapsed = time.time() - start
                        print(f"    [OK] {elapsed:.2f}s | J1={q[0]:.4f} J2={q[1]:.4f} J3={q[2]:.4f}")
                        return (rs0_rm7_joints, rm5_joints)
            time.sleep(0.05)
        
        return (rs0_rm7_joints, rm5_joints)
    
    def execute_validation(self):
        """状态验证测试"""
        print("\n" + "="*50)
        print("状态验证测试")
        print("="*50)
        
        test_point = [200, -200, 300, 180, 0, -180]
        print(f"\n时刻       RS   RM   状态           J1角度    稳定")
        print("-"*60)
        
        state_records = []
        start_time = time.time()
        
        try:
            response = self.robot.motion.MovL(test_point, CoordinateType.CARTESIAN)
            self.total_motion_count += 1
            
            stable_count = 0
            while stable_count < 50 and (time.time() - start_time) < 20:
                if not self.status_queue.empty():
                    status = self.status_queue.get(block=True, timeout=0.1)
                    rs = status.running_status if hasattr(status, 'running_status') else 0
                    rm = status.robot_mode if hasattr(status, 'robot_mode') else 0
                    j1 = status.q_actual[0] if hasattr(status, 'q_actual') and status.q_actual else 0
                    elapsed = time.time() - start_time
                    
                    state_desc = self._get_state_description(rs, rm)
                    is_stable = (rs == 0 and rm == 5)
                    
                    state_records.append({
                        'time': elapsed, 'rs': rs, 'rm': rm, 'j1': j1, 'stable': is_stable
                    })
                    
                    print(f"{elapsed:6.2f}s  {rs:<4} {rm:<4} {state_desc:<14} {j1:>8.3f}   {'[OK]' if is_stable else ''}")
                    
                    stable_count = stable_count + 1 if is_stable else 0
            
            # 分析
            print("\n状态持续时间:")
            state_durations = {}
            for i in range(len(state_records)-1):
                key = f"RS={state_records[i]['rs']},RM={state_records[i]['rm']}"
                dur = state_records[i+1]['time'] - state_records[i]['time']
                state_durations[key] = state_durations.get(key, 0) + dur
            
            for state, dur in sorted(state_durations.items(), key=lambda x: -x[1]):
                print(f"  {state:<15}: {dur*1000:>6.0f} ms")
            
            # 结论
            print("\n结论:")
            print("  RM=5时关节角稳定可靠")
            print("  RM=7时为过渡状态，关节角可能变化")
            
        except Exception as e:
            print(f"[ERR] {str(e)}")
    
    def _get_state_description(self, rs, rm):
        """获取状态描述"""
        rs_desc = "运动中" if rs != 0 else "空闲"
        rm_desc = {
            1: "初始化", 2: "手动", 3: "自动", 4: "远程", 5: "空闲",
            6: "拖拽", 7: "运行", 9: "错误", 10: "暂停", 11: "点动"
        }.get(rm, f"未知({rm})")
        return f"{rs_desc}/{rm_desc}"
    
    def execute_continuous(self):
        """连续快速运动测试"""
        point_a = [200, -200, 300, 180, 0, -180]
        point_b = [300, -100, 400, 180, 0, -180]
        
        print(f"\n{'='*50}")
        print(f"开始连续运动测试 (A ↔ B)")
        print(f"点A: {point_a}")
        print(f"点B: {point_b}")
        print(f"按 Ctrl+C 停止")
        print(f"{'='*50}")
        
        count = 0
        start_time = time.time()
        
        try:
            while self.running:
                target_point = point_a if count % 2 == 0 else point_b
                try:
                    self.robot.motion.MovL(target_point, CoordinateType.CARTESIAN)
                    self.total_motion_count += 1
                    
                    if count > 0 and count % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = count / elapsed if elapsed > 0 else 0
                        print(f"\r[MOVE] 已发送 {count} 个指令 | 速率: {rate:.1f} 指令/秒", end="", flush=True)
                    
                    count += 1
                    time.sleep(0.05)  # 50ms间隔
                    
                except Exception as e:
                    print(f"\n[ERR] 发送失败: {str(e)}")
                    time.sleep(0.5)
                    
        except KeyboardInterrupt:
            print("\n[STOP] 用户终止连续运动")
        
        elapsed = time.time() - start_time
        rate = count / elapsed if elapsed > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"连续运动测试停止")
        print(f"发送指令数: {count}")
        print(f"总耗时: {elapsed:.2f}s")
        print(f"平均速率: {rate:.2f} 指令/秒")
        print(f"{'='*50}")
    
    def _status_callback(self, status):
        """状态回调函数"""
        if self.running and not self.status_queue.full():
            try:
                self.status_queue.put(status, block=False)
            except queue.Full:
                # 队列满时丢弃最新数据
                pass
    
    def start(self):
        """启动控制器"""
        try:
            self.robot = DobotRobot(self.ip, connect_timeout=5.0, receive_timeout=10.0)
            self.robot.Connect()
            self.robot.robot_control.RequestControl()
            self.robot.robot_control.ClearError()
            self.robot.StartFeedbackMonitor(callback=self._status_callback)
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("[OK] 控制器启动完成")
            
        except Exception as e:
            print(f"[ERR] 启动失败: {str(e)}")
            self.stop()
            raise
    
    def stop(self):
        """停止控制器"""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        if self.robot:
            self.robot.StopFeedbackMonitor()
            try:
                self.robot.robot_control.DisableRobot()
            except:
                pass
            try:
                self.robot.Disconnect()
            except:
                pass
        
        # 打印总结报告
        self._print_summary()
        
        print("\n[OK] 控制器已完全停止")
    
    def _print_summary(self):
        """打印测试总结报告"""
        if self.abnormal_events or self.total_motion_count > 0:
            print(f"\n[总结] 运动: {self.total_motion_count}次 | 异常: {len(self.abnormal_events)}次")
        
        print("\n" + "="*50)


def main(enable_motion=False, motion_type='point_by_point'):
    """主函数"""
    ROBOT_IP = "192.168.5.1"
    controller = RobotController(ROBOT_IP)
    
    try:
        controller.start()
        time.sleep(1)
        
        # 主线程：发送控制指令
        print("\n" + "-"*50)
        # 上电、使能、设置速度
        controller.robot.robot_control.PowerOn()
        controller.robot.robot_control.EnableRobot(load=1.0)
        controller.robot.robot_control.SpeedFactor(30)
        
        # 运动测试
        if enable_motion:
            print("\n开始运动测试")
            if motion_type == 'point_by_point':
                controller.execute_point_by_point()
            elif motion_type == 'continuous':
                controller.execute_continuous()
            elif motion_type == 'validation':
                controller.execute_validation()
        else:
            while True:
                time.sleep(0.1)
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[ERR] {str(e)}")
    finally:
        controller.stop()


if __name__ == "__main__":
    ENABLE_MOTION = True
    MOTION_TYPE = 'point_by_point'  # validation / point_by_point / continuous
    main(enable_motion=ENABLE_MOTION, motion_type=MOTION_TYPE)
