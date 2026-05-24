"""
vision/line_detector.py
Black line detection using OpenCV.

Captures frames from USB camera, applies ROI cropping, grayscale conversion,
Gaussian blur, and column-wise darkest-region analysis to find the
black line center position.
"""

import cv2
import numpy as np
from typing import Optional

from src.logger import debug, error


# Detection parameters (tunable on real hardware)
DEFAULT_RESOLUTION = (320, 240)
ROI_TOP_RATIO = 0.5       # ROI starts at 50% from top (only look at ground ahead)
GAUSSIAN_KERNEL = (5, 5)
ADAPTIVE_BLOCK_SIZE = 11
ADAPTIVE_C = 2


class LineDetector:
    """Detects black line in camera frames and returns deviation from center."""

    def __init__(
        self,
        camera_id: int = 0,
        resolution: tuple[int, int] = DEFAULT_RESOLUTION,
    ):
        self._camera_id = camera_id
        self._resolution = resolution
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        """Open camera and set resolution. Returns True on success."""
        self._cap = cv2.VideoCapture(self._camera_id)
        if not self._cap.isOpened():
            error(f"[Vision] Failed to open camera {self._camera_id}")
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return True

    def close(self) -> None:
        """Release camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from camera. Returns None on failure."""
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def _crop_roi(self, frame: np.ndarray) -> np.ndarray:
        """Crop frame to bottom ROI (ground area ahead of car)."""
        h = frame.shape[0]
        top = int(h * ROI_TOP_RATIO)
        return frame[top:h, :]

    def _preprocess(self, roi: np.ndarray) -> np.ndarray:
        """Convert to grayscale and blur. Returns raw grayscale (no threshold)."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, 0)
        return blurred

    def _to_binary(self, gray: np.ndarray) -> np.ndarray:
        """Convert grayscale to binary via adaptive threshold.

        Normalizes grayscale to full 0-255 range first so that
        adaptive threshold works even in low-contrast scenes.
        """
        gray_norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        return cv2.adaptiveThreshold(
            gray_norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, ADAPTIVE_BLOCK_SIZE, ADAPTIVE_C,
        )

    def _find_line_center(self, gray: np.ndarray) -> tuple[Optional[float], bool]:
        """
        Find black line center via per-column darkest-percentile analysis.

        Computes the 5th-percentile value for each column, then isolates
        columns whose value is within 15% of the global minimum. Only those
        columns contribute to the weighted center of mass. This is
        self-calibrating: it works regardless of overall scene brightness.

        Returns:
            (deviation, detected)
            deviation: -1.0 (left) to +1.0 (right), 0.0 = centered
            detected: True if line found
        """
        h, w = gray.shape

        # Per-column: 5th percentile (robust to speckle noise)
        n_dark = max(1, int(h * 0.05))
        col_sorted = np.sort(gray, axis=0)
        col_dark = np.mean(col_sorted[:n_dark], axis=0).astype(np.float32)

        # Invert: dark → high weight
        col_weights = 255.0 - col_dark

        # Only keep columns within 15% of global minimum darkness
        global_min = np.min(col_dark)
        col_weights[col_dark > global_min * 1.15] = 0

        total = np.sum(col_weights)
        if total < 1e-6:
            return 0.0, False

        x_indices = np.arange(w)
        center_x = np.sum(x_indices * col_weights) / total

        deviation = (center_x / w) * 2.0 - 1.0

        debug(f"[Vision] Line center: {center_x:.1f}, deviation: {deviation:.3f}")
        return deviation, True

    def detect(self, frame: Optional[np.ndarray] = None) -> tuple[float, bool]:
        """
        Detect black line in a frame.

        Args:
            frame: Camera frame. If None, reads from camera.

        Returns:
            (deviation, detected)
            deviation: -1.0 (left) to +1.0 (right), 0.0 = centered
            detected: True if line found
        """
        if frame is None:
            frame = self.read_frame()
        if frame is None:
            return 0.0, False

        roi = self._crop_roi(frame)
        gray = self._preprocess(roi)
        deviation, detected = self._find_line_center(gray)

        return deviation, detected

    def detect_with_binary(
        self, frame: Optional[np.ndarray] = None
    ) -> tuple[float, bool, Optional[np.ndarray]]:
        """
        Detect black line and return the binary image for intersection detection.

        Args:
            frame: Camera frame. If None, reads from camera.

        Returns:
            (deviation, detected, binary)
            binary: Preprocessed binary image, or None if no frame
        """
        if frame is None:
            frame = self.read_frame()
        if frame is None:
            return 0.0, False, None

        roi = self._crop_roi(frame)
        gray = self._preprocess(roi)
        deviation, detected = self._find_line_center(gray)
        binary = self._to_binary(gray)

        return deviation, detected, binary

    def detect_with_debug(self, frame: Optional[np.ndarray] = None) -> dict:
        """
        Detect with full debug info for visualization.

        Returns dict with: deviation, detected, roi, binary, contours
        """
        if frame is None:
            frame = self.read_frame()
        if frame is None:
            return {"deviation": 0.0, "detected": False}

        roi = self._crop_roi(frame)
        gray = self._preprocess(roi)
        deviation, detected = self._find_line_center(gray)

        return {
            "deviation": deviation,
            "detected": detected,
            "roi": roi,
            "gray": gray,
            "binary": self._to_binary(gray),
        }
