# triager/condition_collector.py
# User physical condition collector
#
# @author n1ghts4kura
# @date 2026-04-18
#
# Refactored from EOR-Team/ufc-2026/src/smart_triager/triager/condition_collector.py

import dspy

from src import logger


class ConditionCollectorSignature(dspy.Signature):
    """Extract: duration, severity, body_parts, description, other_relevant_info. Build on prior conclusions if provided."""

    previous_conclusions: str = dspy.InputField(
        desc = "prior analysis conclusions, if any"
    )

    description_from_user: str = dspy.InputField(
        desc = "user symptom description"
    )

    duration: str = dspy.OutputField(
        desc = "symptom duration"
    )

    severity: str = dspy.OutputField(
        desc = "severity level"
    )

    body_parts: str = dspy.OutputField(
        desc = "affected body parts"
    )

    description: str = dspy.OutputField(
        desc = "symptom description"
    )

    other_relevant_info: list[str] = dspy.OutputField(
        desc = "other relevant info"
    )


collector = dspy.Predict(
    ConditionCollectorSignature
)


DEFAULT_CONDITION = {
    "duration": "未填写",
    "severity": "未填写",
    "body_parts": "未填写",
    "description": "未填写",
    "other_relevant_info": [],
}


def _normalize_condition_value(value: object) -> str:
    if value in (None, "", "unknown"):
        return "未填写"
    return str(value)


def collect_condition(description_from_user: str, previous_conclusions: list[str] = []) -> dict:
    """Collect user physical condition information.

    Args:
        description_from_user: 用户的症状描述（中文）
        previous_conclusions: 之前的病情分析结论（如果有的话）

    Returns:
        dict: 包含症状信息的字典，包括 duration, severity, body_parts, description, other_relevant_info 字段
    """

    previous_conclusions_str = ""

    if previous_conclusions:
        for i in range(len(previous_conclusions)):
            previous_conclusions_str += f"[{ i + 1 }] { previous_conclusions[i] };"

    try:
        resp = collector(
            description_from_user = description_from_user,
            previous_conclusions = previous_conclusions_str,
        )

        duration = _normalize_condition_value(getattr(resp, "duration", None))
        severity = _normalize_condition_value(getattr(resp, "severity", None))
        body_parts = _normalize_condition_value(getattr(resp, "body_parts", None))
        description = _normalize_condition_value(getattr(resp, "description", None))
        other_relevant_info = getattr(resp, "other_relevant_info", [])

        logger.info(f"[ConditionCollector] Input: {description_from_user}; prev: {previous_conclusions_str}")
        logger.info(f"[ConditionCollector] Extracted: duration={duration}, severity={severity}, body_parts={body_parts}")

        return {
            "duration": duration,
            "severity": severity,
            "body_parts": body_parts,
            "description": description,
            "other_relevant_info": other_relevant_info
        }
    except Exception as e:
        logger.error(f"[ConditionCollector] Fallback to default condition due to error: {e}", exc_info=True)
        return DEFAULT_CONDITION.copy()


__all__ = [
    "collect_condition"
]
