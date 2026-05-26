# triager/clinic_selector.py
# 诊室选择智能体 - 根据结构化症状数据选择合适的诊室
#
# @author n1ghts4kura
# @date 2026-04-18
#
# 重构自 EOR-Team/ufc-2026/src/smart_triager/triager/clinic_selector.py

import dspy

from src import logger
from src.map.tools import get_map


def _get_clinic_ids() -> list[str]:
    """从地图数据中动态获取所有以 _clinic 结尾的 main 节点 ID。"""
    all_main_ids = get_map().get_main_node_ids()
    return sorted([nid for nid in all_main_ids if nid.endswith("_clinic")])


_CLINIC_IDS: list[str] = _get_clinic_ids()
_clinic_ids_str: str = " ".join(_CLINIC_IDS)

DEFAULT_CLINIC_ID: str = _CLINIC_IDS[0] if _CLINIC_IDS else "emergency_clinic"
VALID_CLINIC_IDS: set[str] = set(_CLINIC_IDS)


class ClinicSelectorSignature(dspy.Signature):
    """Select clinic: pediatric_clinic(child<14), emergency_clinic(severe), surgery_clinic(surgical), internal_clinic(default). Examples: fever cough adult→internal_clinic | severe chest pain→emergency_clinic | child fever→pediatric_clinic | broken bone→surgery_clinic"""

    body_parts: str = dspy.InputField(desc="affected body parts")
    duration: str = dspy.InputField(desc="symptom duration")
    severity: str = dspy.InputField(desc="severity: 轻微/中等/严重")
    description: str = dspy.InputField(desc="symptom description")
    other_relevant_info: list[str] = dspy.InputField(desc="age, history, etc.")

    clinic_selection: str = dspy.OutputField(
        desc = f'one of: {_clinic_ids_str}'
    )


collector = dspy.Predict(
    ClinicSelectorSignature
)


def select_clinic(
    body_parts: str,
    duration: str,
    severity: str,
    description: str,
    other_relevant_info: list[str]
) -> str:
    """
    根据患者症状选择合适的诊室。

    Args:
        body_parts: 受影响的身体部位
        duration: 症状持续时间
        severity: 症状严重程度（轻微/中等/严重）
        description: 症状详细描述
        other_relevant_info: 其他相关信息（如年龄、病史等）

    Returns:
        str: 选择的诊室 ID
    """

    try:
        resp = collector(
            body_parts=body_parts,
            duration=duration,
            severity=severity,
            description=description,
            other_relevant_info=other_relevant_info,
        )

        clinic_selection = resp["clinic_selection"] if isinstance(resp, dict) else getattr(resp, "clinic_selection", DEFAULT_CLINIC_ID)
        if clinic_selection not in VALID_CLINIC_IDS:
            clinic_selection = DEFAULT_CLINIC_ID

        logger.info(f"[ClinicSelector] body_parts={body_parts}, severity={severity}, duration={duration}")
        logger.info(f"[ClinicSelector] Selected clinic: {clinic_selection}")

        return clinic_selection
    except Exception as e:
        logger.error(f"[ClinicSelector] Fallback to default clinic due to error: {e}", exc_info=True)
        return DEFAULT_CLINIC_ID


__all__ = [
    "select_clinic",
    "ClinicSelectorSignature"
]
