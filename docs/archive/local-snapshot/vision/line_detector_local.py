"""
vision/line_detector.py
Black line detection using OpenCV.

Captures frames from USB camera, applies ROI cropping, grayscale conversion,
Gaussian blur, adaptive thresholding, and contour detection to find the
black line center position.
"""

import cv2
import numpy as np
from typing import Optional

from src.logger import debug, error


# Detection parameters (tunable on real hardware)
DEFAULT_RESOLUTION = (320, 240)
ROI_START_RATIO = 0.4      # ROI starts at 40% from top → bottom 60% for line following
UPPER_RATIO = 0.4           # Upper 40% for endpoint detection
GAUSSIAN_KERNEL = (5, 5)
ADAPTIVE_BLOCK_SIZE = 11
ADAPTIVE_C = 2
MIN_CONTOUR_AREA = 100      # Minimum contour area to be considered a line


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
        """Crop frame to bottom 60% (ground area ahead of car)."""
        h = frame.shape[0]
        top = int(h * ROI_START_RATIO)
        return frame[top:h, :]

    def _crop_upper(self, frame: np.ndarray) -> np.ndarray:
        """Crop frame to upper 40% for endpoint detection."""
        h = frame.shape[0]
        bottom = int(h * UPPER_RATIO)
        return frame[0:bottom, :]

    def _preprocess(self, roi: np.ndarray) -> np.ndarray:
        """Convert to grayscale, blur, and apply adaptive threshold."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, 0)
        # Black line = low pixel values → invert so line becomes white
        binary = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            ADAPTIVE_BLOCK_SIZE,
            ADAPTIVE_C,
        )
        return binary

    def _find_line_center(self, binary: np.ndarray) -> tuple[float, bool]:
        """
        Find the black line center in binary image.

        Returns:
            (deviation, detected)
            deviation: -1.0 (left) to +1.0 (right), 0.0 = centered
            detected: True if line found
        """
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return 0.0, False

        # Find largest contour (assumed to be the line)
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < MIN_CONTOUR_AREA:
            return 0.0, False

        # Get bounding rect center
        x, y, w, h = cv2.boundingRect(largest)
        center_x = x + w / 2

        # Normalize to -1.0 ~ +1.0
        frame_w = binary.shape[1]
        deviation = (center_x / frame_w) * 2.0 - 1.0

        debug(f"[Vision] Line center: {center_x:.1f}, deviation: {deviation:.3f}")
        return deviation, True

    def detect(self, frame: Optional[np.ndarray] = None) -> tuple[float, bool, Optional[np.ndarray]]:
        """
        Detect black line in a frame.

        Args:
            frame: Camera frame. If None, reads from camera.

        Returns:
            (deviation, detected, binary)
            deviation: -1.0 (left) to +1.0 (right), 0.0 = centered
            detected: True if line found
            binary: Preprocessed binary image (reusable for intersection detection)
        """
        if frame is None:
            frame = self.read_frame()
        if frame is None:
            return 0.0, False, None

        roi = self._crop_roi(frame)
        binary = self._preprocess(roi)
        deviation, detected = self._find_line_center(binary)

        return deviation, detected, binary

    def detect_upper(self, frame: Optional[np.ndarray] = None) -> bool:
        """
        Check if black line exists in the upper 40% of frame (endpoint detection).

        Args:
            frame: Camera frame. If None, reads from camera.

        Returns:
            True if line is present in upper portion.
        """
        if frame is None:
            frame = self.read_frame()
        if frame is None:
            return False

        upper = self._crop_upper(frame)
        binary = self._preprocess(upper)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return False

        largest = max(contours, key=cv2.contourArea)
        return cv2.contourArea(largest) >= MIN_CONTOUR_AREA
