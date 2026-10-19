"""Semantic memory: 候选人画像。backend 抽象, 默认 MySQL (单测用 InMemory)。"""
from __future__ import annotations

import json
from typing import Protocol

from interviewforge.memory.types import MemoryItem, RecallQuery, matches_filter


class SemanticBackend(Protocol):
    def upsert(self, item: MemoryItem) -> None: ...
    def query(self, role: str | None, topic: str | None, limit: int) -> list[MemoryItem]: ...


class InMemorySemanticBackend:
    """供单测的离线实现。按 id 存储, 同 id 覆盖。"""

    def __init__(self):
        self._items: dict[str, MemoryItem] = {}

    def upsert(self, item: MemoryItem) -> None:
        self._items[item.id] = item

    def query(self, role: str | None, topic: str | None, limit: int) -> list[MemoryItem]:
        matched = [it for it in self._items.values() if matches_filter(it, role, topic)]
        matched.sort(key=lambda it: it.salience, reverse=True)
        return matched[:limit]


class MySQLSemanticBackend:
    """生产实现。表 memory_semantic(id, role, topic, content JSON, salience, created_at)。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str):
        import pymysql
        self._pymysql = pymysql
        self._conn_kwargs = dict(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4", autocommit=True,
        )

    def _connect(self):
        return self._pymysql.connect(**self._conn_kwargs)

    def ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_semantic (
                    id VARCHAR(64) PRIMARY KEY,
                    role VARCHAR(64),
                    topic VARCHAR(128),
                    content JSON,
                    salience DOUBLE,
                    created_at DOUBLE
                ) CHARACTER SET utf8mb4
                """
            )

    def clear(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM memory_semantic")

    def upsert(self, item: MemoryItem) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_semantic (id, role, topic, content, salience, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    role=VALUES(role), topic=VALUES(topic), content=VALUES(content),
                    salience=VALUES(salience), created_at=VALUES(created_at)
                """,
                (
                    item.id,
                    item.content.get("role"),
                    item.content.get("topic"),
                    json.dumps(item.content, ensure_ascii=False),
                    item.salience,
                    item.created_at,
                ),
            )

    def query(self, role: str | None, topic: str | None, limit: int) -> list[MemoryItem]:
        clauses, params = [], []
        if role is not None:
            clauses.append("role = %s")
            params.append(role)
        if topic is not None:
            clauses.append("topic = %s")
            params.append(topic)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id, content, salience, created_at FROM memory_semantic "
                f"{where} ORDER BY salience DESC LIMIT %s",
                params,
            )
            rows = cur.fetchall()
        items = []
        for row_id, content, salience, created_at in rows:
            data = content if isinstance(content, dict) else json.loads(content)
            items.append(MemoryItem(kind="semantic", content=data,
                                    salience=salience, id=row_id, created_at=created_at))
        return items


class SemanticMemory:
    def __init__(self, backend: SemanticBackend):
        self._backend = backend

    def add(self, item: MemoryItem) -> None:
        self._backend.upsert(item)

    def recall(self, query: RecallQuery) -> list[MemoryItem]:
        return self._backend.query(query.role, query.topic, query.limit)
