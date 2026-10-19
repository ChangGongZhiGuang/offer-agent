import pytest

from interviewforge.context.compaction import (
    BudgetReductionLayer,
    CompactionPipeline,
    ContextCollapseLayer,
)
from interviewforge.loop.adapter import SearchAdapter
from interviewforge.loop.machine import InterviewLoop
from interviewforge.loop.planner import RulePlanner
from interviewforge.loop.session_plan import PlanItem, SessionPlan
from interviewforge.loop.types import Bounds, HaltReason, Phase
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryKind, RecallQuery
from interviewforge.memory.working import WorkingMemory
from interviewforge.persistence.transcript import Transcript
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore
from interviewforge.subagents.base import SubResult, SubTask
from interviewforge.subagents.examiner import Examiner
from interviewforge.subagents.grader import Grader
from interviewforge.tools.interview_tools import build_default_registry
from interviewforge.types import Message, Role

_VOCAB = ["redis", "mysql", "分布式", "锁", "索引"]


def _embed(texts):
    return [[float(t.lower().count(w)) for w in _VOCAB] for t in texts]


class _FakeModel:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages):
        return self.reply


_EXAM_JSON = ('{"question": "如何实现分布式锁?", "rubric": "看过期时间", '
              '"expected_points": ["SETNX"]}')
_GRADE_OK = '{"score": 4, "weakness_tags": ["边界"], "feedback": "不错"}'
_GRADE_BAD = '{"score": 9, "weakness_tags": [], "feedback": "x"}'


def _memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def _retriever():
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    qs = [
        Question(id="be-1", role="后端", topic="redis",
                 stem="Redis 锁误删如何避免", answer="唯一 value", difficulty="hard"),
        Question(id="be-2", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard"),
    ]
    seed_questions(qb, vs, _embed, qs)
    return Retriever(vs, qb, _embed)


def _build(tmp_path, grade_reply=_GRADE_OK, *, bounds=None, pipeline=None, token_budget=24000):
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    registry = build_default_registry(mem, retriever=adapter)
    examiner = Examiner(_FakeModel(_EXAM_JSON), registry)
    grader = Grader(_FakeModel(grade_reply), registry)
    loop = InterviewLoop(
        memory=mem, examiner=examiner, grader=grader, planner=RulePlanner(),
        registry=registry, search_adapter=adapter,
        transcript=Transcript(tmp_path / "t.jsonl"),
        bounds=bounds or Bounds(max_questions=3),
        pipeline=pipeline, token_budget=token_budget,
    )
    loop.start(role="后端", topic="redis", profile="擅长SQL")
    return loop, mem


def test_ask_question_returns_question_and_tracks_state(tmp_path):
    loop, mem = _build(tmp_path)
    q = loop.ask_question()
    # 混合方案: LLM 个性化题干保留 (不再被题库原文覆盖)
    assert q == "如何实现分布式锁?"
    assert loop.state.asked_ids == ["be-1"]
    assert loop.state.turn == 1
    assert loop.state.phase == Phase.IDLE
    working = mem.recall(RecallQuery(kinds=[MemoryKind.WORKING], limit=10))
    assert any(it.content.get("question_id") == "be-1" for it in working)


def test_submit_answer_grades_and_records_episodic(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    res = loop.submit_answer("我会用 SETNX 加过期时间")
    assert res["score"] == 4
    assert loop.state.current_question is None
    items = mem.episodic.all()
    assert len(items) == 1
    assert items[0].content["question_id"] == "be-1"
    assert items[0].content["score"] == 4


def test_dedup_across_two_questions(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    loop.submit_answer("a1")
    q2 = loop.ask_question()
    assert loop.state.asked_ids == ["be-1", "be-2"]
    assert q2 is not None


def test_invalid_score_replans_then_halts(tmp_path):
    loop, mem = _build(tmp_path, grade_reply=_GRADE_BAD,
                       bounds=Bounds(max_questions=3, max_replans=2))
    loop.ask_question()
    res = loop.submit_answer("乱答")
    assert res is None
    assert loop.state.halted == HaltReason.MAX_REPLANS


def test_max_turns_halts(tmp_path):
    loop, mem = _build(tmp_path, bounds=Bounds(max_turns=1, max_questions=5))
    loop.ask_question()
    q2 = loop.ask_question()
    assert q2 is None
    assert loop.state.halted == HaltReason.MAX_TURNS


def test_finish_generates_report_and_halts(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    loop.submit_answer("a1")
    report = loop.finish()
    assert report["answered"] == 1
    assert report["avg_score"] == 4
    assert loop.state.halted == HaltReason.COMPLETED


def test_transcript_records_transitions(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    events = Transcript(tmp_path / "t.jsonl").replay()
    types = {e.type for e in events}
    assert "transition" in types
    phases = [e.payload.get("to") for e in events if e.type == "transition"]
    assert "plan" in phases and "execute" in phases and "verify" in phases


def test_planner_query_reaches_retriever(tmp_path):
    """A: jd_keywords/dimension/profile 应经 Planner 拼成 query 传到 Retriever。"""
    seen: list[str] = []

    class _SpyRetriever:
        """嗅探 retrieve_one 的 query_text, 但仍走真正题库以让 loop 跑通。"""
        def __init__(self, inner):
            self.inner = inner

        def retrieve_one(self, query_text, **kw):
            seen.append(query_text)
            return self.inner.retrieve_one(query_text, **kw)

    mem = _memory(tmp_path)
    adapter = SearchAdapter(_SpyRetriever(_retriever()), mem)
    registry = build_default_registry(mem, retriever=adapter)
    examiner = Examiner(_FakeModel(_EXAM_JSON), registry)
    grader = Grader(_FakeModel(_GRADE_OK), registry)
    loop = InterviewLoop(
        memory=mem, examiner=examiner, grader=grader, planner=RulePlanner(),
        registry=registry, search_adapter=adapter,
        transcript=Transcript(tmp_path / "t.jsonl"),
        bounds=Bounds(max_questions=2),
    )
    loop.start(role="后端", topic="redis", profile="3年Java 分布式锁",
               jd_keywords=["MySQL", "Kafka"], dimension="缓存一致性")
    loop.ask_question()
    assert seen, "retriever 应被调用过一次"
    q = seen[-1]
    # 维度/主题/岗位/JD 全部出现, 且 dimension 在最前
    assert q.startswith("缓存一致性")
    for tok in ("redis", "后端", "MySQL", "Kafka"):
        assert tok in q
    # profile 不再注入 query (新实现通过 session_plan 取主题/维度)


def test_compact_runs_when_budget_tiny(tmp_path):
    pipeline = CompactionPipeline([
        BudgetReductionLayer(single_output_cap=5),
        ContextCollapseLayer(collapse_ratio=0.1, keep_recent=1),
    ])
    loop, mem = _build(tmp_path, pipeline=pipeline, token_budget=10)
    loop.state.recent_messages = [
        Message(Role.ASSISTANT, "很长的内容 " * 20),
        Message(Role.USER, "回答内容 " * 20),
    ]
    loop.ask_question()
    events = Transcript(tmp_path / "t.jsonl").replay()
    assert any(e.type == "compact" for e in events)


# ---------------------------------------------------------------------------
# 混合出题: LLM 题干保留 + SessionPlan 驱动主题/维度
# ---------------------------------------------------------------------------

class _PlanExaminer:
    """最简假出题官: 记录被传入的 topic, 返回固定 LLM 个性化题。"""

    def __init__(self):
        self.last_topic: str | None = None

    def run(self, task: SubTask) -> SubResult:
        self.last_topic = task.inputs["topic"]
        dim = task.inputs.get("dimension")
        return SubResult(
            summary="fake",
            structured={
                "question": "LLM个性化题",
                "rubric": "r",
                "expected_points": [],
                "dimension": dim,
            },
        )


class _FakeSearchAdapter:
    """最简假检索适配器: 返回固定 id/题干/参考答案供断言。"""

    last_id: str = "q-fake"
    last_question: str = "题库原文"          # 与 LLM 题干故意不同, 证明不被覆盖
    last_reference_answer: str = "参考答案"

    def set_next_query(self, query: str) -> None:
        pass  # 不做任何事


class _FakeGrader:
    """最简假评分官: 总是返回合法评分。"""

    def run(self, task: SubTask) -> SubResult:
        return SubResult(
            summary="fake grade",
            structured={"score": 3, "weakness_tags": [], "feedback": "ok"},
        )


def test_ask_keeps_llm_question_and_uses_plan_topic(tmp_path):
    """(a) LLM 题干不被题库原文覆盖; (b) topic 来自 SessionPlan; (c) dimension 落到存储题上。"""
    mem = _memory(tmp_path)
    registry = build_default_registry(mem, retriever=None)
    fake_examiner = _PlanExaminer()
    fake_grader = _FakeGrader()
    fake_adapter = _FakeSearchAdapter()

    loop = InterviewLoop(
        memory=mem,
        examiner=fake_examiner,
        grader=fake_grader,
        planner=RulePlanner(),
        registry=registry,
        search_adapter=fake_adapter,
        transcript=Transcript(tmp_path / "t.jsonl"),
        bounds=Bounds(max_questions=3),
    )
    loop.start(role="后端", topic="redis", profile="")
    # 注入 SessionPlan: 第 0 轮 -> topic="缓存", dimension="缓存层"
    loop.state.session_plan = SessionPlan(
        items=[PlanItem(topic="缓存", dimension="缓存层", difficulty="easy")]
    )

    q = loop.ask_question()

    assert q == "LLM个性化题"                           # (a) LLM 题干保留, 未被 "题库原文" 覆盖
    assert loop.state.current_question["dimension"] == "缓存层"  # (c) dimension 落到题上
    assert fake_examiner.last_topic == "缓存"           # (b) topic 来自 SessionPlan
