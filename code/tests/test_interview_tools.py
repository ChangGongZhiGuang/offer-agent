from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryKind
from interviewforge.memory.working import WorkingMemory
from interviewforge.tools.interview_tools import (
    build_default_registry,
    make_generate_report,
    make_lookup_jd,
    make_record_answer,
    make_search_questions,
)


def _memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def test_search_questions_stub_returns_list():
    tool = make_search_questions()
    out = tool(role="后端", topic="redis")
    assert isinstance(out, list) and out[0]["question_id"] == "stub-1"


def test_search_questions_uses_injected_retriever():
    captured = {}
    def fake_retriever(role, topic, difficulty=None):
        captured["role"] = role
        captured["difficulty"] = difficulty
        return [{"question_id": "rag-1"}]
    tool = make_search_questions(retriever=fake_retriever)
    out = tool(role="后端", topic="redis", difficulty="hard")
    assert out == [{"question_id": "rag-1"}]
    assert captured["role"] == "后端"
    assert captured["difficulty"] == "hard"


def test_lookup_jd_returns_requirements():
    tool = make_lookup_jd()
    out = tool(company="字节", role="后端")
    assert out["company"] == "字节"
    assert isinstance(out["requirements"], list) and len(out["requirements"]) > 0


def test_record_answer_writes_episodic(tmp_path):
    mem = _memory(tmp_path)
    tool = make_record_answer(mem)
    result = tool(question_id="q1", score=4, notes="答对索引")
    assert result["recorded"] == "q1"
    items = mem.episodic.all()
    assert len(items) == 1
    assert items[0].kind == MemoryKind.EPISODIC
    assert items[0].content["question_id"] == "q1"
    assert items[0].content["score"] == 4
    assert items[0].salience == 4.0


def test_record_answer_notes_optional(tmp_path):
    mem = _memory(tmp_path)
    tool = make_record_answer(mem)
    result = tool(question_id="q2", score=3)
    assert result["recorded"] == "q2"


def test_generate_report_aggregates(tmp_path):
    mem = _memory(tmp_path)
    make_record_answer(mem)(question_id="q1", score=4, notes="")
    make_record_answer(mem)(question_id="q2", score=2, notes="")
    report = make_generate_report(mem)()
    assert report["answered"] == 2
    assert report["avg_score"] == 3.0


def test_record_answer_stores_weakness_tags(tmp_path):
    mem = _memory(tmp_path)
    tool = make_record_answer(mem)
    tool(question_id="q1", score=3, notes="还行", weakness_tags=["边界条件", "时间复杂度"])
    items = mem.episodic.all()
    assert items[0].content["weakness_tags"] == ["边界条件", "时间复杂度"]


def test_build_default_registry_has_four_tools(tmp_path):
    reg = build_default_registry(_memory(tmp_path))
    assert set(reg.names()) == {
        "search_questions", "lookup_jd", "record_answer", "generate_report"
    }


def test_record_answer_persists_dimension(tmp_path):
    mem = _memory(tmp_path)
    tool = make_record_answer(mem)
    tool.run(question_id="be-1", score=4, notes="ok", weakness_tags=["x"], dimension="缓存层")
    item = mem.episodic.all()[-1]
    assert item.content["dimension"] == "缓存层"
