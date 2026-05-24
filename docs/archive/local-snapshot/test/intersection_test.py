#!/usr/bin/env python3
"""
十字路口检测测试脚本。

用法:
    source ./venv/bin/activate
    python -m test.intersection_test

功能:
    1. 打开摄像头，逐帧运行 intersection detector
    2. 检出路口后保存触发帧为 intersection.jpg，输出检测结果
    3. 最长运行 10 秒，超时未检出则保存最后一帧为 no_intersection.jpg
"""

import sys
import time

sys.path.insert(0, ".")

import cv2

from src.vision.line_detector import LineDetector
from src.vision.intersection_detector import IntersectionDetector

TIMEOUT = 10.0       # 最长运行秒数
CAMERA_ID = 0


def main() -> None:
    detector = LineDetector(camera_id=CAMERA_ID)
    if not detector.open():
        print("[FAIL] 摄像头打开失败")
        return

    inter = IntersectionDetector()
    inter.reset()

    start = time.time()
    last_frame = None
    frame_count = 0

    print(f"[INFO] 开始检测十字路口, 超时={TIMEOUT}s ...")
    print(f"[INFO] 需要连续 {3} 帧确认（debounce）")

    try:
        while time.time() - start < TIMEOUT:
            raw = detector.read_frame()
            frame_count += 1

            if raw is None:
                time.sleep(0.01)
                continue

            _, detected, binary = detector.detect_with_binary(raw)
            last_frame = raw

            at_inter = inter.detect(binary, _, detected)

            if at_inter:
                elapsed = time.time() - start
                print(f"\n[PASS] 检测到十字路口!")
                print(f"  耗时: {elapsed:.1f}s")
                print(f"  帧数: {frame_count}")
                if last_frame is not None:
                    cv2.imwrite("intersection.jpg", last_frame)
                    print(f"  已保存触发帧: intersection.jpg")
                detector.close()
                return

    except KeyboardInterrupt:
        print("\n[ABORT] 用户中断")
    finally:
        detector.close()

    elapsed = time.time() - start
    print(f"\n[FAIL] 超时未检出十字路口")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  帧数: {frame_count}")
    if last_frame is not None:
        cv2.imwrite("no_intersection.jpg", last_frame)
        print(f"  已保存最后一帧: no_intersection.jpg")


if __name__ == "__main__":
    main()
