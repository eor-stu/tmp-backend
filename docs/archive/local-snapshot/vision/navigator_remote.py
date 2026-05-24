"""
vision/navigator.py
Line-following navigation controller.

Consumes get_commands() output directly: [{action: "forward"|"turn", param: float}].
- "forward" param = Manhattan distance → number of intersections to pass
- "turn" param = angle → execute fixed turn at intersection

Mock modes:
    Camera unavailable → mock line following, auto-intersection every N ticks
    Car unavailable → mock motor control with console logging

State machine:
    FOLLOW_LINE → 检测到路口 → CROSSING（过路口）→ TURNING（转向）→ FOLLOW_LINE → ... → DONE
"""

import time
from enum import Enum, auto
from typing import Final

from src.logger import info, warning, error, debug
from src.vision.line_detector import LineDetector
from src.vision.pid_controller import PIDController
from src.vision.intersection_detector import IntersectionDetector
from src.car.LOBOROBOT import Robot


# Calibration constants (measure on real hardware)
INTERSECTION_FORWARD_TIME: Final[float] = 1.4   # seconds to cross intersection center (~30cm @ V=0.215m/s)
LINE_FOLLOW_BASE_SPEED: Final[int] = 20          # base motor speed (0-100)
INTERSECTION_COOLDOWN: Final[float] = 2.0        # seconds to ignore after handling intersection
TURN_SPEED: Final[int] = 30                      # motor speed for turning (0-100)
TURN_LINE_CENTER_THRESHOLD: Final[float] = 0.15  # early-stop when |dev| below this during turn
LOG_INTERVAL: Final[int] = 30                    # log every N frames during line following

# Mock mode constants
MOCK_INTERSECTION_TICKS: Final[int] = 100        # ticks between auto-intersections in mock mode


class NavState(Enum):
    """Navigation state machine states."""
    IDLE = auto()
    FOLLOW_LINE = auto()
    CROSSING = auto()
    TURNING = auto()
    DONE = auto()
    STOPPED = auto()


class Navigator:
    """
    Line-following navigator that directly executes get_commands() output.

    Supports offline mock modes when camera or car hardware is unavailable.

    Usage:
        from src.map import get_commands

        nav = Navigator()
        commands = get_commands("entrance", "pharmacy")
        nav.set_commands(commands)
        nav.run()
    """

    def __init__(self, camera_id: int = 0):
        self._line_detector = LineDetector(camera_id=camera_id)
        self._pid = PIDController()
        self._intersection_detector = IntersectionDetector()

        self._commands: list[dict] = []         # [{action, param}]
        self._cmd_idx: int = 0                  # current command index
        self._intersections_passed: int = 0     # intersections passed in current forward segment
        self._intersections_target: int = 0     # how many to pass before next turn
        self._state = NavState.IDLE
        self._last_intersection_time: float = 0.0
        self._frame_count: int = 0              # total frames processed
        self._tick_count: int = 0               # ticks in current state
        self._start_time: float = 0.0           # navigation start timestamp
        self._turn_duration: float = 0.0         # calibrated turn duration (set at turn start)

        # Mock mode flags
        self._camera_mock: bool = False
        self._car_mock: bool = not Robot.is_available

    def set_commands(self, commands: list[dict]) -> None:
        """
        Set commands from get_commands() output.

        Args:
            commands: [{action: "forward"|"turn", param: float}]
                      forward param = Manhattan distance (1.0 = one edge = one intersection)
                      turn param = angle in degrees (positive = right, negative = left)
        """
        self._commands = commands
        self._cmd_idx = 0
        self._state = NavState.IDLE
        info(f"[Navigator] Commands set: {commands}")

    def _prepare_next_forward(self) -> bool:
        """
        Set up the next forward segment by counting intersections to pass.

        Returns:
            True if there's a forward segment to execute, False if no more commands.
        """
        self._intersections_passed = 0
        self._intersections_target = 0

        # Count intersections from consecutive forward commands
        while self._cmd_idx < len(self._commands):
            cmd = self._commands[self._cmd_idx]
            if cmd["action"] == "forward":
                # Each 1.0 Manhattan distance = one edge = one intersection to pass
                self._intersections_target += int(round(cmd["param"]))
                self._cmd_idx += 1
            else:
                break

        return self._intersections_target > 0

    # ------------------------------------------------------------------
    # Motor control helpers (mock-aware)
    # ------------------------------------------------------------------

    def _motor_forward(self, speed: int) -> None:
        """Move all motors forward. Logs mock output if hardware unavailable."""
        if self._car_mock:
            info(f"[MockCar] ▲ 前进 speed={speed}")
        else:
            Robot._bot.t_up(speed)

    def _motor_turn_left(self, speed: int) -> None:
        """Turn left. Logs mock output if hardware unavailable."""
        if self._car_mock:
            info(f"[MockCar] ↺ 左转 speed={speed}")
        else:
            Robot._bot.turnLeft(speed)

    def _motor_turn_right(self, speed: int) -> None:
        """Turn right. Logs mock output if hardware unavailable."""
        if self._car_mock:
            info(f"[MockCar] ↻ 右转 speed={speed}")
        else:
            Robot._bot.turnRight(speed)

    def _motor_stop(self) -> None:
        """Stop all motors. Logs mock output if hardware unavailable."""
        if self._car_mock:
            info(f"[MockCar] ■ 停止")
        else:
            Robot.stop()

    def _set_differential_speed(self, left: int, right: int) -> None:
        """Set left/right motor speeds for differential steering."""
        if self._car_mock:
            if self._frame_count % LOG_INTERVAL == 0:
                info(f"[MockCar] ◇ 差速 L={left} R={right}")
        else:
            Robot._bot.MotorRun(0, 'forward', left)
            Robot._bot.MotorRun(1, 'forward', left)
            Robot._bot.MotorRun(2, 'forward', right)
            Robot._bot.MotorRun(3, 'forward', right)

    # ------------------------------------------------------------------
    # Navigation lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Emergency stop."""
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0
        info(f"[Navigator] ===== 紧急停止 =====")
        info(f"[Navigator] 状态={self._state.name}, 帧数={self._frame_count}, "
             f"耗时={elapsed:.1f}s, 指令进度={self._cmd_idx}/{len(self._commands)}")
        self._state = NavState.STOPPED
        self._motor_stop()
        if not self._camera_mock:
            self._line_detector.close()

    def run(self) -> None:
        """
        Main navigation loop. Blocks until all commands are executed or stopped.

        Executes get_commands() sequence:
            forward N → 巡线经过 N 个路口
            turn ±90 → 路口固定转向
        """
        if not self._commands:
            warning("[Navigator] No commands set")
            return

        # Try to open camera; fall back to mock mode
        if not self._line_detector.open():
            warning("[Navigator] 摄像头不可用, 进入 mock 巡线模式")
            self._camera_mock = True

        # Prepare first forward segment
        if not self._prepare_next_forward():
            warning("[Navigator] No forward commands at start")
            if not self._camera_mock:
                self._line_detector.close()
            return

        self._state = NavState.FOLLOW_LINE
        self._pid.reset()
        self._intersection_detector.reset()
        self._last_intersection_time = 0.0
        self._frame_count = 0
        self._tick_count = 0
        self._start_time = time.time()

        info(f"[Navigator] ===== 启动导航 =====")
        info(f"[Navigator] 总指令数: {len(self._commands)}, 首段路口数: {self._intersections_target}")
        info(f"[Navigator] 指令序列: {self._commands}")
        info(f"[Navigator] 标定参数: base_speed={LINE_FOLLOW_BASE_SPEED}, "
             f"cross_time={INTERSECTION_FORWARD_TIME}s, "
             f"turn_mode=adaptive, turn_speed={TURN_SPEED}, "
             f"turn_center_thresh={TURN_LINE_CENTER_THRESHOLD}")
        info(f"[Navigator] 设备状态: 摄像头={'MOCK' if self._camera_mock else 'OK'}, "
             f"底盘={'MOCK' if self._car_mock else 'OK'}")
        info(f"[Navigator] ====================")

        try:
            while self._state not in (NavState.DONE, NavState.STOPPED):
                self._tick()
        except KeyboardInterrupt:
            elapsed = time.time() - self._start_time
            info(f"[Navigator] 用户中断, 帧数={self._frame_count}, 耗时={elapsed:.1f}s")
        finally:
            self._motor_stop()
            if not self._camera_mock:
                self._line_detector.close()

    def _tick(self) -> None:
        """Single iteration of the navigation loop."""
        if self._state == NavState.FOLLOW_LINE:
            self._tick_follow_line()
        elif self._state == NavState.CROSSING:
            self._tick_crossing()
        elif self._state == NavState.TURNING:
            self._tick_turning()

    def _tick_follow_line(self) -> None:
        """Follow the black line, check for intersections."""
        self._frame_count += 1
        self._tick_count += 1

        if self._camera_mock:
            self._tick_follow_line_mock()
        else:
            self._tick_follow_line_real()

    def _tick_follow_line_mock(self) -> None:
        """Mock line following: simulate intersection every MOCK_INTERSECTION_TICKS ticks."""
        # Simulate a centered line with no deviation
        deviation = 0.0
        left_speed, right_speed = self._pid.compute(deviation)
        self._set_differential_speed(left_speed, right_speed)

        # Auto-detect intersection at fixed tick intervals
        if self._tick_count >= MOCK_INTERSECTION_TICKS:
            self._motor_stop()
            self._state = NavState.CROSSING
            self._intersections_passed += 1
            elapsed = time.time() - self._start_time
            info(f"[Navigator] [Mock] >>> 模拟路口! "
                 f"路口进度: {self._intersections_passed}/{self._intersections_target}, "
                 f"指令进度: {self._cmd_idx}/{len(self._commands)}, "
                 f"已运行: {elapsed:.1f}s")
            self._tick_count = 0

        # Periodic log
        if self._frame_count % LOG_INTERVAL == 0:
            elapsed = time.time() - self._start_time
            debug(f"[Navigator] [Mock巡线] frame={self._frame_count} "
                  f"tick={self._tick_count}/{MOCK_INTERSECTION_TICKS} "
                  f"路口={self._intersections_passed}/{self._intersections_target} "
                  f"指令={self._cmd_idx}/{len(self._commands)} "
                  f"耗时={elapsed:.1f}s")

    def _tick_follow_line_real(self) -> None:
        """Real camera line following with intersection detection."""
        frame = self._line_detector.read_frame()
        if frame is None:
            return

        deviation, line_detected, binary = self._line_detector.detect_with_binary(frame)

        # Check for intersection (with cooldown)
        now = time.time()
        if now - self._last_intersection_time > INTERSECTION_COOLDOWN:
            at_intersection = self._intersection_detector.detect(
                binary, deviation, line_detected
            )
            if at_intersection:
                self._motor_stop()
                self._state = NavState.CROSSING
                self._intersections_passed += 1
                elapsed = now - self._start_time
                info(f"[Navigator] >>> 检测到路口! "
                     f"路口进度: {self._intersections_passed}/{self._intersections_target}, "
                     f"指令进度: {self._cmd_idx}/{len(self._commands)}, "
                     f"已运行: {elapsed:.1f}s")
                self._tick_count = 0
                return

        # PID line following
        left_speed, right_speed = self._pid.compute(deviation)
        self._set_differential_speed(left_speed, right_speed)

        # Periodic runtime log
        if self._frame_count % LOG_INTERVAL == 0:
            elapsed = now - self._start_time
            debug(f"[Navigator] [巡线] frame={self._frame_count} "
                  f"偏差={deviation:+.3f} 检线={'Y' if line_detected else 'N'} "
                  f"电机L={left_speed} R={right_speed} "
                  f"路口={self._intersections_passed}/{self._intersections_target} "
                  f"指令={self._cmd_idx}/{len(self._commands)} "
                  f"耗时={elapsed:.1f}s")

    def _tick_crossing(self) -> None:
        """
        Cross through intersection with fixed forward movement.
        Then decide: more intersections in this segment → continue,
        or next command is a turn → execute turn, or done.
        """
        info(f"[Navigator] [过路口] 直行 {INTERSECTION_FORWARD_TIME}s, "
             f"速度={LINE_FOLLOW_BASE_SPEED}")

        # Move forward to cross intersection center
        self._motor_forward(LINE_FOLLOW_BASE_SPEED)
        time.sleep(INTERSECTION_FORWARD_TIME)
        self._motor_stop()
        self._last_intersection_time = time.time()

        # Check if we've passed enough intersections for current forward segment
        if self._intersections_passed < self._intersections_target:
            # More intersections to pass in this segment
            info(f"[Navigator] [过路口] 还需经过 {self._intersections_target - self._intersections_passed} 个路口")
            self._intersection_detector.reset()
            self._pid.reset()
            self._state = NavState.FOLLOW_LINE
            self._tick_count = 0
            return

        # Forward segment complete — look for next turn command
        turn_angle = self._get_next_turn()

        if turn_angle is None:
            # No more commands — done
            self._state = NavState.DONE
            elapsed = time.time() - self._start_time
            info(f"[Navigator] ===== 导航完成 =====")
            info(f"[Navigator] 总帧数: {self._frame_count}, 总耗时: {elapsed:.1f}s")
            return

        # Execute turn
        self._pending_turn_angle = turn_angle
        self._state = NavState.TURNING
        info(f"[Navigator] [过路口] 段完成, 准备转向: {turn_angle}°")

    def _get_next_turn(self) -> float | None:
        """
        Consume the next turn command from the command list.

        Returns:
            Turn angle (positive = right, negative = left), or None if no more turns.
        """
        while self._cmd_idx < len(self._commands):
            cmd = self._commands[self._cmd_idx]
            if cmd["action"] == "turn":
                self._cmd_idx += 1
                return cmd["param"]
            elif cmd["action"] == "forward":
                # Next forward segment — prepare it and return None (no turn needed yet)
                self._prepare_next_forward()
                return None
        return None

    def _tick_turning(self) -> None:
        """Fixed-angle turn at intersection, with optional early-stop on line center."""
        angle = self._pending_turn_angle
        turn_right = angle > 0

        # First tick: calculate duration and start motors
        if self._tick_count == 0:
            # V_ROTATE = 96 deg/s @ speed=30, proportional to TURN_SPEED
            rate = (TURN_SPEED / 30.0) * 96.0
            self._turn_duration = abs(angle) / rate
            direction = "right" if turn_right else "left"
            info(f"[Navigator] [转向] {direction} {abs(angle)}° "
                 f"速度={TURN_SPEED}, 基准={self._turn_duration:.2f}s")

            if turn_right:
                self._motor_turn_right(TURN_SPEED)
            else:
                self._motor_turn_left(TURN_SPEED)

        self._tick_count += 1

        # Optional early-stop: check if line is centered
        if not self._camera_mock:
            frame = self._line_detector.read_frame()
            if frame is not None:
                deviation, detected, _ = self._line_detector.detect_with_binary(frame)
                if self._tick_count % 10 == 0:
                    debug(f"[Navigator] [转向] tick={self._tick_count} "
                          f"dev={deviation:+.3f} detected={detected}")
                if detected and self._tick_count > 10 and abs(deviation) < TURN_LINE_CENTER_THRESHOLD:
                    self._motor_stop()
                    info(f"[Navigator] [转向] 线居中提前停止 (dev={deviation:+.3f}, "
                         f"ticks={self._tick_count})")
                    self._finish_turn()
                    return

        # Stop when calibrated duration expires
        if self._tick_count * 0.033 >= self._turn_duration:  # ~30fps per tick
            self._motor_stop()
            info(f"[Navigator] [转向] 完成 (ticks={self._tick_count}, "
                 f"{self._turn_duration:.2f}s)")
            self._finish_turn()

    def _finish_turn(self) -> None:
        """Transition out of turning state to next forward segment or done."""
        self._last_intersection_time = time.time()
        has_next = self._prepare_next_forward()
        self._intersection_detector.reset()
        self._pid.reset()
        self._tick_count = 0

        if has_next:
            self._state = NavState.FOLLOW_LINE
            info(f"[Navigator] [转向] 完成, 下一段: {self._intersections_target} 个路口")
        else:
            self._state = NavState.DONE
            elapsed = time.time() - self._start_time
            info(f"[Navigator] ===== 导航完成 =====")
            info(f"[Navigator] 总帧数: {self._frame_count}, 总耗时: {elapsed:.1f}s")
