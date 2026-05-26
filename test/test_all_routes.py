"""
test/test_all_routes.py
Enumerate all main-location → main-location routes and their commands.

Usage:
    python -m test.test_all_routes
"""

import logging

from src.map.tools import get_map, get_commands

logging.disable(logging.INFO)


def main():
    map_data = get_map()
    main_ids = sorted(map_data.get_main_node_ids())
    names = map_data.get_main_node_info()

    for start in main_ids:
        for end in main_ids:
            if start == end:
                continue
            commands = get_commands(start, end)
            cmd_str = ", ".join(
                f"{c['action']}({c['param']})" for c in commands
            )
            start_name = names.get(start, {}).get("name", start)
            end_name = names.get(end, {}).get("name", end)
            print(f"{start_name}({start}) → {end_name}({end})")
            print(f"  ==> [{cmd_str}]")
            print()


if __name__ == "__main__":
    main()
