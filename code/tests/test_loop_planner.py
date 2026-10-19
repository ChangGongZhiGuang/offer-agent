from interviewforge.loop.planner import RulePlanner, build_retrieval_query
from interviewforge.loop.session_plan import SessionPlan, PlanItem
from interviewforge.loop.types import LoopState


def test_rule_planner_ask():
    p = RulePlanner().plan_ask(LoopState(role="后端", topic="redis"))
    assert p.intent == "ask"
    assert p.tool_calls == ["search_questions"]
    # A: 即使没填 jd_keywords/dimension, query 至少含 topic + role
    assert "redis" in p.query and "后端" in p.query


def test_rule_planner_grade():
    p = RulePlanner().plan_grade(LoopState(role="后端", topic="redis"))
    assert p.intent == "grade"
    assert p.tool_calls == ["record_answer"]
    # 评分轮不需要检索 query
    assert p.query is None


def test_plan_ask_query_includes_dimension_first():
    """A: dimension 是本轮考察维度, 应排在最前。"""
    state = LoopState(role="后端", topic="缓存", dimension="缓存一致性")
    p = RulePlanner().plan_ask(state)
    assert p.query.startswith("缓存一致性")


def test_plan_ask_query_includes_jd():
    """A: 拼接顺序: dimension → topic → role → JD, 各自去重。"""
    state = LoopState(
        role="后端", topic="redis",
        jd_keywords=["MySQL", "Kafka", "高并发"], dimension="并发")
    q = build_retrieval_query(state)
    # dimension/topic/role/jd 全部出现
    for tok in ("并发", "redis", "后端", "MySQL", "Kafka", "高并发"):
        assert tok in q
    # 顺序: dimension 在 topic 之前
    assert q.index("并发") < q.index("redis")


def test_plan_ask_query_dedup():
    """重复 token 不应出现两次, 避免 embedding 噪声。"""
    state = LoopState(role="redis", topic="redis", jd_keywords=["redis"])
    q = build_retrieval_query(state)
    assert q.count("redis") == 1


def test_plan_ask_query_caps_jd():
    """JD 默认截前 3, 避免噪声压过核心维度。"""
    state = LoopState(
        role="后端", topic="x",
        jd_keywords=["A", "B", "C", "D", "E"])
    q = build_retrieval_query(state)
    # 默认 max_jd=3
    for kw in ("A", "B", "C"):
        assert kw in q
    assert "D" not in q and "E" not in q


def _state(turn, plan=None):
    s = LoopState(role="后端", topic="默认主题", jd_keywords=["高并发"])
    s.turn = turn
    s.session_plan = plan
    return s


def test_plan_ask_uses_session_plan_topic_and_dimension():
    plan = SessionPlan(items=[
        PlanItem(topic="redis", dimension="缓存层", difficulty="easy"),
        PlanItem(topic="mysql", dimension="存储层", difficulty="hard"),
    ])
    p = RulePlanner()
    plan0 = p.plan_ask(_state(0, plan))
    assert plan0.tool_calls == ["search_questions"]
    assert "缓存层" in plan0.query and "redis" in plan0.query
    plan1 = p.plan_ask(_state(1, plan))
    assert "存储层" in plan1.query and "mysql" in plan1.query


def test_plan_ask_falls_back_to_state_topic_without_plan():
    p = RulePlanner()
    plan = p.plan_ask(_state(0, None))
    assert "默认主题" in plan.query


def test_plan_grade_unchanged():
    assert RulePlanner().plan_grade(_state(0)).tool_calls == ["record_answer"]
