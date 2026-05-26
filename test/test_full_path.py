"""
test/test_full_path.py
Full-path navigation test — uses map routing + Navigator end-to-end.

Usage:
    python -m test.test_full_path
    python -m test.test_full_path --start entrance --dest pharmacy
    python -m test.test_full_path --start entrance --dest pharmacy --camera 1

Requires a physical track with intersections matching the grid map layout.
"""

import argparse
import sys

from src.vision.navigator import Navigator
from src.map import get_commands


def main():
    p = argparse.ArgumentParser(description="Full-path navigation test")
    p.add_argument("--start", default="entrance", help="Start location ID")
    p.add_argument("--dest", default="pharmacy", help="Destination location ID")
    p.add_argument("--camera", type=int, default=0)
    args = p.parse_args()

    print(f"Planning route: {args.start} → {args.dest}")
    commands = get_commands(args.start, args.dest)

    if not commands:
        print(f"ERROR: No route found from {args.start} to {args.dest}")
        sys.exit(1)

    print(f"Commands: {commands}")
    print(f"Place car at START position, then it will auto-navigate.")
    print()

    nav = Navigator(camera_id=args.camera)
    nav.set_commands(commands)
    nav.run()


if __name__ == "__main__":
    main()
