"""
test/test_straight_line.py
Straight line-following test — drives motors with PID correction.

Place the car on a straight black line (no intersections). The car will
follow the line, logging deviation and motor speeds. Stop with Ctrl+C.

Usage:
    python -m test.test_straight_line
    python -m test.test_straight_line --base-speed 25 --camera 1
"""

import argparse
import sys
import time

from src.vision.line_detector import LineDetector
from src.vision.pid_controller import PIDController
from src.car.LOBOROBOT import Robot

BASE_SPEED = 20
LOG_EVERY_N = 30


def main():
    p = argparse.ArgumentParser(description="Straight line-following test")
    p.add_argument("--base-speed", type=int, default=BASE_SPEED)
    p.add_argument("--camera", type=int, default=0)
    args = p.parse_args()

    detector = LineDetector(camera_id=args.camera)
    if not detector.open():
        print("ERROR: Cannot open camera")
        sys.exit(1)

    pid = PIDController()
    car = Robot.is_available

    print(f"Straight line test | base_speed={args.base_speed} | car={'OK' if car else 'MOCK'}")
    print("Ctrl+C to stop")
    print(f"{'frame':>6} {'dev':>7} {'L':>4} {'R':>4} {'line'}")
    print("-" * 42)

    def set_motors(left: int, right: int) -> None:
        if car:
            Robot._bot.MotorRun(0, 'forward', left)
            Robot._bot.MotorRun(1, 'forward', left)
            Robot._bot.MotorRun(2, 'forward', right)
            Robot._bot.MotorRun(3, 'forward', right)

    frame_count = 0
    start_time = time.time()
    deviations = []

    try:
        while True:
            frame = detector.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            deviation, detected, _binary = detector.detect(frame)
            deviations.append(deviation)

            left, right = pid.compute(deviation, detected)
            set_motors(left, right)

            if frame_count % LOG_EVERY_N == 0:
                elapsed = time.time() - start_time
                print(f"{frame_count:6d} {deviation:+7.3f} {left:4d} {right:4d} {'Y' if detected else 'N'}")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        Robot.stop()
        detector.close()

        elapsed = time.time() - start_time
        print(f"\nDone. {frame_count} frames in {elapsed:.1f}s")
        if deviations:
            s = sum(d for d in deviations)
            avg = s / len(deviations)
            var = sum((d - avg) ** 2 for d in deviations) / len(deviations)
            left_pct = sum(1 for d in deviations if d < -0.1) / len(deviations) * 100
            center_pct = sum(1 for d in deviations if -0.1 <= d <= 0.1) / len(deviations) * 100
            right_pct = sum(1 for d in deviations if d > 0.1) / len(deviations) * 100
            print(f"avg dev={avg:+.4f}  std={var**0.5:.4f}  |  "
                  f"left: {left_pct:.0f}%  center: {center_pct:.0f}%  right: {right_pct:.0f}%")


if __name__ == "__main__":
    main()
