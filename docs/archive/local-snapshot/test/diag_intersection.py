#!/usr/bin/env python3
"""
十字路口检测诊断脚本 — 逐帧输出 intersection detector 内部状态。

用法:
    source ./venv/bin/activate
    python -m test.diag_intersection [image_path]

无参数时从摄像头实时读取，有参数时分析指定图片（模拟单帧，跳过 debounce）。
"""

import sys
import time

sys.path.insert(0, ".")

import cv2
import numpy as np

from src.vision.line_detector import LineDetector
from src.vision.intersection_detector import IntersectionDetector

FRAMES = 30        # 实时模式采集帧数
CAMERA_ID = 0


def diag_frame(binary: np.ndarray, inter: IntersectionDetector) -> dict:
    """Run one frame through the detector and return internal state."""
    area = inter._compute_line_area(binary)
    inter._area_history.append(area)
    if len(inter._area_history) > 10:
        inter._area_history.pop(0)

    has_h = False
    avg_a = 0.0
    spike = False

    if len(inter._area_history) >= 5:
        areas = np.array(inter._area_history)
        avg_a = np.mean(areas[:-1])
        spike = bool(area > avg_a * 2.5 and avg_a > 100)
        has_h = inter._detect_horizontal_lines(binary)

    return {
        "area": area,
        "avg_area": avg_a,
        "spike": spike,
        "has_horizontal": has_h,
        "history_len": len(inter._area_history),
    }


def main() -> None:
    args = sys.argv[1:]

    if args:
        # 图片模式
        img = cv2.imread(args[0])
        if img is None:
            print(f"[FAIL] 无法读取图片: {args[0]}")
            return
        print(f"[INFO] 图片模式: {args[0]}")

        detector = LineDetector(camera_id=CAMERA_ID)
        h = img.shape[0]
        top = int(h * 0.5)
        roi = img[top:h, :]
        gray = detector._preprocess(roi)
        deviation, detected = detector._find_line_center(gray)
        binary = detector._to_binary(gray)

        print(f"deviation={deviation:+.3f}  detected={detected}")
        print(f"binary shape={binary.shape}, unique values={np.unique(binary)}")
        print(f"white pixels: {np.sum(binary == 255)} / {binary.size} ({np.sum(binary == 255) / binary.size * 100:.1f}%)")

        inter = IntersectionDetector()
        info = diag_frame(binary, inter)
        print(f"area={info['area']:.0f}  avg_area={info['avg_area']:.0f}  spike={info['spike']}  has_h={info['has_horizontal']}")
        return

    # 实时模式
    print("[INFO] 实时模式 — 逐帧诊断")
    detector = LineDetector(camera_id=CAMERA_ID)
    if not detector.open():
        print("[FAIL] 摄像头打开失败")
        return

    inter = IntersectionDetector()

    print(f"{'帧':>4}  {'区域':>8}  {'均区':>8}  {'spike':>6}  {'h_edge':>6}  {'确认':>4}")
    print("-" * 58)

    try:
        for i in range(FRAMES):
            raw = detector.read_frame()
            if raw is None:
                time.sleep(0.01)
                continue

            _, detected, binary = detector.detect_with_binary(raw)
            info = diag_frame(binary, inter)

            at_inter = inter.detect(binary, _, detected)

            flag = " ***" if at_inter else ""
            print(
                f"{i+1:4d}  {info['area']:8.0f}  {info['avg_area']:8.0f}  "
                f"{'Y' if info['spike'] else 'N':>6}  {'Y' if info['has_horizontal'] else 'N':>6}  "
                f"{inter._confirm_count:>4}{flag}"
            )

            if at_inter:
                print("\n[PASS] 检测到十字路口!")
                if raw is not None:
                    cv2.imwrite("intersection.jpg", raw)

    except KeyboardInterrupt:
        print("\n[ABORT]")

    finally:
        detector.close()
        if raw is not None:
            cv2.imwrite("no_intersection.jpg", raw)


if __name__ == "__main__":
    main()
