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
AREA_THRESHOLD_RATIO = 0.3    # Total contour area must exceed 30% of ROI
ASPECT_VERTICAL = 2.0          # h/w > 2 → vertical line segment
ASPECT_HORIZONTAL = 2.0        # w/h > 2 → horizontal line segment
CONFIRM_FRAMES = 3              # Consecutive frames needed to confirm intersection


class IntersectionDetector:
    """Detects intersections using contour aspect-ratio classification and debouncing."""

    def __init__(self, area_threshold_ratio: float = AREA_THRESHOLD_RATIO):
        self._area_threshold_ratio = area_threshold_ratio
        self._confirm_count: int = 0
        self._is_at_intersection: bool = False

    def reset(self) -> None:
        """Reset detector state."""
        self._confirm_count = 0
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

        Args:
            binary: Preprocessed binary image (from LineDetector._preprocess)
            deviation: Current line deviation (unused in new logic, kept for API compat)
            line_detected: Whether line is currently detected (unused, kept for API compat)

        Returns:
            True if at intersection (confirmed after debouncing)
        """
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            self._confirm_count = 0
            self._is_at_intersection = False
            return False

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

        # Check both criteria
        roi_h, roi_w = binary.shape[:2]
        roi_area = roi_w * roi_h
        area_ok = total_area > roi_area * self._area_threshold_ratio

        signal = has_vertical and has_horizontal and area_ok

        # Debounce
        if signal:
            self._confirm_count += 1
        else:
            self._confirm_count = 0
            self._is_at_intersection = False

        if self._confirm_count >= CONFIRM_FRAMES and not self._is_at_intersection:
            self._is_at_intersection = True
            info(f"[Vision] Intersection detected! area_ratio={total_area / roi_area:.2f}")
            return True

        return False
