"""
vision/intersection_detector.py
Detects intersections (crossroads) in camera frames.

Uses contour area analysis and horizontal line detection to identify
when the car has reached a junction point.
"""

import cv2
import numpy as np
from typing import Optional

from src.logger import debug, info


# Detection parameters
AREA_SPIKE_RATIO = 2.5      # Contour area must increase by this factor vs average
CONFIRM_FRAMES = 3           # Consecutive frames needed to confirm intersection
HORIZONTAL_LINE_THRESHOLD = 0.3  # Ratio of horizontal edges to frame width


class IntersectionDetector:
    """Detects intersections using frame analysis and debouncing."""

    def __init__(self):
        self._area_history: list[float] = []
        self._confirm_count: int = 0
        self._is_at_intersection: bool = False

    def reset(self) -> None:
        """Reset detector state."""
        self._area_history.clear()
        self._confirm_count = 0
        self._is_at_intersection = False

    def _compute_line_area(self, binary: np.ndarray) -> float:
        """Compute total contour area in binary image."""
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 0.0
        return sum(cv2.contourArea(c) for c in contours)

    def _detect_horizontal_lines(self, binary: np.ndarray) -> bool:
        """Detect strong horizontal edges (cross-line at intersection)."""
        # Sobel in X direction to find horizontal edges
        sobel_x = cv2.Sobel(binary, cv2.CV_64F, 1, 0, ksize=3)
        abs_sobel = np.abs(sobel_x).astype(np.uint8)
        _, thresh = cv2.threshold(abs_sobel, 50, 255, cv2.THRESH_BINARY)
        # Note: threshold 50 is tuned for adaptive-threshold binary input.
        # If switching to a different binary source, re-tune.

        # Count horizontal edge pixels in each row
        row_sums = np.sum(thresh, axis=1) / 255
        width = binary.shape[1]

        # If any row has > threshold ratio of edge pixels, it's a cross-line
        max_ratio = np.max(row_sums) / width if width > 0 else 0.0
        return max_ratio > HORIZONTAL_LINE_THRESHOLD

    def detect(
        self,
        binary: np.ndarray,
        deviation: float,
        line_detected: bool,
    ) -> bool:
        """
        Detect if car is at an intersection.

        Args:
            binary: Adaptive-threshold binary image (from LineDetector._to_binary)
            deviation: Current line deviation
            line_detected: Whether line is currently detected

        Returns:
            True if at intersection (confirmed after debouncing)
        """
        # If line is lost, could be at intersection center (no line ahead)
        # But also could be lost tracking — use area spike as primary signal

        area = self._compute_line_area(binary)
        self._area_history.append(area)

        # Keep last 10 frames of history
        if len(self._area_history) > 10:
            self._area_history.pop(0)

        # Need at least 5 frames of history
        if len(self._area_history) < 5:
            return False

        # Check if current area is a spike vs average of previous frames
        avg_area = np.mean(self._area_history[:-1])
        area_spike = area > avg_area * AREA_SPIKE_RATIO and avg_area > 100

        # Check for horizontal cross-lines
        has_horizontal = self._detect_horizontal_lines(binary)

        # Intersection signal: area spike OR horizontal lines
        is_intersection_signal = area_spike or has_horizontal

        # Debounce: require consecutive confirmations
        if is_intersection_signal:
            self._confirm_count += 1
        else:
            self._confirm_count = 0

        if self._confirm_count >= CONFIRM_FRAMES and not self._is_at_intersection:
            self._is_at_intersection = True
            info("[Vision] Intersection detected!")
            return True

        if not is_intersection_signal and self._is_at_intersection:
            # Left intersection zone
            self._is_at_intersection = False
            self._confirm_count = 0

        return False
