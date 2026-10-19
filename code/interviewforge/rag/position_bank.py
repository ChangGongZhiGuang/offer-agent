"""岗位分类模型及题库抽象。InMemory 单测 + MySQL 生产。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Position:
    id: str
    name: str
    color: str = "#4F46E5"

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(id=d["id"], name=d["name"], color=d.get("color", "#4F46E5"))


class PositionBank(Protocol):
    def add(self, position: Position) -> None: ...
    def list_all(self) -> list[Position]: ...
    def delete(self, id: str) -> None: ...


class InMemoryPositionBank:
    def __init__(self):
        self._p: dict[str, Position] = {}

    def add(self, position: Position) -> None:
        self._p[position.id] = position

    def list_all(self) -> list[Position]:
        return list(self._p.values())

    def delete(self, id: str) -> None:
        self._p.pop(id, None)


class MySQLPositionBank:
    """生产: 表 positions(id, name, color)。懒导入 PyMySQL。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str):
        import pymysql
        self._pymysql = pymysql
        self._conn_kwargs = dict(host=host, port=port, user=user, password=password,
                                 database=database, charset="utf8mb4", autocommit=True)

    def _connect(self):
        return self._pymysql.connect(**self._conn_kwargs)

    def ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id VARCHAR(32) PRIMARY KEY,
                    name VARCHAR(64),
                    color VARCHAR(16)
                ) CHARACTER SET utf8mb4
                """
            )

    def add(self, position: Position) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO positions (id, name, color) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name), color=VALUES(color)
                """,
                (position.id, position.name, position.color),
            )

    def list_all(self) -> list[Position]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, color FROM positions")
            rows = cur.fetchall()
        return [Position(id=r[0], name=r[1], color=r[2]) for r in rows]

    def delete(self, id: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM positions WHERE id = %s", (id,))
