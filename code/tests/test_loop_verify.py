from interviewforge.loop.types import Plan
from interviewforge.loop.verify import (
    VerifyResult,
    verify_plan,
    verify_question,
    verify_score,
)


def test_verify_plan_ok():
    p = Plan(intent="ask", tool_calls=["search_questions"])
    r = verify_plan(p, remaining_questions=2, max_tool_calls=5)
    assert r.passed and r.reason is None


def test_verify_plan_illegal_tool():
    p = Plan(intent="ask", tool_calls=["rm_rf"])
    r = verify_plan(p, remaining_questions=2, max_tool_calls=5)
    assert not r.passed and "rm_rf" in r.reason


def test_verify_plan_tool_storm():
    p = Plan(intent="ask", tool_calls=["search_questions"] * 6)
    r = verify_plan(p, remaining_questions=2, max_tool_calls=5)
    assert not r.passed and "too many" in r.reason


def test_verify_plan_no_remaining_questions():
    p = Plan(intent="ask", tool_calls=["search_questions"])
    r = verify_plan(p, remaining_questions=0, max_tool_calls=5)
    assert not r.passed and "remaining" in r.reason


def test_verify_question_ok():
    r = verify_question({"question": "q", "question_id": "be-2"}, asked_ids=["be-1"])
    assert r.passed


def test_verify_question_missing_field():
    r = verify_question({"question_id": "be-2"}, asked_ids=[])
    assert not r.passed and "question" in r.reason


def test_verify_question_duplicate():
    r = verify_question({"question": "q", "question_id": "be-1"}, asked_ids=["be-1"])
    assert not r.passed and "duplicate" in r.reason


def test_verify_score_ok():
    assert verify_score({"score": 4}).passed


def test_verify_score_out_of_range():
    assert not verify_score({"score": 9}).passed


def test_verify_score_not_int():
    assert not verify_score({"score": "good"}).passed


def test_verify_result_is_dataclass():
    r = VerifyResult(passed=True)
    assert r.reason is None
