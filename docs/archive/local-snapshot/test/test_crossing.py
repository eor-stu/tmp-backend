#!/usr/bin/env python3
"""
十字路口穿越 + 自适应转向 + 巡线测试脚本。

用法:
    source ./venv/bin/activate
    python -m test.test_crossing --turn right   # 右转
    python -m test.test_crossing --turn left    # 左转

功能:
    1. 巡线直到检测到第一个十字路口
    2. 穿越路口中心（直行，提速以完整越过）
    3. 实时检线自适应转向 — 转到黑线居中才停
    4. 转向后恢复巡线一小段（确认路线识别正常）
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

from src.vision.line_detector import LineDetector
from src.vision.pid_controller import PIDController
from src.vision.intersection_detector import IntersectionDetector
from src.car.LOBOROBOT import Robot

# ── 穿越参数 ──
CROSS_SPEED = 30              # 穿越路口直行速度
CROSS_TIME = 1.2              # 穿越直行时长（秒）→ ~25cm @ V=0.215m/s

# ── 转向参数 ──
TURN_SPEED = 30               # 转向速度 (标定: V_ROTATE=96 deg/s)
TURN_ANGLE = 90               # 固定转向角度（度）
TURN_LINE_CENTER = 0.15       # 提前停止阈值 — 偏差绝对值在此以内即停（可选）

# ── 巡线参数 ──
LINE_FOLLOW_BASE_SPEED = 20
POST_TURN_LINE_FOLLOW = 2.0

# ── 其他 ──
CAMERA_ID = 0
TIMEOUT = 30.0


def _turn(detector: LineDetector, turn_right: bool, speed: int, angle: float) -> tuple[float, float]:
    """
    固定角度转向 + 线居中提前停止。

    按标定数据 V_ROTATE=96 deg/s @ speed=30 计算基准时长。
    旋转期间读取摄像头，若线居中（|dev| < TURN_LINE_CENTER）则提前停止。
    基准时长到达后强制停止。

    Returns:
        (duration_s, final_deviation)
    """
    car_ok = Robot.is_available
    # 标定: V_ROTATE = 96 deg/s @ speed=30, 转速正比于 speed
    rate = (speed / 30.0) * 96.0
    base_duration = angle / rate

    print(f"  [转向] {'右' if turn_right else '左'}转 {angle}° "
          f"基准={base_duration:.2f}s (速率={rate:.0f} deg/s)")

    if car_ok:
        if turn_right:
            Robot._bot.turnRight(speed)
        else:
            Robot._bot.turnLeft(speed)

    start = time.time()
    frames = 0
    final_dev = 0.0

    try:
        while time.time() - start < base_duration:
            raw = detector.read_frame()
            frames += 1
            if raw is None:
                time.sleep(0.01)
                continue

            deviation, detected, _ = detector.detect_with_binary(raw)
            final_dev = deviation

            # 提前停止：线居中
            if detected and abs(deviation) < TURN_LINE_CENTER:
                elapsed = time.time() - start
                print(f"  [转向] 线居中提前停止 (dev={deviation:+.3f}, "
                      f"{elapsed:.2f}s/{base_duration:.2f}s, frames={frames})")
                Robot.stop()
                return elapsed, deviation

        # 基准时长到达
        Robot.stop()
        elapsed = time.time() - start
        print(f"  [转向] 基准时长到达 ({elapsed:.2f}s, frames={frames}, "
              f"final dev={final_dev:+.3f})")
        return elapsed, final_dev

    except Exception:
        Robot.stop()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="路口穿越 + 自适应转向 + 巡线测试")
    parser.add_argument("--turn", type=str, default="right",
                        choices=["right", "left"], help="转向方向 (默认 right)")
    args = parser.parse_args()

    turn_right = args.turn == "right"
    direction = "右转" if turn_right else "左转"

    detector = LineDetector(camera_id=CAMERA_ID)
    if not detector.open():
        print("[FAIL] 摄像头打开失败")
        return

    pid = PIDController()
    inter = IntersectionDetector()
    pid.reset()
    inter.reset()

    car_ok = Robot.is_available
    print(f"[INFO] 底盘: {'OK' if car_ok else 'MOCK'}")
    print(f"[INFO] 转向模式: 自适应 ({direction})")
    print(f"[INFO] 穿越: {CROSS_TIME}s @ speed={CROSS_SPEED}")
    print(f"[INFO] 转向后巡线: {POST_TURN_LINE_FOLLOW}s")
    print()

    frame_count = 0
    start = time.time()
    phase = "line_follow"

    try:
        while time.time() - start < TIMEOUT:
            raw = detector.read_frame()
            frame_count += 1

            if raw is None:
                time.sleep(0.01)
                continue

            _, detected, binary = detector.detect_with_binary(raw)

            at_intersection = inter.detect(binary, _, detected)

            if phase == "line_follow":
                # PID 巡线
                left, right = pid.compute(_)
                if car_ok:
                    Robot._bot.MotorRun(0, 'forward', left)
                    Robot._bot.MotorRun(1, 'forward', left)
                    Robot._bot.MotorRun(2, 'forward', right)
                    Robot._bot.MotorRun(3, 'forward', right)

                if frame_count % 10 == 0:
                    print(f"  [巡线] 帧={frame_count}  偏差={_:+.3f}  "
                          f"{'N' if not detected else ''}")

                if at_intersection:
                    print(f"\n[STEP 1] 检测到路口 (帧={frame_count})")
                    Robot.stop()
                    time.sleep(0.1)

                    # ── 穿越 ──
                    print(f"[STEP 2] 穿越路口 ({CROSS_TIME}s @ speed={CROSS_SPEED})...")
                    if car_ok:
                        Robot._bot.t_up(CROSS_SPEED)
                    time.sleep(CROSS_TIME)
                    Robot.stop()
                    time.sleep(0.1)

                    # ── 转向 ──
                    print(f"[STEP 3] 转向 ({direction} {TURN_ANGLE}°)...")
                    pid.reset()
                    inter.reset()
                    _turn(detector, turn_right, TURN_SPEED, TURN_ANGLE)
                    time.sleep(0.1)

                    # ── 恢复巡线 ──
                    print(f"[STEP 4] 恢复巡线 {POST_TURN_LINE_FOLLOW}s ...")
                    phase = "post_turn"
                    phase_start = time.time()

            elif phase == "post_turn":
                left, right = pid.compute(_)
                if car_ok:
                    Robot._bot.MotorRun(0, 'forward', left)
                    Robot._bot.MotorRun(1, 'forward', left)
                    Robot._bot.MotorRun(2, 'forward', right)
                    Robot._bot.MotorRun(3, 'forward', right)

                if frame_count % 10 == 0:
                    print(f"  [转向后巡线] 帧={frame_count}  偏差={_:+.3f}  "
                          f"{'N' if not detected else ''}")

                if time.time() - phase_start >= POST_TURN_LINE_FOLLOW:
                    Robot.stop()
                    elapsed = time.time() - start
                    print(f"\n[DONE] 测试完成!")
                    print(f"  总耗时: {elapsed:.1f}s")
                    print(f"  总帧数: {frame_count}")
                    detector.close()
                    return

    except KeyboardInterrupt:
        print("\n[ABORT] 用户中断")
    finally:
        Robot.stop()
        detector.close()


if __name__ == "__main__":
    main()
