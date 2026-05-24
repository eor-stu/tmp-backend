"""
vision/navigator.py
Line-following navigation controller.

Consumes get_commands() output directly: [{action: "forward"|"turn", param: float}].
- "forward" param = Manhattan distance → number of intersections to pass
- "turn" param = angle → execute fixed turn at intersection

Mock modes:
    Camera unavailable → mock line following, auto-intersection every N ticks
    Car unavailable → mock motor control with time.sleep(2) for cross/turn phases

State machine:
    FOLLOW_LINE → 检测到路口 → CROSSING（过路口）→ TURNING（转向）→ FOLLOW_LINE → ... → DONE
    FOLLOW_LINE → 上半画面连续丢线 → DONE（到达终点）

TODO: get_commands() design needs refactoring (tracked separately)
"""

import time
from enum import Enum, auto
from typing import Final

from src.logger import info, warning, error, debug
from src.vision.line_detector import LineDetector
from src.vision.pid_controller import PIDController
from src.vision.intersection_detector import IntersectionDetector
from src.car.LOBOROBOT import Robot
from src.car.control import forward, turn, stop as car_stop


# Calibration constants
LINE_FOLLOW_BASE_SPEED: Final[int] = 20          # base motor speed (0-100)
TURN_SPEED: Final[int] = 30                      # motor speed for turning (0-100)
LOG_INTERVAL: Final[int] = 30                    # log every N frames during line following

# Intersection handling
FORWARD_DISTANCE: Final[float] = 0.1             # meters to push through intersection
INTERSECTION_COOLDOWN: Final[float] = 2.0        # seconds to ignore after handling intersection

# Endpoint detection
UPPER_LOSS_CONFIRM: Final[int] = 3               # consecutive frames with no line in upper portion

# Mock mode
MOCK_INTERSECTION_TICKS: Final[int] = 100        # ticks between auto-intersections in mock mode
MOCK_PHASE_SLEEP: Final[float] = 2.0             # seconds to sleep during cross/turn in mock mode


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

        # Endpoint detection
        self._upper_loss_count: int = 0
        self._pending_turn_angle: float = 0.0

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

        while self._cmd_idx < len(self._commands):
            cmd = self._commands[self._cmd_idx]
            if cmd["action"] == "forward":
                self._intersections_target += int(round(cmd["param"]))
                self._cmd_idx += 1
            else:
                break

        return self._intersections_target > 0

    # ------------------------------------------------------------------
    # Motor control (mock-aware)
    # ------------------------------------------------------------------

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
        car_stop()
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

        if not self._line_detector.open():
            warning("[Navigator] 摄像头不可用, 进入 mock 巡线模式")
            self._camera_mock = True
            self._car_mock = True

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
        self._upper_loss_count = 0
        self._start_time = time.time()

        info(f"[Navigator] ===== 启动导航 =====")
        info(f"[Navigator] 总指令数: {len(self._commands)}, 首段路口数: {self._intersections_target}")
        info(f"[Navigator] 指令序列: {self._commands}")
        info(f"[Navigator] 参数: base_speed={LINE_FOLLOW_BASE_SPEED}, "
             f"cross_distance={FORWARD_DISTANCE}m, turn_speed={TURN_SPEED}")
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
            car_stop()
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
        """Follow the black line, check for intersections and endpoint."""
        self._frame_count += 1
        self._tick_count += 1

        if self._camera_mock:
            self._tick_follow_line_mock()
        else:
            self._tick_follow_line_real()

    def _tick_follow_line_mock(self) -> None:
        """Mock line following: simulate intersection every MOCK_INTERSECTION_TICKS ticks."""
        deviation = 0.0
        left_speed, right_speed = self._pid.compute(deviation, line_detected=True)
        self._set_differential_speed(left_speed, right_speed)

        if self._tick_count >= MOCK_INTERSECTION_TICKS:
            car_stop()
            self._state = NavState.CROSSING
            self._intersections_passed += 1
            elapsed = time.time() - self._start_time
            info(f"[Navigator] [Mock] >>> 模拟路口! "
                 f"路口进度: {self._intersections_passed}/{self._intersections_target}, "
                 f"指令进度: {self._cmd_idx}/{len(self._commands)}, "
                 f"已运行: {elapsed:.1f}s")
            self._tick_count = 0

        if self._frame_count % LOG_INTERVAL == 0:
            elapsed = time.time() - self._start_time
            debug(f"[Navigator] [Mock巡线] frame={self._frame_count} "
                  f"tick={self._tick_count}/{MOCK_INTERSECTION_TICKS} "
                  f"路口={self._intersections_passed}/{self._intersections_target} "
                  f"指令={self._cmd_idx}/{len(self._commands)} "
                  f"耗时={elapsed:.1f}s")

    def _tick_follow_line_real(self) -> None:
        """Real camera line following with intersection and endpoint detection."""
        frame = self._line_detector.read_frame()
        if frame is None:
            return

        deviation, detected, binary = self._line_detector.detect(frame)
        if binary is None:
            return

        # Endpoint detection: upper 40% loses line → destination reached
        line_in_upper = self._line_detector.detect_upper(frame)
        if not line_in_upper:
            self._upper_loss_count += 1
            if self._upper_loss_count >= UPPER_LOSS_CONFIRM:
                car_stop()
                self._state = NavState.DONE
                elapsed = time.time() - self._start_time
                info(f"[Navigator] >>> 检测到终点! (上半画面连续{self._upper_loss_count}帧无黑线)")
                info(f"[Navigator] ===== 导航完成 =====")
                info(f"[Navigator] 总帧数: {self._frame_count}, 总耗时: {elapsed:.1f}s")
                return
        else:
            self._upper_loss_count = 0

        # Intersection detection (with cooldown)
        now = time.time()
        if now - self._last_intersection_time > INTERSECTION_COOLDOWN:
            at_intersection = self._intersection_detector.detect(
                binary, deviation, detected
            )
            if at_intersection:
                car_stop()
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
        left_speed, right_speed = self._pid.compute(deviation, detected)
        self._set_differential_speed(left_speed, right_speed)

        if self._frame_count % LOG_INTERVAL == 0:
            elapsed = now - self._start_time
            debug(f"[Navigator] [巡线] frame={self._frame_count} "
                  f"偏差={deviation:+.3f} 检线={'Y' if detected else 'N'} "
                  f"电机L={left_speed} R={right_speed} "
                  f"路口={self._intersections_passed}/{self._intersections_target} "
                  f"指令={self._cmd_idx}/{len(self._commands)} "
                  f"耗时={elapsed:.1f}s")

    def _tick_crossing(self) -> None:
        """
        Cross through intersection with calibrated forward movement.
        Then decide: more intersections → continue, next command is turn → execute, or done.
        """
        info(f"[Navigator] [过路口] 直行 {FORWARD_DISTANCE}m")

        forward(FORWARD_DISTANCE)
        if self._car_mock:
            time.sleep(MOCK_PHASE_SLEEP)

        self._last_intersection_time = time.time()

        # Check if more intersections to pass in this segment
        if self._intersections_passed < self._intersections_target:
            info(f"[Navigator] [过路口] 还需经过 {self._intersections_target - self._intersections_passed} 个路口")
            self._intersection_detector.reset()
            self._pid.reset()
            self._state = NavState.FOLLOW_LINE
            self._tick_count = 0
            return

        # Forward segment complete — look for next turn
        turn_angle = self._get_next_turn()

        if turn_angle is None:
            self._state = NavState.DONE
            elapsed = time.time() - self._start_time
            info(f"[Navigator] ===== 导航完成 =====")
            info(f"[Navigator] 总帧数: {self._frame_count}, 总耗时: {elapsed:.1f}s")
            return

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
                self._prepare_next_forward()
                return None
        return None

    def _tick_turning(self) -> None:
        """Execute a calibrated-angle turn at intersection."""
        angle = self._pending_turn_angle

        if angle > 0:
            direction = "right"
        elif angle < 0:
            direction = "left"
        else:
            direction = "forward"

        info(f"[Navigator] [转向] {direction} {abs(angle)}°")

        turn(angle)
        if self._car_mock:
            time.sleep(MOCK_PHASE_SLEEP)

        self._last_intersection_time = time.time()

        # After turn, prepare next forward segment
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
