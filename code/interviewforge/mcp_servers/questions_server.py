"""MCP server: 题库检索 (RAG)。stdio 传输。

启动期构建 Retriever:
  - 默认: 读 MySQL 题库 + 真实 embedder 建向量索引 (生产)。
  - INTERVIEWFORGE_MCP_FAKE_EMBED=1: 用 SEED_QUESTIONS + 关键词 embedder (离线测试, 无需 MySQL/网络)。

search_questions 用 role+topic 做元数据硬过滤, 再用语义 query 在候选内重排
(不再忽略 query, 也不会在 topic 无命中时返回跨主题噪声题)。
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("interviewforge.mcp.questions")

from interviewforge.rag.index_builder import build_index_from_bank
from interviewforge.rag.question_bank import InMemoryQuestionBank, MySQLQuestionBank
from interviewforge.rag.seed import SEED_QUESTIONS, seed_questions
from interviewforge.rag.vector_store import InMemoryVectorStore

mcp = FastMCP("interviewforge-questions")

_FAKE_VOCAB = ["redis", "mysql", "并发", "分布式", "锁", "索引", "缓存", "动态规划", "vue"]


def _build_retriever():
    load_dotenv()  # 子进程自读 code/.env (MYSQL_*/OPENAI_*)
    if os.getenv("INTERVIEWFORGE_MCP_FAKE_EMBED") == "1":
        from interviewforge.loop.driver import make_keyword_embedder
        from interviewforge.rag.retriever import Retriever
        embed = make_keyword_embedder(_FAKE_VOCAB)
        vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
        seed_questions(qb, vs, embed, SEED_QUESTIONS)
        return Retriever(vs, qb, embed)
    from interviewforge.config.settings import load_settings
    from interviewforge.model_client import ModelClient
    from interviewforge.api.factory import (build_vector_store, is_chroma_mode,
                                             _safe_ensure_index)
    settings = load_settings()
    qb = MySQLQuestionBank(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "interviewforge"),
    )
    qb.ensure_schema()
    logger.info("连接 MySQL 题库成功, 开始构建向量索引 …")
    embed = ModelClient.from_settings(settings).embed
    if is_chroma_mode():
        # 持久库: 按 id+题干hash 增量补齐, 避免每次启动重 embed 全量题
        store = build_vector_store()
        _safe_ensure_index(qb, embed, store)
        from interviewforge.rag.retriever import Retriever
        return Retriever(store, qb, embed)
    # 非持久: 全量灌内存索引 (旧行为)
    return build_index_from_bank(qb, embed)


_RETRIEVER = _build_retriever()
logger.info("questions_server 就绪, retriever=%s",
            "fake" if os.getenv("INTERVIEWFORGE_MCP_FAKE_EMBED") == "1" else "mysql")


@mcp.tool()
def search_questions(role: str, topic: str, query: str = "") -> list[dict]:
    """按岗位/主题硬过滤 + 语义 query 重排, 返回 [{question_id, question, difficulty, reference_answer}]。"""
    query_text = query or f"{role} {topic}"
    where = {k: v for k, v in (("role", role), ("topic", topic)) if v}
    hits = _RETRIEVER.retrieve_many(query_text, top_k=5, where=where or None)
    logger.info("search_questions role=%s topic=%s -> %d 条命中", role, topic, len(hits))
    return [{"question_id": q.id, "question": q.stem,
             "difficulty": q.difficulty, "reference_answer": q.answer}
            for q in hits]


if __name__ == "__main__":
    mcp.run()
