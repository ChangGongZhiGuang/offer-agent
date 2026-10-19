"""端到端: 起 questions MCP server 子进程 (fake-embed 离线模式), 验证走 RAG 路径。"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("mcp")

from interviewforge.mcp.client import MCPClientPool, ServerSpec


@pytest.fixture()
def pool():
    spec = ServerSpec(name="questions",
                      module="interviewforge.mcp_servers.questions_server",
                      env={**os.environ, "INTERVIEWFORGE_MCP_FAKE_EMBED": "1"})
    p = MCPClientPool([spec])
    p.start()
    yield p
    p.stop()


def test_list_tools_exposes_search_questions(pool):
    assert "search_questions" in pool.list_tools("questions")


def test_search_questions_returns_hit_with_reference(pool):
    res = pool.call("questions", "search_questions",
                    {"role": "后端", "topic": "redis", "query": "分布式锁"})
    assert isinstance(res, list) and res
    item = res[0]
    assert {"question_id", "question", "difficulty", "reference_answer"} <= set(item)
    assert item["reference_answer"]


def test_search_questions_empty_on_miss(pool):
    res = pool.call("questions", "search_questions",
                    {"role": "后端", "topic": "rust-async", "query": "rust"})
    assert res == []
