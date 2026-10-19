import pytest

pytest.importorskip("fastapi")

from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.loop.machine import InterviewLoop
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore
from interviewforge.resume.types import CandidateProfile

_VOCAB = ["redis", "mysql", "分布式", "锁", "索引"]


class _RoutingFakeModel:
    """按 prompt 区分 Examiner / Grader 返回对应 JSON。"""
    def chat(self, messages):
        text = " ".join(m.content for m in messages)
        if "评分" in text:
            return '{"score": 4, "weakness_tags": ["边界"], "feedback": "不错"}'
        return ('{"question": "如何实现分布式锁?", "rubric": "看过期时间", '
                '"expected_points": ["SETNX"]}')


def _retriever():
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    embed = make_keyword_embedder(_VOCAB)
    qs = [
        Question(id="be-1", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard"),
        Question(id="be-2", role="后端", topic="redis",
                 stem="Redis 锁误删如何避免", answer="唯一 value", difficulty="hard"),
    ]
    seed_questions(qb, vs, embed, qs)
    return Retriever(vs, qb, embed)


def _factory(tmp_path):
    return SessionFactory(retriever=_retriever(), model_client=_RoutingFakeModel(),
                          base_dir=tmp_path)


def test_factory_builds_started_loop(tmp_path):
    loop = _factory(tmp_path).build(session_id="s1", role="后端", topic="redis",
                                    profile="擅长SQL", num_questions=2)
    assert isinstance(loop, InterviewLoop)
    assert loop.state is not None and loop.state.role == "后端"
    assert loop.bounds.max_questions == 2
    # 混合方案: LLM 个性化题干保留 (题库锚点不再覆盖)
    assert loop.ask_question() == "如何实现分布式锁?"


def test_factory_routes_free_text_profile_into_state(tmp_path):
    """仅提供自由文本画像 (无 profile_struct) 时, 应注入 state.profile,
    否则 Examiner 出题会忽略简历 (生成与候选人无关的题)。"""
    loop = _factory(tmp_path).build(session_id="s1", role="后端", topic="redis",
                                    profile="秒杀系统Redis集群预扣库存,分布式CAP较弱",
                                    num_questions=2)
    assert "秒杀系统Redis集群预扣库存" in loop.state.profile


def test_store_create_and_get(tmp_path):
    store = SessionStore(_factory(tmp_path))
    sid = store.create(role="后端", topic="redis", num_questions=3)
    assert isinstance(sid, str) and store.get(sid) is not None
    assert store.get("missing") is None


def test_store_sessions_are_isolated(tmp_path):
    store = SessionStore(_factory(tmp_path))
    s1 = store.create(role="后端", topic="redis", num_questions=3)
    s2 = store.create(role="后端", topic="redis", num_questions=3)
    store.get(s1).ask_question()
    assert store.get(s1).state.asked_ids != []
    assert store.get(s2).state.asked_ids == []
    assert store.get(s1).memory is not store.get(s2).memory


def test_store_remove(tmp_path):
    store = SessionStore(_factory(tmp_path))
    sid = store.create(role="后端", topic="redis")
    store.remove(sid)
    assert store.get(sid) is None


def test_factory_builds_plan_and_injects_methodology(tmp_path):
    retriever = _retriever()
    fake_model = _RoutingFakeModel()
    factory = SessionFactory(retriever=retriever, model_client=fake_model,
                             base_dir=tmp_path)
    loop = factory.build(session_id="s1", role="后端", topic="redis",
                         profile_struct=CandidateProfile(topic_plan=["redis", "mysql"]),
                         num_questions=3, jd_keywords=["高并发"])
    assert loop.state.session_plan is not None
    assert len(loop.state.session_plan.items) == 3
    assert loop.state.profile_struct.topic_plan == ["redis", "mysql"]
    # backend-interview SKILL 命中 → Examiner 拿到非空方法论
    assert loop.examiner.methodology
