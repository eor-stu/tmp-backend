"""
map/tools.py
Map management functions, utilities, and path-to-command conversion.
"""

import json
from pathlib import Path
from typing import Literal

from src.logger import info, error, debug
from src.utils import ROOT_DIR
from src.map.typedef import Map, Node, Edge

AbsoluteDir = Literal["east", "west", "south", "north", "stay"]


def _rename_nav_nodes(nodes: list[dict]) -> list[dict]:
    """Assign unique IDs to nav nodes: road_{x}_{y}."""
    for n in nodes:
        if n.get("type") == "nav" and n.get("id") == "road":
            n["id"] = f"road_{n['x']}_{n['y']}"
    return nodes


def _load_map_from_json(json_path: Path | str | None = None) -> Map | None:
    """Load map from JSON file and return Map object."""
    if json_path is None:
        json_path = ROOT_DIR / "src" / "map" / "map.json"
    else:
        json_path = Path(json_path)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["nodes"] = _rename_nav_nodes(data.get("nodes", []))
        return Map(**data)
    except Exception as e:
        error(f"[Map] Failed to load map: {e}")
        return None


def _compute_all_costs(map_obj: Map) -> None:
    """Deprecated: costs are now set during edge building. Kept as no-op for compatibility."""
    pass


# ========== Module-level Cache ==========

_cached_map: Map | None = None


def get_map() -> Map:
    """
    Get the pre-loaded and pre-computed Map object.
    Uses lazy loading - loads and computes costs on first call.
    """
    global _cached_map

    if _cached_map is None:
        map_obj = _load_map_from_json()
        if map_obj is None:
            raise RuntimeError("Failed to load map from map.json")
        _cached_map = map_obj
        info(f"[Map] Loaded map with {len(map_obj.nodes)} nodes, {len(map_obj.edges)} edges")

    return _cached_map


# ========== Path to Commands ==========


def _get_absolute_direction(dx: float, dy: float) -> AbsoluteDir:
    """Convert coordinate delta to cardinal direction."""
    if dx > 0:
        return "east"
    elif dx < 0:
        return "west"
    elif dy > 0:
        return "south"
    elif dy < 0:
        return "north"
    return "stay"


def _direction_to_degrees(direction: AbsoluteDir) -> int:
    """Map cardinal direction to degrees (clockwise from east)."""
    mapping = {"east": 0, "north": 90, "west": 180, "south": 270, "stay": 0}
    return mapping[direction]


def _get_relative_turn(current_dir: AbsoluteDir, target_dir: AbsoluteDir) -> int:
    """
    Calculate the relative turn angle between two directions.
    Returns angle in degrees: positive = clockwise (right), negative = counter-clockwise (left).
    """
    current_deg = _direction_to_degrees(current_dir)
    target_deg = _direction_to_degrees(target_dir)
    diff = (target_deg - current_deg) % 360

    if diff == 0:
        return 0
    elif diff == 180:
        return 180
    elif diff == 90:
        return -90   # counter-clockwise = left turn
    elif diff == 270:
        return 90    # clockwise = right turn
    return 0


def _merge_consecutive_straights(actions: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Merge consecutive forward moves into a single action."""
    if not actions:
        return []

    merged: list[tuple[str, float]] = []
    for action_type, param in actions:
        if action_type == "forward" and merged and merged[-1][0] == "forward":
            merged[-1] = ("forward", merged[-1][1] + param)
        else:
            merged.append((action_type, param))

    return merged


def _is_intersection(node_id: str, node_dict: dict) -> bool:
    """
    Determine if a road node is a functional intersection.

    A node is considered an intersection when ALL of the following are true:
    1. The node itself is of type "nav" (a road node)
    2. All 4 orthogonally adjacent cells (up/down/left/right at distance 1)
       contain a node of ANY type (nav or main)

    This captures both pure crossroads (4 nav neighbors) and corridor
    junctions where one direction leads to a main location (e.g. exit).
    """
    node = node_dict.get(node_id)
    if node is None or node.type != "nav":
        return False

    # Build coordinate → node lookup from all nodes
    coord_to_node = {}
    for n in node_dict.values():
        coord_to_node[(int(n.x), int(n.y))] = n

    x, y = int(node.x), int(node.y)
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        if (x + dx, y + dy) not in coord_to_node:
            return False

    return True


def get_commands(start: str, end: str) -> list[dict[str, str | float]]:
    """
    Convert a path between two map nodes into car control commands.

    The car starts parked at a main-type node, facing the main node itself
    (i.e. facing away from the adjacent road). Each command is executed
    sequentially: the car follows the black line, counts intersections,
    and executes explicit turns at intersections where the path changes
    direction. Direction changes at non-intersection nodes are handled
    naturally by the line detector (the line curves and the car follows).

    An intersection is a road node whose 4 orthogonally adjacent cells are
    all also roads. At an intersection, the car goes straight unless told
    to turn.

    Example: entrance → pharmacy
        Path: entrance → (northbound) → road_2_5 → pharmacy
        Intersections: road_2_7 (#1), road_2_5 (#2)
        Direction change: at road_2_5 (north → west, a left turn)
        Commands: [turn(180), forward(2), turn(-90), arrive]

    Example: internal_clinic → toilet
        Path: IC → east to road_2_3 → south to road_2_7 → east to toilet
        Intersections: road_2_3 (#1), road_2_5 (#2), road_2_7 (#3)
        Direction changes: at road_2_3 (east → south, right turn),
                           at road_2_7 (south → east, left turn)
        Commands: [turn(180), forward(1), turn(90), forward(2), turn(-90), arrive]

    Args:
        start: Starting node ID (e.g. "entrance", "internal_clinic")
        end: Ending node ID (e.g. "pharmacy", "toilet")

    Returns:
        List of {action, param} dicts, e.g.:
            [{"action": "turn", "param": 180.0},
             {"action": "forward", "param": 1.0},
             {"action": "turn", "param": 90.0}, ...]
    """
    map_data = get_map()
    path = map_data.dijkstra(start, end)
    if path is None or len(path) < 2:
        return []

    node_dict: dict[str, object] = {n.id: n for n in map_data.nodes}

    # ── Phase 1: Identify all intersections and direction changes on the path ──
    isect_indices: list[int] = []         # path indices of intersection nodes
    turns: list[tuple[int, float]] = []    # (path_index, turn_angle) for each turn

    current_dir: AbsoluteDir | None = None

    for i in range(len(path) - 1):
        current_id = path[i]
        next_id = path[i + 1]

        current_node = node_dict.get(current_id)
        next_node = node_dict.get(next_id)

        if not current_node or not next_node:
            continue

        dx = next_node.x - current_node.x
        dy = next_node.y - current_node.y
        target_dir = _get_absolute_direction(dx, dy)

        # Record intersections. Skip the very first node of the path
        # (the start location, which is a "main"-type node).
        if i > 0 and _is_intersection(current_id, node_dict):
            isect_indices.append(i)

        if current_dir is None:
            current_dir = target_dir
            continue

        turn_angle = _get_relative_turn(current_dir, target_dir)
        if turn_angle != 0 and _is_intersection(current_id, node_dict):
            turns.append((i, turn_angle))
        current_dir = target_dir

    # ── Phase 2: Build actions from ALL turns ──
    # The car is parked at the start location, facing away from the road.
    # First action: turn 180° to face the road.
    #
    # Then for each direction change, emit:
    #   forward(N) → turn(angle)
    # where N counts intersections since the last action point up to
    # and including the turn's own intersection.
    #
    # No turns → all intersections go into one forward segment.
    actions: list[tuple[str, float]] = []
    actions.append(("turn", 180.0))

    if turns:
        last_mark = 0  # path index of last turn (0 = start location)

        for turn_idx, turn_angle in turns:
            n = sum(1 for idx in isect_indices if last_mark < idx <= turn_idx)
            if n > 0:
                actions.append(("forward", float(n)))
            actions.append(("turn", float(turn_angle)))
            last_mark = turn_idx

        # Remaining intersections after the last turn
        remaining = sum(1 for idx in isect_indices if idx > last_mark)
        if remaining > 0:
            actions.append(("forward", float(remaining)))
    else:
        total = len(isect_indices)
        if total > 0:
            actions.append(("forward", float(total)))

    # ── Phase 3: Final approach to destination ──
    # After the last turn (or last forward if no turns), the car follows
    # the line until endpoint detection triggers DONE at the main location.
    actions.append(("arrive", 0.0))

    # ── Cleanup ──
    actions = [(a, p) for a, p in actions if not (a == "forward" and p == 0)]
    actions = _merge_consecutive_straights(actions)

    debug(f"[Map] Commands {start} → {end}: {len(actions)} actions")
    return [{"action": a, "param": p} for a, p in actions]


def get_cost(start: str, end: str) -> int | None:
    """
    Get the shortest-path cost (Manhattan distance) between two nodes.

    Args:
        start: Starting node ID
        end: Ending node ID

    Returns:
        Total cost in meters, or None if unreachable.
    """
    map_data = get_map()
    path = map_data.dijkstra(start, end)
    if path is None or len(path) < 2:
        return None
    return len(path) - 1
