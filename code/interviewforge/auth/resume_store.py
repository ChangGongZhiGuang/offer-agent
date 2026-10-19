"""用户"我的简历"正文存储抽象。仅登录用户可维护, 每人一份, 新保存覆盖旧版。

只持久化简历正文 (raw text), 不持久化结构化画像 —— 画像是岗位相关的过期产物,
每次开始面试前按当前 JD 现调大模型生成。InMemory 单测/无 MySQL + MySQL 生产。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# 正文长度上限 (字符): 超出视为异常输入, 端点转 400
MAX_RESUME_CHARS = 200_000


@dataclass
class StoredResume:
    user_id: str
    text: str
    filename: str = ""
    size: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict:
        """含正文的完整表示 (供前端回填)。"""
        return {
            "filename": self.filename,
            "size": self.size,
            "updated_at": self.updated_at,
            "text": self.text,
        }

    def summary(self) -> dict:
        """不含正文的摘要 (供头部展示, 避免无谓传输)。"""
        return {
            "filename": self.filename,
            "size": self.size,
            "updated_at": self.updated_at,
        }


class ResumeStore(Protocol):
    def get(self, user_id: str) -> StoredResume | None: ...
    def put(self, user_id: str, text: str, filename: str = "",
            size: int = 0) -> StoredResume: ...
    def delete(self, user_id: str) -> bool: ...


def _validate_text(text: str) -> str:
    if text is None or not text.strip():
        raise ValueError("简历正文不能为空")
    if len(text) > MAX_RESUME_CHARS:
        raise ValueError(f"简历正文过长 (超过 {MAX_RESUME_CHARS} 字符)")
    return text


class InMemoryResumeStore:
    def __init__(self):
        self._items: dict[str, StoredResume] = {}

    def get(self, user_id: str) -> StoredResume | None:
        return self._items.get(user_id)

    def put(self, user_id: str, text: str, filename: str = "",
            size: int = 0) -> StoredResume:
        text = _validate_text(text)
        sr = StoredResume(
            user_id=user_id, text=text, filename=filename,
            size=size if size else len(text.encode("utf-8")),
            updated_at=datetime.now().isoformat(timespec="seconds"))
        self._items[user_id] = sr   # 直接覆盖旧版
        return sr

    def delete(self, user_id: str) -> bool:
        if user_id in self._items:
            del self._items[user_id]
            return True
        return False


class MySQLResumeStore:
    """生产: 表 user_resumes(user_id PK, resume_text LONGTEXT, filename, size, updated_at)。"""

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
                CREATE TABLE IF NOT EXISTS user_resumes (
                    user_id VARCHAR(32) PRIMARY KEY,
                    resume_text LONGTEXT,
                    filename VARCHAR(255),
                    size INT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4
                """
            )

    def get(self, user_id: str) -> StoredResume | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, resume_text, filename, size, updated_at
                FROM user_resumes WHERE user_id = %s
                """,
                (user_id,),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return StoredResume(
            user_id=r[0], text=r[1] or "", filename=r[2] or "",
            size=int(r[3] or 0), updated_at=self._fmt_updated(r[4]))

    def put(self, user_id: str, text: str, filename: str = "",
            size: int = 0) -> StoredResume:
        text = _validate_text(text)
        size = size if size else len(text.encode("utf-8"))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_resumes (user_id, resume_text, filename, size)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    resume_text=VALUES(resume_text), filename=VALUES(filename),
                    size=VALUES(size), updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, text, filename, size),
            )
        stored = self.get(user_id)
        return stored if stored is not None else StoredResume(
            user_id=user_id, text=text, filename=filename, size=size,
            updated_at=datetime.now().isoformat(timespec="seconds"))

    def delete(self, user_id: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM user_resumes WHERE user_id = %s", (user_id,))
            return cur.rowcount > 0

    @staticmethod
    def _fmt_updated(updated) -> str:
        if hasattr(updated, "isoformat"):
            return updated.isoformat(sep=" ", timespec="seconds")
        return str(updated or "")
