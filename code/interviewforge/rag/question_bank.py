"""题库 (关系库) 抽象。InMemory 单测 + MySQL 生产。get_by_ids 保持入参顺序。"""
from __future__ import annotations

from typing import Protocol

from interviewforge.rag.types import Question


class QuestionBank(Protocol):
    def add(self, question: Question) -> None: ...
    def get_by_ids(self, ids: list[str]) -> list[Question]: ...
    def list_all(self, role: str | None = None) -> list[Question]: ...
    def delete(self, id: str) -> None: ...


class InMemoryQuestionBank:
    def __init__(self):
        self._q: dict[str, Question] = {}

    def add(self, question: Question) -> None:
        self._q[question.id] = question

    def get_by_ids(self, ids: list[str]) -> list[Question]:
        return [self._q[i] for i in ids if i in self._q]

    def list_all(self, role: str | None = None) -> list[Question]:
        qs = list(self._q.values())
        if role is not None:
            qs = [q for q in qs if q.role == role]
        return qs

    def delete(self, id: str) -> None:
        self._q.pop(id, None)


class MySQLQuestionBank:
    """生产: 表 questions(id,role,topic,stem,answer,difficulty,fu)。懒导入 PyMySQL。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str):
        import pymysql
        self._pymysql = pymysql
        self._conn_kwargs = dict(host=host, port=port, user=user, password=password,
                                 database=database, charset="utf8mb4", autocommit=True)

    def _connect(self):
        return self._pymysql.connect(**self._conn_kwargs)

    def _ensure_database(self) -> None:
        kwargs = {k: v for k, v in self._conn_kwargs.items() if k != "database"}
        db = self._conn_kwargs["database"]
        with self._pymysql.connect(**kwargs) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

    def ensure_schema(self) -> None:
        self._ensure_database()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS questions (
                    id VARCHAR(64) PRIMARY KEY,
                    role VARCHAR(64),
                    topic VARCHAR(128),
                    stem TEXT,
                    answer TEXT,
                    difficulty VARCHAR(16),
                    fu TEXT
                ) CHARACTER SET utf8mb4
                """
            )
            # 若旧表存在但无 fu 列，则补列
            cur.execute("SHOW COLUMNS FROM questions LIKE 'fu'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN fu TEXT")

    def clear(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM questions")

    def add(self, question: Question) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO questions (id, role, topic, stem, answer, difficulty, fu)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    role=VALUES(role), topic=VALUES(topic), stem=VALUES(stem),
                    answer=VALUES(answer), difficulty=VALUES(difficulty), fu=VALUES(fu)
                """,
                (question.id, question.role, question.topic,
                 question.stem, question.answer, question.difficulty, question.fu),
            )

    def get_by_ids(self, ids: list[str]) -> list[Question]:
        if not ids:
            return []
        placeholders = ", ".join(["%s"] * len(ids))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id, role, topic, stem, answer, difficulty, fu "
                f"FROM questions WHERE id IN ({placeholders})",
                ids,
            )
            rows = cur.fetchall()
        by_id = {
            row[0]: Question(id=row[0], role=row[1], topic=row[2],
                             stem=row[3], answer=row[4], difficulty=row[5],
                             fu=row[6] or "")
            for row in rows
        }
        return [by_id[i] for i in ids if i in by_id]

    def list_all(self, role: str | None = None) -> list[Question]:
        sql = "SELECT id, role, topic, stem, answer, difficulty, fu FROM questions"
        params: tuple = ()
        if role is not None:
            sql += " WHERE role = %s"
            params = (role,)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [Question(id=r[0], role=r[1], topic=r[2], stem=r[3],
                         answer=r[4], difficulty=r[5], fu=r[6] or "")
                for r in rows]

    def delete(self, id: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE id = %s", (id,))
