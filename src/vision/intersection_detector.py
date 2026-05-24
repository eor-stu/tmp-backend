"""
vision/intersection_detector.py
Detects intersections (crossroads) in camera frames.

Uses contour aspect-ratio classification: vertical contours (tall, narrow)
indicate the main line; horizontal contours (wide, short) indicate a crossing
line. Both must be present, and total contour area must exceed a threshold
ratio of ROI area to ensure the car is close enough to the intersection.
"""

import cv2
import numpy as np

from src.logger import debug, info


# Detection parameters
AREA_THRESHOLD_RATIO = 0.20   # Total contour area must exceed 20% of ROI (calibrated 2026-05-24)
ASPECT_VERTICAL = 2.0          # h/w > 2 → vertical line segment
ASPECT_HORIZONTAL = 2.0        # w/h > 2 → horizontal line segment
ENTRY_FRAMES = 2                # Consecutive signal frames to confirm entry
RELEASE_FRAMES = 8              # Consecutive no-signal frames to release latch


class IntersectionDetector:
    """Detects intersections using contour aspect-ratio classification with latch."""

    def __init__(self, area_threshold_ratio: float = AREA_THRESHOLD_RATIO):
        self._area_threshold_ratio = area_threshold_ratio
        self._confirm_count: int = 0
        self._release_count: int = 0
        self._is_at_intersection: bool = False

    def reset(self) -> None:
        """Reset detector state."""
        self._confirm_count = 0
        self._release_count = 0
        self._is_at_intersection = False

    def detect(
        self,
        binary: np.ndarray,
        deviation: float,
        line_detected: bool,
    ) -> bool:
        """
        Detect if car is at an intersection.

        An intersection requires:
        1. Both vertical and horizontal line contours present
        2. Total contour area exceeds threshold ratio of ROI area

        Uses a latch: once triggered, stays active until signal is absent
        for RELEASE_FRAMES consecutive frames, preventing missed triggers
        at normal driving speed.

        Args:
            binary: Preprocessed binary image (from LineDetector._to_binary)
            deviation: Current line deviation (unused, kept for API compat)
            line_detected: Whether line is currently detected (unused, kept for API compat)

        Returns:
            True when intersection first confirmed (fires once per entry)
        """
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            signal = False
            total_area = 0.0
            roi_area = 1.0
        else:
            has_vertical = False
            has_horizontal = False
            total_area = 0.0

            for c in contours:
                area = cv2.contourArea(c)
                total_area += area
                x, y, w, h = cv2.boundingRect(c)

                if h <= 0 or w <= 0:
                    continue

                if h / w > ASPECT_VERTICAL:
                    has_vertical = True
                if w / h > ASPECT_HORIZONTAL:
                    has_horizontal = True

            roi_h, roi_w = binary.shape[:2]
            roi_area = roi_w * roi_h
            area_ok = total_area > roi_area * self._area_threshold_ratio
            signal = has_vertical and has_horizontal and area_ok

        # Latch logic
        if self._is_at_intersection:
            if signal:
                self._release_count = 0
            else:
                self._release_count += 1
                if self._release_count >= RELEASE_FRAMES:
                    self._is_at_intersection = False
                    self._release_count = 0
                    self._confirm_count = 0
            return False

        # Not latched — accumulate confirmations
        if signal:
            self._confirm_count += 1
        else:
            self._confirm_count = 0

        if self._confirm_count >= ENTRY_FRAMES:
            self._is_at_intersection = True
            self._release_count = 0
            info(f"[Vision] Intersection detected! area_ratio={total_area / roi_area:.2f}")
            return True

        return False
