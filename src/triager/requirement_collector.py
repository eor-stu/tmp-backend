# triager/requirement_collector.py
# 患者需求收集器
# 根据用户自述收集患者的具体需求（when/what 结构）
#
# @author n1ghts4kura
# @date 2026-04-18
#
# 重构自 EOR-Team/ufc-2026/src/smart_triager/triager/requirement_collector.py

import json
import dspy

from src import logger


class RequirementCollectorSignature(dspy.Signature):
    """Extract requirements as [{when: timing, what: action}]. List all if multiple."""

    requirement_from_user: str = dspy.InputField(
        desc="user requirement description"
    )

    requirements: list[dict[str, str]] = dspy.OutputField(
        desc="requirements. key: when (timing), value: what (action)."
    )


collector = dspy.ChainOfThought(
    RequirementCollectorSignature
)


DEFAULT_REQUIREMENTS: list[dict[str, str]] = []


def _normalize_requirements_value(value: object) -> list[dict[str, str]]:
    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        if "when" in value and "what" in value:
            return [value]

        nested_requirements = value.get("requirements")
        if isinstance(nested_requirements, list):
            return nested_requirements
        if isinstance(nested_requirements, dict):
            return [nested_requirements]

    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            return DEFAULT_REQUIREMENTS.copy()
        return _normalize_requirements_value(parsed_value)

    return DEFAULT_REQUIREMENTS.copy()


def collect_requirement(requirement_from_user: str) -> list[dict[str, str]]:
    """
    收集用户需求。

    Args:
        requirement_from_user: 用户的需求描述（中文）

    Returns:
        requirements_list: 解析后的需求列表，每个需求包含 when 和 what 字段
    """

    try:
        result = collector(
            requirement_from_user=requirement_from_user,
        )

        requirements = _normalize_requirements_value(getattr(result, "requirements", DEFAULT_REQUIREMENTS))

        logger.info(f"[RequirementCollector] Receive user requirement: {requirement_from_user}")
        logger.info(f"[RequirementCollector] Reasoning: {result.reasoning}")
        logger.info(f"[RequirementCollector] Extracted requirements: {requirements}")

        return requirements
    except Exception as e:
        logger.error(f"[RequirementCollector] Fallback to empty requirements due to error: {e}", exc_info=True)
        return DEFAULT_REQUIREMENTS.copy()

__all__ = [
    "collect_requirement",
    "RequirementCollectorSignature"
]