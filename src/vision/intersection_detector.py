"""
vision/intersection_detector.py
Detects intersections (crossroads) in camera frames.

Uses two complementary signals (OR logic):
1. Area spike vs fixed baseline — area exceeds a locked straight-line reference
2. Horizontal edge detection — Sobel X finds strong cross-lines

The baseline is computed from the first frames (assumed to be on a straight line)
and locked, avoiding the rolling-average problem where gradual area increases
are never detected as spikes.
"""

import cv2
import numpy as np

from src.logger import debug, info


# Detection parameters
AREA_SPIKE_RATIO = 1.5          # Area must exceed fixed baseline by this factor
HORIZONTAL_LINE_THRESHOLD = 0.3  # Ratio of horizontal edge pixels to frame width
SOBEL_THRESHOLD = 50             # Fixed threshold for Sobel edges (tuned for normalized binary)
CONFIRM_FRAMES = 3               # Consecutive signal frames to confirm
BASELINE_WINDOW = 10             # Frames to collect for fixed baseline


class IntersectionDetector:
    """Detects intersections via area spike (fixed baseline) OR horizontal lines."""

    def __init__(self):
        self._baseline_samples: list[float] = []
        self._baseline_area: float | None = None
        self._confirm_count: int = 0
        self._is_at_intersection: bool = False

    def reset(self) -> None:
        """Reset detector state (baseline is preserved)."""
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
        sobel_x = cv2.Sobel(binary, cv2.CV_64F, 1, 0, ksize=3)
        abs_sobel = np.abs(sobel_x).astype(np.uint8)
        _, thresh = cv2.threshold(abs_sobel, SOBEL_THRESHOLD, 255, cv2.THRESH_BINARY)

        row_sums = np.sum(thresh, axis=1) / 255
        width = binary.shape[1]

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

        Uses OR logic with a fixed baseline (not rolling average):
        area spike vs locked straight-line reference, or horizontal edges.

        Args:
            binary: Preprocessed binary image (from LineDetector._to_binary)
            deviation: Current line deviation (unused, kept for API compat)
            line_detected: Whether line is currently detected (unused, kept for API compat)

        Returns:
            True when intersection first confirmed (fires once per entry)
        """
        area = self._compute_line_area(binary)

        # Lock baseline after collecting enough samples on straight line
        if self._baseline_area is None:
            self._baseline_samples.append(area)
            if len(self._baseline_samples) >= BASELINE_WINDOW:
                self._baseline_area = np.mean(self._baseline_samples)
                info(f"[Vision] Intersection baseline locked: {self._baseline_area:.0f}")
            return False

        # Signal 1: area spike vs fixed baseline
        area_spike = area > self._baseline_area * AREA_SPIKE_RATIO and self._baseline_area > 100

        # Signal 2: horizontal cross-lines
        has_horizontal = self._detect_horizontal_lines(binary)

        is_signal = area_spike or has_horizontal

        if is_signal:
            self._confirm_count += 1
        else:
            self._confirm_count = 0
            self._is_at_intersection = False

        if self._confirm_count >= CONFIRM_FRAMES and not self._is_at_intersection:
            self._is_at_intersection = True
            info(f"[Vision] Intersection detected! area={area:.0f} baseline={self._baseline_area:.0f} "
                 f"spike={'Y' if area_spike else 'N'} h_edge={'Y' if has_horizontal else 'N'}")
            return True

        return False
