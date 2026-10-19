"""用户账号存储抽象。InMemory 单测/无 MySQL + MySQL 生产。

username 唯一性由数据库 UNIQUE 键 (或内存 dict) 保证, 重复注册抛 DuplicateUserError。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4


class DuplicateUserError(Exception):
    """用户名已存在。"""


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    created_at: str = ""
    role: str = "user"          # "user" | "admin" | "root"

    def to_dict(self) -> dict:
        return {"id": self.id, "username": self.username,
                "created_at": self.created_at, "role": self.role}


class UserBank(Protocol):
    def create(self, username: str, password_hash: str, role: str = "user") -> User: ...
    def get_by_username(self, username: str) -> User | None: ...
    def get_by_id(self, user_id: str) -> User | None: ...
    def list_all(self) -> list[User]: ...
    def set_role(self, user_id: str, role: str) -> bool: ...


class InMemoryUserBank:
    """进程内用户表, 供单测与无 MySQL 环境。"""

    def __init__(self):
        self._by_name: dict[str, User] = {}
        self._by_id: dict[str, User] = {}

    def create(self, username: str, password_hash: str, role: str = "user") -> User:
        if username in self._by_name:
            raise DuplicateUserError(username)
        user = User(id=uuid4().hex, username=username,
                    password_hash=password_hash,
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    role=role)
        self._by_name[username] = user
        self._by_id[user.id] = user
        return user

    def get_by_username(self, username: str) -> User | None:
        return self._by_name.get(username)

    def get_by_id(self, user_id: str) -> User | None:
        return self._by_id.get(user_id)

    def list_all(self) -> list[User]:
        return sorted(self._by_id.values(), key=lambda u: u.created_at)

    def set_role(self, user_id: str, role: str) -> bool:
        user = self._by_id.get(user_id)
        if user is None:
            return False
        user.role = role          # _by_name 与 _by_id 指向同一对象, 改一处即可
        return True


class MySQLUserBank:
    """生产: 表 users(id, username UNIQUE, password_hash, created_at)。懒导入 PyMySQL。"""

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
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(32) PRIMARY KEY,
                    username VARCHAR(64) UNIQUE,
                    password_hash VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    role VARCHAR(16) NOT NULL DEFAULT 'user'
                ) CHARACTER SET utf8mb4
                """
            )
            # 迁移: 老表无 role 列时补上 (1060 = ER_DUP_FIELDNAME 则忽略)
            cur.execute(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'users' AND column_name = 'role'
                """
            )
            if (cur.fetchone() or [0])[0] == 0:
                cur.execute(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'user'")

    def create(self, username: str, password_hash: str, role: str = "user") -> User:
        uid = uuid4().hex
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (id, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (uid, username, password_hash, role),
                )
        except self._pymysql.err.IntegrityError as exc:
            # 1062 = ER_DUP_ENTRY
            if getattr(exc, "args", (None,))[0] == 1062:
                raise DuplicateUserError(username) from exc
            raise
        return self.get_by_id(uid) or User(id=uid, username=username,
                                           password_hash=password_hash, role=role)

    def get_by_username(self, username: str) -> User | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at, role FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
        return self._row_to_user(row)

    def get_by_id(self, user_id: str) -> User | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at, role FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return self._row_to_user(row)

    def list_all(self) -> list[User]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at, role FROM users ORDER BY created_at")
            rows = cur.fetchall()
        return [self._row_to_user(r) for r in rows if r is not None]

    def set_role(self, user_id: str, role: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
            return cur.rowcount > 0

    @staticmethod
    def _row_to_user(row) -> User | None:
        if row is None:
            return None
        created = row[3]
        return User(id=row[0], username=row[1], password_hash=row[2],
                    created_at=created.isoformat(sep=" ", timespec="seconds")
                    if hasattr(created, "isoformat") else str(created or ""),
                    role=row[4] if len(row) > 4 and row[4] else "user")
