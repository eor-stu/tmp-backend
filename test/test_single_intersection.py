"""
test/test_single_intersection.py
Single-intersection navigation test — follow line, detect & cross junction, turn.

Usage:
    python -m test.test_single_intersection
    python -m test.test_single_intersection --camera 1
    python -m test.test_single_intersection --forward 2 --turn -90  # pass 2 intersections, turn left

Place the car on a straight line before an intersection. The car will:
1. Follow the line → detect intersection → cross forward → turn → follow next line
"""

import argparse
import sys

from src.vision.navigator import Navigator

DEFAULT_COMMANDS = [
    {"action": "forward", "param": 1},   # pass 1 intersection
    {"action": "turn", "param": 90},      # turn right 90°
]


def main():
    p = argparse.ArgumentParser(description="Single-intersection navigation test")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--forward", type=int, default=1, help="Intersections to pass before turn")
    p.add_argument("--turn", type=int, default=90, help="Turn angle (positive=right, negative=left)")
    args = p.parse_args()

    commands = [
        {"action": "forward", "param": args.forward},
        {"action": "turn", "param": args.turn},
    ]

    nav = Navigator(camera_id=args.camera)
    nav.set_commands(commands)
    nav.run()


if __name__ == "__main__":
    main()
