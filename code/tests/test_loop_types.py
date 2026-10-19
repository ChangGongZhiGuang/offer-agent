from interviewforge.loop.session_plan import SessionPlan, PlanItem
from interviewforge.loop.types import LoopState
from interviewforge.resume.types import CandidateProfile

from interviewforge.loop.types import Bounds, HaltReason, Phase, Plan


def test_phase_has_seven_states():
    names = {p.name for p in Phase}
    assert names == {"IDLE", "PLAN", "EXECUTE", "VERIFY", "COMPACT", "RESPOND", "HALT"}


def test_plan_defaults():
    p = Plan(intent="ask", tool_calls=["search_questions"])
    assert p.expected_outcome == ""


def test_bounds_defaults_and_from_settings():
    b = Bounds()
    assert b.max_turns == 30 and b.max_replans == 3 and b.max_questions == 3

    class _S:
        max_turns = 10
        max_replans = 2
        max_tool_calls_per_turn = 4
    b2 = Bounds.from_settings(_S(), max_questions=5)
    assert (b2.max_turns, b2.max_replans, b2.max_tool_calls_per_turn, b2.max_questions) == (10, 2, 4, 5)


def test_loopstate_defaults():
    s = LoopState(role="后端", topic="redis")
    assert s.phase == Phase.IDLE
    assert s.turn == 0 and s.replan_count == 0
    assert s.asked_ids == [] and s.recent_messages == []
    assert s.current_question is None and s.halted is None
    assert s.profile == "" and s.difficulty == "medium"


def test_loopstate_defaults_plan_and_profile_struct():
    s = LoopState(role="后端", topic="redis")
    assert s.session_plan is None
    assert s.profile_struct is None


def test_loopstate_holds_plan_and_profile_struct():
    plan = SessionPlan(items=[PlanItem(topic="redis", dimension="缓存层")])
    prof = CandidateProfile(skills=["Redis"])
    s = LoopState(role="后端", topic="redis", session_plan=plan, profile_struct=prof)
    assert s.session_plan.items[0].dimension == "缓存层"
    assert s.profile_struct.skills == ["Redis"]
