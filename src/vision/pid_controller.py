"""
vision/pid_controller.py
PID controller for line-following differential steering.

Takes deviation from line center and outputs left/right motor speed adjustment.
"""

from dataclasses import dataclass, field
from typing import Final

from src.logger import debug


# Default PID gains (tune on real hardware)
DEFAULT_KP: Final[float] = 30.0
DEFAULT_KI: Final[float] = 1.0
DEFAULT_KD: Final[float] = 10.0

# Speed limits (0-100, matching LOBOROBOT duty cycle)
BASE_SPEED: Final[int] = 20
MAX_SPEED: Final[int] = 35
MIN_SPEED: Final[int] = 5


@dataclass
class PIDController:
    """
    PID controller for line-following.

    Usage:
        pid = PIDController()
        left_speed, right_speed = pid.compute(deviation=0.3)
    """

    kp: float = DEFAULT_KP
    ki: float = DEFAULT_KI
    kd: float = DEFAULT_KD

    _integral: float = field(default=0.0, init=False)
    _prev_error: float = field(default=0.0, init=False)
    _last_deviation: float = field(default=0.0, init=False)

    def reset(self) -> None:
        """Reset integral and derivative state."""
        self._integral = 0.0
        self._prev_error = 0.0

    def compute(self, deviation: float, line_detected: bool = True) -> tuple[int, int]:
        """
        Compute left and right motor speeds from line deviation.

        Args:
            deviation: -1.0 (line on left) to +1.0 (line on right), 0.0 = centered
            line_detected: Whether line is currently found. If False, deviation is
                           treated as 0 (straight) to coast until line reappears.

        Returns:
            (left_speed, right_speed) — values in [MIN_SPEED, MAX_SPEED]
        """
        if line_detected:
            self._last_deviation = deviation
        else:
            deviation = 0.0

        # PID calculation
        self._integral += deviation
        # Anti-windup: clamp integral
        self._integral = max(-50.0, min(50.0, self._integral))

        derivative = deviation - self._prev_error
        self._prev_error = deviation

        correction = (
            self.kp * deviation
            + self.ki * self._integral
            + self.kd * derivative
        )

        # Differential steering: line on right → turn left → speed up right wheel
        left_speed = int(BASE_SPEED - correction)
        right_speed = int(BASE_SPEED + correction)

        # Clamp speeds
        left_speed = max(MIN_SPEED, min(MAX_SPEED, left_speed))
        right_speed = max(MIN_SPEED, min(MAX_SPEED, right_speed))

        debug(f"[PID] dev={deviation:.3f} corr={correction:.1f} L={left_speed} R={right_speed}")
        return left_speed, right_speed
