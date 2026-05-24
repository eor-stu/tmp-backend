"""
test/test_chassis_calib.py
Chassis physical calibration — verifies V_FORWARD and V_ROTATE.

Runs forward(1.0) x3 and turn(360) x3, prompting the human to measure
and report actual distances/angles. Results are logged to JSONL for
Claude Code to analyze and suggest updated calibration values.

Usage:
    python -m test.test_chassis_calib
"""

import json
import time
from datetime import datetime

from src.car.control import forward, turn
from src.car.LOBOROBOT import Robot
from test.vision_calib_utils import ensure_calib_dir, JsonlWriter

SCENE = "chassis"

FORWARD_DISTANCE = 1.0    # meters — nominal distance to test
TURN_ANGLE = 360           # degrees — nominal angle to test
TRIALS = 3                  # repetitions per test


def _prompt(prompt_text: str) -> str:
    """Prompt user for input and return stripped response."""
    print(prompt_text)
    try:
        return input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def main():
    print("=" * 60)
    print("Chassis Physical Calibration")
    print("=" * 60)
    print()
    print(f"V_FORWARD (nominal): {Robot.V_FORWARD} m/s")
    print(f"V_ROTATE  (nominal): {Robot.V_ROTATE} deg/s")
    print(f"Car available: {Robot.is_available}")
    print()

    if not Robot.is_available:
        print("WARNING: Robot hardware not available. Running in mock mode.")
        print("Motor commands will be logged but car will not move.")
        print("Calibration cannot proceed without hardware.")
        print()

    # Setup output
    out_dir = ensure_calib_dir(SCENE)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = out_dir / f"{ts}.jsonl"
    writer = JsonlWriter(jsonl_path)

    results: list[dict] = []

    try:
        # ------------------------------------------------------------------
        # Forward distance tests
        # ------------------------------------------------------------------
        print("-" * 40)
        print(f"FORWARD TEST ({FORWARD_DISTANCE}m, {TRIALS} trials)")
        print(f"Place a tape mark at the starting position.")
        print()

        for trial in range(1, TRIALS + 1):
            _prompt(f"[Trial {trial}/{TRIALS}] Press Enter to move forward {FORWARD_DISTANCE}m...")

            t0 = time.time()
            forward(FORWARD_DISTANCE)
            elapsed = time.time() - t0

            actual_str = _prompt(f"Enter ACTUAL distance moved (m):")
            try:
                actual = float(actual_str) if actual_str else None
            except ValueError:
                actual = None

            record = {
                "test": "forward",
                "trial": trial,
                "nominal_distance": FORWARD_DISTANCE,
                "nominal_speed": Robot.V_FORWARD,
                "elapsed_s": round(elapsed, 3),
                "actual_distance": actual,
                "measured_speed": round(actual / elapsed, 4) if actual and elapsed > 0 else None,
            }
            writer.write(record)
            results.append(record)
            print(f"  → elapsed={elapsed:.3f}s, actual={actual}m"
                  + (f", measured speed={record['measured_speed']} m/s" if record["measured_speed"] else ""))
            print()

        # ------------------------------------------------------------------
        # Rotation tests
        # ------------------------------------------------------------------
        print("-" * 40)
        print(f"TURN TEST ({TURN_ANGLE}deg, {TRIALS} trials)")
        print("Mark the starting orientation.")
        print()

        for trial in range(1, TRIALS + 1):
            _prompt(f"[Trial {trial}/{TRIALS}] Press Enter to turn {TURN_ANGLE}deg...")

            t0 = time.time()
            turn(TURN_ANGLE)
            elapsed = time.time() - t0

            actual_str = _prompt(f"Enter ACTUAL rotation angle (deg):")
            try:
                actual = float(actual_str) if actual_str else None
            except ValueError:
                actual = None

            record = {
                "test": "turn",
                "trial": trial,
                "nominal_angle": TURN_ANGLE,
                "nominal_speed": Robot.V_ROTATE,
                "elapsed_s": round(elapsed, 3),
                "actual_angle": actual,
                "measured_speed": round(actual / elapsed, 4) if actual and elapsed > 0 else None,
            }
            writer.write(record)
            results.append(record)
            print(f"  → elapsed={elapsed:.3f}s, actual={actual}deg"
                  + (f", measured speed={record['measured_speed']} deg/s" if record["measured_speed"] else ""))
            print()

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("=" * 60)
        print(f"Calibration complete. {len(results)} records written.")
        print(f"Output: {jsonl_path}")
        print()
        print("Next: share the actual_distance and actual_angle values with Claude Code.")
        print("Claude Code will read the JSONL and suggest updated V_FORWARD / V_ROTATE.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        writer.close()
        Robot.stop()
        print("已停止")


if __name__ == "__main__":
    main()
