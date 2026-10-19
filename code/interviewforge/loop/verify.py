"""PEV 相位门: 纯函数规则校验。落地全局 procedural 规则的可纯函数部分。"""
from __future__ import annotations

from dataclasses import dataclass

from interviewforge.loop.types import Plan

# 合法工具白名单 (与 build_default_registry 对齐)
LEGAL_TOOLS = {"search_questions", "lookup_jd", "record_answer", "generate_report"}


@dataclass
class VerifyResult:
    passed: bool
    reason: str | None = None


def _fail(reason: str) -> VerifyResult:
    return VerifyResult(passed=False, reason=reason)


def verify_plan(plan: Plan, *, remaining_questions: int, max_tool_calls: int) -> VerifyResult:
    """PLAN 出口门: 合法工具 + 不超工具上限 + ask 时仍有剩余题数。"""
    if len(plan.tool_calls) > max_tool_calls:
        return _fail(f"too many tool calls: {len(plan.tool_calls)} > {max_tool_calls}")
    for tool in plan.tool_calls:
        if tool not in LEGAL_TOOLS:
            return _fail(f"illegal tool: {tool}")
    if plan.intent == "ask" and remaining_questions <= 0:
        return _fail("no remaining questions")
    return VerifyResult(passed=True)


def verify_question(structured: dict, asked_ids: list[str]) -> VerifyResult:
    """VERIFY 门 (出题): 含 question 字段 + 无重复题 (no_duplicate_question)。"""
    if "question" not in structured or not structured["question"]:
        return _fail("missing question field")
    qid = structured.get("question_id")
    if qid is not None and qid in asked_ids:
        return _fail(f"duplicate question: {qid}")
    return VerifyResult(passed=True)


def verify_score(structured: dict) -> VerifyResult:
    """VERIFY 门 (评分): score 必须是 1-5 整数 (score_in_range)。"""
    score = structured.get("score")
    if not isinstance(score, int) or isinstance(score, bool):
        return _fail(f"score not an int: {score!r}")
    if not (1 <= score <= 5):
        return _fail(f"score out of range: {score}")
    return VerifyResult(passed=True)
