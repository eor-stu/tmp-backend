#!/usr/bin/env python3
"""
PID 巡线调优脚本。

用法:
    source ./venv/bin/activate
    python -m test.tune_pid --kp 30 --ki 0 --kd 10

功能:
    1. 打开摄像头，巡线行驶
    2. 每帧输出: 帧号 | 偏差 | 检线 | 纠正量 | 左轮 | 右轮
    3. 检测到十字路口后自动停止
    4. 输出统计摘要（平均偏差、偏差标准差、运行时长）

Ctrl+C 随时停止。
"""

import argparse
import math
import subprocess
import sys
import time

sys.path.insert(0, ".")

from src.vision.line_detector import LineDetector
from src.vision.intersection_detector import IntersectionDetector
from src.car.LOBOROBOT import Robot


# ──────────────────────────────────────────────
# 默认参数（可通过命令行覆盖）
# ──────────────────────────────────────────────
DEFAULT_KP = 30.0
DEFAULT_KI = 0.0
DEFAULT_KD = 10.0

BASE_SPEED = 20
MAX_SPEED = 35
MIN_SPEED = 5
ANTI_WINDUP = 50.0

INTERSECTION_COOLDOWN = 2.0
LOG_EVERY_N = 15       # 每 N 帧输出一行日志 (~2Hz)
CAMERA_ID = 0


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _check_video_devices() -> None:
    """列出 /dev/video* 设备。"""
    print("\n[INFO] ls -al /dev/video*:")
    result = subprocess.run(
        ["ls", "-al", "/dev/video*"],
        capture_output=True, text=True, timeout=5,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())


def run(kp: float, ki: float, kd: float, camera_id: int = 0, base_speed: int = 20) -> None:
    # ── 硬件初始化 ──
    detector = LineDetector(camera_id=camera_id)
    if not detector.open():
        print("[ERROR] 摄像头打开失败")
        detector.close()
        _check_video_devices()
        return

    car_available = Robot.is_available
    print(f"[INFO] 底盘: {'OK' if car_available else 'MOCK'}")
    print(f"[INFO] PID: Kp={kp}  Ki={ki}  Kd={kd}")
    print(f"[INFO] 基准速度={base_speed}  速度范围=[{MIN_SPEED}, {MAX_SPEED}]")
    print()

    inter_detector = IntersectionDetector()

    # ── PID 状态 ──
    integral = 0.0
    prev_error = 0.0

    # ── 统计 ──
    deviations: list[float] = []
    frame_count = 0
    start_time = time.time()
    last_intersection_time = 0.0

    # ── 表头 ──
    print(f"{'帧':>5}  {'偏差':>7}  {'检线':>4}  {'纠正':>7}  {'左轮':>4}  {'右轮':>4}  {'状态'}")
    print("-" * 55)

    def motor_forward(speed: int) -> None:
        if car_available:
            Robot._bot.t_up(speed)

    def motor_stop() -> None:
        if car_available:
            Robot.stop()

    def set_differential(left: int, right: int) -> None:
        if car_available:
            Robot._bot.MotorRun(0, 'forward', left)
            Robot._bot.MotorRun(1, 'forward', left)
            Robot._bot.MotorRun(2, 'forward', right)
            Robot._bot.MotorRun(3, 'forward', right)

    try:
        while True:
            frame_count += 1

            # 读帧 + 检线
            frame = detector.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            deviation, detected, binary = detector.detect_with_binary(frame)
            deviations.append(deviation)

            # 路口检测（带冷却）
            now = time.time()

            at_intersection = False
            if now - last_intersection_time > INTERSECTION_COOLDOWN:
                at_intersection = inter_detector.detect(binary, deviation, detected)

            if at_intersection:
                motor_stop()
                elapsed = now - start_time
                print("-" * 55)
                print(f"[路口] 检测到十字路口! 耗时={elapsed:.1f}s, 总帧数={frame_count}")
                _print_summary(deviations, elapsed)
                return

            # PID 计算
            integral += deviation
            integral = clamp(integral, -ANTI_WINDUP, ANTI_WINDUP)
            derivative = deviation - prev_error
            prev_error = deviation

            correction = kp * deviation + ki * integral + kd * derivative

            left_speed = int(clamp(base_speed - correction, MIN_SPEED, MAX_SPEED))
            right_speed = int(clamp(base_speed + correction, MIN_SPEED, MAX_SPEED))

            set_differential(left_speed, right_speed)

            # 日志
            if frame_count % LOG_EVERY_N == 0:
                status = "Y" if detected else "N"
                print(
                    f"{frame_count:5d}  {deviation:+7.3f}  {status:>4}  "
                    f"{correction:+7.1f}  {left_speed:4d}  {right_speed:4d}"
                )

    except KeyboardInterrupt:
        motor_stop()
        elapsed = time.time() - start_time
        print("\n" + "-" * 55)
        print(f"[中断] 用户停止, 耗时={elapsed:.1f}s, 总帧数={frame_count}")
        if deviations:
            _print_summary(deviations, elapsed)
    finally:
        Robot.stop()
        detector.close()
        _check_video_devices()


def _print_summary(deviations: list[float], elapsed: float) -> None:
    """输出统计摘要。"""
    if not deviations:
        return

    avg = sum(deviations) / len(deviations)
    variance = sum((d - avg) ** 2 for d in deviations) / len(deviations)
    std = math.sqrt(variance)
    abs_avg = sum(abs(d) for d in deviations) / len(deviations)

    print()
    print(f"  总帧数:      {len(deviations)}")
    print(f"  运行时长:    {elapsed:.1f}s")
    print(f"  平均偏差:    {avg:+.4f}  (理想=0)")
    print(f"  偏差标准差:  {std:.4f}   (越小越稳)")
    print(f"  平均|偏差|:  {abs_avg:.4f}  (越小越好)")
    print()

    # 偏差分布
    left_count = sum(1 for d in deviations if d < -0.1)
    center_count = sum(1 for d in deviations if -0.1 <= d <= 0.1)
    right_count = sum(1 for d in deviations if d > 0.1)
    total = len(deviations)
    print(f"  偏左 (<-0.1): {left_count:5d}  ({left_count/total*100:5.1f}%)")
    print(f"  居中:          {center_count:5d}  ({center_count/total*100:5.1f}%)")
    print(f"  偏右 (>+0.1): {right_count:5d}  ({right_count/total*100:5.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="PID 巡线调优")
    parser.add_argument("--kp", type=float, default=DEFAULT_KP, help="比例增益")
    parser.add_argument("--ki", type=float, default=DEFAULT_KI, help="积分增益")
    parser.add_argument("--kd", type=float, default=DEFAULT_KD, help="微分增益")
    parser.add_argument("--camera", type=int, default=CAMERA_ID, help="摄像头 ID")
    parser.add_argument("--base-speed", type=int, default=BASE_SPEED, help="基准速度")
    args = parser.parse_args()

    run(args.kp, args.ki, args.kd, camera_id=args.camera, base_speed=args.base_speed)


if __name__ == "__main__":
    main()
