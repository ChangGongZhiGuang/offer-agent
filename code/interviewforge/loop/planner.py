"""PLAN 相位的计划来源 (注入式)。RulePlanner 按 SessionPlan 逐题取主题/维度。"""
from __future__ import annotations

from typing import Protocol

from interviewforge.loop.types import Bounds, LoopState, Plan


def should_follow_up(state: LoopState, score_result: dict, *,
                     bounds: Bounds, parent_qid: str) -> bool:
    """追问触发的规则边界 (与 Grader 的 LLM 判定双重把关, 全部满足才追):

    1) 每题上限 > 0 (追问未关闭); 2) LLM 判 need_follow_up=True;
    3) 分数处于两端: >=4 答得好→深挖 / <=2 答得卡→提示换角度;
    4) 该题未达每问上限; 5) 全场追问未达总量上限。
    """
    if bounds.max_follow_ups_per_question <= 0:
        return False
    if not score_result.get("need_follow_up", False):
        return False
    score = score_result.get("score")
    if not isinstance(score, int) or isinstance(score, bool):
        return False
    if not (score >= 4 or score <= 2):
        return False
    if state.follow_up_counts.get(parent_qid, 0) >= bounds.max_follow_ups_per_question:
        return False
    if state.total_follow_ups >= bounds.total_follow_up_cap():
        return False
    return True


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

    def plan_follow_up(self, state: LoopState) -> Plan:
        """追问计划: intent="follow_up" 不占主题额度 (verify_plan 只对 ask 卡
        remaining_questions), 且不声明工具 (追问基于问答链生成, 不查题库)。"""
        return Plan(intent="follow_up", tool_calls=[],
                    expected_outcome="一道针对上一答的追问")
