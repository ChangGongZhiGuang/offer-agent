"""PLAN 相位的计划来源 (注入式)。RulePlanner 按 SessionPlan 逐题取主题/维度。"""
from __future__ import annotations

from typing import Protocol

from interviewforge.loop.types import LoopState, Plan


def _current_item(state: LoopState):
    """取当轮 PlanItem; 无 plan 或越界时返回 None。"""
    plan = state.session_plan
    if plan is None or not plan.items:
        return None
    idx = min(state.turn, len(plan.items) - 1)
    return plan.items[idx]


def build_retrieval_query(state: LoopState, *, max_jd: int = 3) -> str:
    """拼接检索 query: 维度 → 主题 → 岗位 → JD 关键技能。顺序便于人读, embedding 不在意位置。"""
    item = _current_item(state)
    topic = item.topic if item else state.topic
    dimension = item.dimension if item else state.dimension

    parts: list[str] = []

    def _push(token: str | None) -> None:
        if token and token.strip() and token not in parts:
            parts.append(token.strip())

    _push(dimension)
    _push(topic)
    _push(state.role)
    for kw in state.jd_keywords[:max_jd]:
        _push(kw)
    return " ".join(parts)


class Planner(Protocol):
    def plan_ask(self, state: LoopState) -> Plan: ...
    def plan_grade(self, state: LoopState) -> Plan: ...


class RulePlanner:
    """规则式计划: 出题用 search_questions, 评分用 record_answer。"""

    def plan_ask(self, state: LoopState) -> Plan:
        return Plan(intent="ask", tool_calls=["search_questions"],
                    expected_outcome="一道未问过且难度匹配的题",
                    query=build_retrieval_query(state))

    def plan_grade(self, state: LoopState) -> Plan:
        return Plan(intent="grade", tool_calls=["record_answer"],
                    expected_outcome="一个 1-5 的合法评分")
