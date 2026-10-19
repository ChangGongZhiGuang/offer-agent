"""面试历史记录存储抽象。仅记录"登录状态下发起的面试"。

InMemory 单测/无 MySQL + MySQL 生产。每条记录挂一个 session, 存摘要字段
+ 完整报告 JSON, 供用户回看历史列表与单场报告。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class HistoryEntry:
    session_id: str
    user_id: str
    role: str
    topic: str
    overall_score: float
    avg_score: float
    answered: int
    report: dict
    created_at: str = ""

    def summary(self) -> dict:
        """列表展示用的摘要 (不含完整 report)。"""
        return {
            "session_id": self.session_id,
            "role": self.role,
            "topic": self.topic,
            "overall_score": self.overall_score,
            "avg_score": self.avg_score,
            "answered": self.answered,
            "created_at": self.created_at,
        }


class HistoryBank(Protocol):
    def add(self, entry: HistoryEntry) -> None: ...
    def list_by_user(self, user_id: str) -> list[HistoryEntry]: ...
    def get_by_session(self, user_id: str, session_id: str) -> HistoryEntry | None: ...
    def delete(self, user_id: str, session_id: str) -> bool: ...


class InMemoryHistoryBank:
    def __init__(self):
        self._items: dict[str, HistoryEntry] = {}

    def add(self, entry: HistoryEntry) -> None:
        if not entry.created_at:
            entry.created_at = datetime.now().isoformat(timespec="seconds")
        self._items[entry.session_id] = entry

    def list_by_user(self, user_id: str) -> list[HistoryEntry]:
        items = [e for e in self._items.values() if e.user_id == user_id]
        # 时间倒序 (最新在前)
        items.sort(key=lambda e: e.created_at, reverse=True)
        return items

    def get_by_session(self, user_id: str, session_id: str) -> HistoryEntry | None:
        e = self._items.get(session_id)
        return e if e is not None and e.user_id == user_id else None

    def delete(self, user_id: str, session_id: str) -> bool:
        e = self._items.get(session_id)
        if e is not None and e.user_id == user_id:
            del self._items[session_id]
            return True
        return False


class MySQLHistoryBank:
    """生产: 表 interview_history(session_id PK, user_id, ..., report_json)。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str):
        import pymysql
        self._pymysql = pymysql
        self._conn_kwargs = dict(host=host, port=port, user=user, password=password,
                                 database=database, charset="utf8mb4", autocommit=True)

    def _connect(self):
        return self._pymysql.connect(**self._conn_kwargs)

    def ensure_schema(self) -> None:
        # 库已由 MySQLUserBank.ensure_schema 建过; 这里幂等再保一次
        kwargs = {k: v for k, v in self._conn_kwargs.items() if k != "database"}
        db = self._conn_kwargs["database"]
        with self._pymysql.connect(**kwargs) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_history (
                    session_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(32),
                    role VARCHAR(64),
                    topic VARCHAR(128),
                    overall_score FLOAT,
                    avg_score FLOAT,
                    answered INT,
                    report_json LONGTEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id, created_at)
                ) CHARACTER SET utf8mb4
                """
            )

    def add(self, entry: HistoryEntry) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interview_history
                    (session_id, user_id, role, topic, overall_score, avg_score,
                     answered, report_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    overall_score=VALUES(overall_score), avg_score=VALUES(avg_score),
                    answered=VALUES(answered), report_json=VALUES(report_json)
                """,
                (entry.session_id, entry.user_id, entry.role, entry.topic,
                 entry.overall_score, entry.avg_score, entry.answered,
                 json.dumps(entry.report, ensure_ascii=False)),
            )

    def list_by_user(self, user_id: str) -> list[HistoryEntry]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, user_id, role, topic, overall_score, avg_score,
                       answered, created_at
                FROM interview_history WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        out: list[HistoryEntry] = []
        for r in rows:
            out.append(HistoryEntry(
                session_id=r[0], user_id=r[1], role=r[2], topic=r[3],
                overall_score=float(r[4] or 0), avg_score=float(r[5] or 0),
                answered=int(r[6] or 0), report={},
                created_at=self._fmt_created(r[7])))
        return out

    def get_by_session(self, user_id: str, session_id: str) -> HistoryEntry | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, user_id, role, topic, overall_score, avg_score,
                       answered, report_json, created_at
                FROM interview_history WHERE session_id = %s AND user_id = %s
                """,
                (session_id, user_id),
            )
            r = cur.fetchone()
        if r is None:
            return None
        report = {}
        if r[7]:
            try:
                report = json.loads(r[7])
            except (ValueError, TypeError):
                report = {}
        return HistoryEntry(
            session_id=r[0], user_id=r[1], role=r[2], topic=r[3],
            overall_score=float(r[4] or 0), avg_score=float(r[5] or 0),
            answered=int(r[6] or 0), report=report,
            created_at=self._fmt_created(r[8]))

    @staticmethod
    def _fmt_created(created) -> str:
        if hasattr(created, "isoformat"):
            return created.isoformat(sep=" ", timespec="seconds")
        return str(created or "")

    def delete(self, user_id: str, session_id: str) -> bool:
        # 仅删属于本人的记录 (WHERE 同时限定 user_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM interview_history WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
            return cur.rowcount > 0
