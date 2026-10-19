"""把 MCPClientPool 包装成 ToolRegistry 可用的 retriever / jd_lookup 回调。

设计要点:
- MCPSearchAdapter 与 loop.adapter.SearchAdapter 行为对齐: 返回 [{question_id,question,difficulty}]
  且暴露 last_id 供 InterviewLoop 关联评分; 按本场已问 id 做客户端去重。
- mcp_jd_lookup 是无状态函数闭包, 直接转发 (company, role)。
"""
from __future__ import annotations

from typing import Callable

from interviewforge.loop.adapter import collect_asked_ids
from interviewforge.mcp.client import MCPClientPool
from interviewforge.memory.base import MemoryService
from interviewforge.rag.types import difficulty_rank


class MCPSearchAdapter:
    """search_questions 的 MCP 版本: 调 questions server, 客户端做去重并取首项。"""

    SERVER = "questions"
    TOOL = "search_questions"

    def __init__(self, pool: MCPClientPool, memory: MemoryService):
        self.pool = pool
        self.memory = memory
        self.last_id: str | None = None
        self.last_question: str | None = None
        self.last_reference_answer: str | None = None  # D: 参考答案回流
        self._next_query: str | None = None             # A: 同 SearchAdapter 一致 API

    def set_next_query(self, query: str | None) -> None:
        """A: 与 SearchAdapter 对齐; 当前 server 端 (questions_server) 关键词过滤忽略
        query 字段, 但接口保留以便后续 server 端接真实 RAG 时无缝启用。"""
        self._next_query = query or None

    def __call__(self, role: str, topic: str,
                 difficulty: str | None = None) -> list[dict]:
        args: dict = {"role": role, "topic": topic}
        if self._next_query:
            args["query"] = self._next_query
        self._next_query = None  # one-shot
        items = self.pool.call(self.SERVER, self.TOOL, args) or []
        asked = set(collect_asked_ids(self.memory))
        # 客户端去重
        items = [it for it in items if it.get("question_id") not in asked]
        # B: 客户端按 |rank(item.difficulty) - target| 稳定重排
        if difficulty is not None and items:
            target = difficulty_rank(difficulty)
            items.sort(key=lambda it: abs(
                difficulty_rank(it.get("difficulty", "medium")) - target))
        if not items:
            self.last_id = None
            self.last_question = None
            self.last_reference_answer = None
            return []
        picked = items[0]
        self.last_id = picked.get("question_id")
        self.last_question = picked.get("question")
        self.last_reference_answer = picked.get("reference_answer")
        # 不把 reference_answer 暴露给主上下文 (Examiner 不需要), 由 adapter 持有
        return [{k: v for k, v in picked.items() if k != "reference_answer"}]


def make_mcp_jd_lookup(pool: MCPClientPool) -> Callable[..., dict]:
    """返回 jd_lookup(company, role) -> dict, 转发到 jd server。"""

    def _lookup(company: str, role: str) -> dict:
        return pool.call("jd", "lookup_jd", {"company": company, "role": role})

    return _lookup
