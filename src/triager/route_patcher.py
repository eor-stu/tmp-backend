# triager/route_patcher.py
# 路线修改器 - 使用 ChainOfThought 模式根据用户需求生成修改方案
#
# @author n1ghts4kura
# @date 2026-04-19
#
# 重构自 EOR-Team/ufc-2026/src/smart_triager/triager/route_patcher.py

from typing import Optional

import dspy

from src import logger
from src.map import get_map


def _get_default_route() -> list[str]:
    """从 map.json 的 main 节点中获取默认路线（按坐标排序）。"""
    map_data = get_map()
    main_nodes = [n for n in map_data.nodes if n.type == "main"]
    sorted_nodes = sorted(main_nodes, key=lambda n: (n.y, n.x))
    return [n.id for n in sorted_nodes[:6]]


class RoutePatcherSignature(dspy.Signature):
    '''Route patcher. Insert waypoints by timing: "现在"(after start), "给医生看病前"(before clinic), "拿完药之后"(after pharmacy), "最后"(before end). Output: {"patches":[{"type":"insert"|"delete","previous":loc,"this":loc,"next":loc}]}'''

    destination_clinic_id: str = dspy.InputField(
        desc="target clinic ID"
    )

    requirement_summary: list[dict] = dspy.InputField(
        desc="list of {when: timing, what: action} requirements"
    )

    current_route: list[str] = dspy.InputField(
        desc="path as location IDs, e.g. ['entrance', 'registration_center', 'surgery_clinic']"
    )

    patches: list[dict] = dspy.OutputField(
        desc='''list of patches: {type: "insert"|"delete", previous: loc, this: loc, next: loc}.
Example: [{"type": "insert", "previous": "entrance", "this": "toilet", "next": "registration_center"}].
Output [] if no modifications needed.'''
    )


class RoutePatcherCot(dspy.ChainOfThought):
    """路线修改器的 CoT 模块"""
    pass


def apply_patches(route: list[str], patches: list[dict]) -> list[str]:
    """
    应用 patches 到路线上。

    Args:
        route: 原路线
        patches: 修改方案列表

    Returns:
        修改后的路线
    """
    if not patches:
        return route.copy()

    # 深拷贝路线
    result = route.copy()

    # 先应用所有 delete 操作
    for patch in patches:
        if patch.get("type") == "delete":
            previous = patch.get("previous")
            this = patch.get("this")

            if previous in result:
                idx = result.index(previous)
                # 删除 previous 后的第一个 this
                if idx + 1 < len(result) and result[idx + 1] == this:
                    result.pop(idx + 1)

    # 再应用所有 insert 操作
    for patch in patches:
        if patch.get("type") == "insert":
            previous = patch.get("previous")
            this = patch.get("this")
            next_loc = patch.get("next")

            if previous in result and isinstance(this, str):
                idx = result.index(previous)
                if next_loc and next_loc in result:
                    next_idx = result.index(next_loc)
                    if next_idx == idx + 1:
                        result.insert(idx + 1, this)
                    else:
                        # 如果 next 不在紧邻位置，调整插入逻辑
                        result.insert(idx + 1, this)
                else:
                    # 追加到 previous 之后
                    result.insert(idx + 1, this)

    return result


def patch_route(
    destination_clinic_id: str,
    requirement_summary: list[dict],
    origin_route: Optional[list[str]] = None
) -> list[str]:
    """
    根据用户需求生成路线修改方案并应用。

    Args:
        destination_clinic_id: 目标诊室 ID
        requirement_summary: 用户需求列表，每个需求包含 'when'（时机）和 'what'（动作）
        origin_route: 原路线，默认为基于 surgery_clinic 的标准路线

    Returns:
        list[str]: 修改后的路线
    """
    
    if origin_route is None:
        origin_route = _get_default_route().copy()

    cot = RoutePatcherCot(RoutePatcherSignature)

    try:
        result = cot(
            destination_clinic_id=destination_clinic_id,
            requirement_summary=requirement_summary,
            current_route=origin_route,
        )

        # 提取 patches
        patches = result.patches if hasattr(result, 'patches') else []

        # 应用 patches 到路线
        final_route = apply_patches(origin_route, patches)

        logger.info(f"[RoutePatcher] Destination: {destination_clinic_id}, Requirements: {requirement_summary}")
        logger.info(f"[RoutePatcher] Reasoning: {result.reasoning}")
        logger.info(f"[RoutePatcher] Generated patches: {patches}")
        logger.info(f"[RoutePatcher] Final route: {final_route}")

        return final_route
    except Exception as e:
        logger.error(f"[RoutePatcher] Fallback to origin route due to error: {e}", exc_info=True)
        return origin_route.copy()


__all__ = [
    "patch_route",
    "RoutePatcherSignature",
    "apply_patches",
]
