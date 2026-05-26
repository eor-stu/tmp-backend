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
        return 90
    elif diff == 270:
        return -90
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
    Determine if a road node is a true intersection.

    A node is considered an intersection when ALL of the following are true:
    1. The node itself is of type "nav" (a road node)
    2. All 4 orthogonally adjacent cells (up/down/left/right at distance 1)
       also contain "nav"-type nodes

    This definition ensures the car only counts road junctions where
    horizontal and vertical lines genuinely cross, and does NOT count:
    - Dead-end road nodes (missing neighbors)
    - Edge road nodes (one side has no road)
    - Start/end "main"-type nodes like entrances or clinics
    """
    node = node_dict.get(node_id)
    if node is None or node.type != "nav":
        return False

    x, y = int(node.x), int(node.y)
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        neighbor_id = f"road_{x + dx}_{y + dy}"
        neighbor = node_dict.get(neighbor_id)
        if neighbor is None or neighbor.type != "nav":
            return False

    return True


def get_commands(start: str, end: str) -> list[dict[str, str | float]]:
    """
    Convert a path between two map nodes into car control commands.

    The car navigates by following a black line on the ground. Commands are
    expressed in terms of INTERSECTIONS (junction points where lines cross),
    not raw grid coordinates.

    An intersection is a road node whose 4 orthogonally adjacent cells are
    all also roads. The car passes through intersections by following the
    line; the only deliberate turn happens at the LAST direction change
    on the path (where the car must choose a different direction to reach
    the destination).

    Example: entrance → pharmacy
        Path: entrance → (grid nodes southbound) → road_2_5 → pharmacy
        All intersections on path: road_2_7 (#1), road_2_5 (#2)
        Last direction change: at road_2_5 (south → west)
        #1 is passed through, #2 is the turning point
        Commands: [forward(1), turn(-90)]

    Example: internal_clinic → toilet
        Path: IC → east to road_2_3 → south to road_2_7 → east to toilet
        All intersections on path: road_2_3 (#1), road_2_5 (#2), road_2_7 (#3)
        Last direction change: at road_2_7 (south → east)
        #1 and #2 are passed through, #3 is the turning point
        Commands: [forward(2), turn(90)]

    Args:
        start: Starting node ID (e.g. "entrance", "internal_clinic")
        end: Ending node ID (e.g. "pharmacy", "toilet")

    Returns:
        List of {action, param} dicts, e.g.:
            [{"action": "forward", "param": 2.0}, {"action": "turn", "param": 90}]
    """
    map_data = get_map()
    path = map_data.dijkstra(start, end)
    if path is None or len(path) < 2:
        return []

    node_dict: dict[str, object] = {n.id: n for n in map_data.nodes}

    # ── Phase 1: Identify all intersections and direction changes on the path ──
    # We need to know: which nodes are intersections, and where the path turns.
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
        if turn_angle != 0:
            turns.append((i, turn_angle))
        current_dir = target_dir

    # ── Phase 2: Partition intersections around the LAST turn ──
    # All intersections before the last turn are "passed through";
    # the intersection at the last turn is the turning point (NOT counted
    # in the forward parameter — the car stops and turns at it).
    # Intersections after the last turn (if any) go to the final forward.
    #
    # If there are no turns, all intersections are passed through.
    if turns:
        turn_idx, turn_angle = turns[-1]

        passed = sum(1 for idx in isect_indices if idx < turn_idx)
        after = sum(1 for idx in isect_indices if idx > turn_idx)

        actions: list[tuple[str, float]] = []
        if passed > 0:
            actions.append(("forward", float(passed)))
        actions.append(("turn", float(turn_angle)))
        if after > 0:
            actions.append(("forward", float(after)))
    else:
        total = len(isect_indices)
        actions = [("forward", float(total))] if total > 0 else []

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
