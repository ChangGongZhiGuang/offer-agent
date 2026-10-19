"""MCPSearchAdapter / make_mcp_jd_lookup: 用 fake pool, 不起子进程, 只验包装行为。"""
from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from interviewforge.mcp.tools import MCPSearchAdapter, make_mcp_jd_lookup
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.memory.working import WorkingMemory


class FakePool:
    """记录 call 并回放预置结果。"""

    def __init__(self, scripted):
        self.scripted = scripted
        self.calls: list[tuple] = []

    def call(self, server, tool, args):
        self.calls.append((server, tool, args))
        return self.scripted.get((server, tool), None)


@pytest.fixture()
def memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "ep.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def test_search_adapter_returns_first_and_sets_last_id(memory):
    pool = FakePool({("questions", "search_questions"): [
        {"question_id": "be-1", "question": "Q1", "difficulty": "hard",
         "reference_answer": "SETNX"},
        {"question_id": "be-2", "question": "Q2", "difficulty": "medium",
         "reference_answer": "回表"},
    ]})
    adapter = MCPSearchAdapter(pool, memory)
    res = adapter(role="后端", topic="redis")
    # 主上下文里不应出现 reference_answer (留给 adapter 持有)
    assert res == [{"question_id": "be-1", "question": "Q1", "difficulty": "hard"}]
    assert adapter.last_id == "be-1"
    assert adapter.last_question == "Q1"
    assert adapter.last_reference_answer == "SETNX"  # D
    assert pool.calls == [("questions", "search_questions",
                           {"role": "后端", "topic": "redis"})]


def test_search_adapter_dedups_via_episodic(memory):
    memory.remember(MemoryItem(
        kind=MemoryKind.EPISODIC, content={"question_id": "be-1", "score": 4}))
    pool = FakePool({("questions", "search_questions"): [
        {"question_id": "be-1", "question": "Q1", "difficulty": "hard",
         "reference_answer": "A1"},
        {"question_id": "be-2", "question": "Q2", "difficulty": "medium",
         "reference_answer": "A2"},
    ]})
    adapter = MCPSearchAdapter(pool, memory)
    res = adapter(role="后端", topic="redis")
    assert res[0]["question_id"] == "be-2"
    assert adapter.last_id == "be-2"
    assert adapter.last_reference_answer == "A2"


def test_mcp_adapter_forwards_next_query_to_server(memory):
    """A: set_next_query 后, MCP 调用 args 应携带 query 字段; 用完即清。"""
    pool = FakePool({("questions", "search_questions"): [
        {"question_id": "x", "question": "Q", "difficulty": "medium",
         "reference_answer": "A"}]})
    adapter = MCPSearchAdapter(pool, memory)
    adapter.set_next_query("缓存一致性 redis 后端")
    adapter(role="后端", topic="redis")
    assert pool.calls[-1][2] == {"role": "后端", "topic": "redis",
                                 "query": "缓存一致性 redis 后端"}
    # 第二次没 set, 不应携带 query
    adapter(role="后端", topic="redis")
    assert "query" not in pool.calls[-1][2]


def test_search_adapter_reranks_by_difficulty(memory):
    """B: 给 difficulty 时, 客户端按难度距离重排。"""
    pool = FakePool({("questions", "search_questions"): [
        {"question_id": "h1", "question": "H1", "difficulty": "hard",
         "reference_answer": "AH"},
        {"question_id": "e1", "question": "E1", "difficulty": "easy",
         "reference_answer": "AE"},
        {"question_id": "m1", "question": "M1", "difficulty": "medium",
         "reference_answer": "AM"},
    ]})
    adapter = MCPSearchAdapter(pool, memory)
    res = adapter(role="后端", topic="x", difficulty="medium")
    assert res[0]["question_id"] == "m1"
    assert adapter.last_reference_answer == "AM"


def test_search_adapter_empty_returns_none_last_id(memory):
    pool = FakePool({("questions", "search_questions"): []})
    adapter = MCPSearchAdapter(pool, memory)
    assert adapter(role="x", topic="y") == []
    assert adapter.last_id is None
    assert adapter.last_reference_answer is None


def test_jd_lookup_forwards_args(memory):
    pool = FakePool({("jd", "lookup_jd"): {"company": "ACME",
                                            "role": "backend",
                                            "requirements": ["MySQL"]}})
    lookup = make_mcp_jd_lookup(pool)
    assert lookup(company="ACME", role="backend")["requirements"] == ["MySQL"]
    assert pool.calls == [("jd", "lookup_jd",
                           {"company": "ACME", "role": "backend"})]
