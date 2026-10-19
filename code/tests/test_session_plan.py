from interviewforge.loop.session_plan import build_session_plan
from interviewforge.resume.types import CandidateProfile


def _profile(topics):
    return CandidateProfile(topic_plan=topics)


def test_plan_length_matches_num_questions():
    plan = build_session_plan(_profile(["redis", "mysql"]), ["存储层", "缓存层"], 3)
    assert len(plan.items) == 3


def test_topics_cycle_through_topic_plan():
    plan = build_session_plan(_profile(["redis", "mysql"]), ["存储层"], 4)
    assert [i.topic for i in plan.items] == ["redis", "mysql", "redis", "mysql"]


def test_dimensions_cycle_through_methodology():
    plan = build_session_plan(_profile(["redis"]), ["存储层", "缓存层"], 3)
    assert [i.dimension for i in plan.items] == ["存储层", "缓存层", "存储层"]


def test_difficulty_ramps_up():
    plan = build_session_plan(_profile(["redis"]), ["存储层"], 3)
    assert [i.difficulty for i in plan.items] == ["easy", "medium", "hard"]


def test_fallback_topic_when_topic_plan_empty():
    plan = build_session_plan(_profile([]), [], 2, fallback_topic="通用")
    assert [i.topic for i in plan.items] == ["通用", "通用"]
    assert all(i.dimension is None for i in plan.items)
