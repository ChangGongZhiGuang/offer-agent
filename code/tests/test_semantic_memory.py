import os

import pytest

from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery


def _profile(fact, role="后端", salience=1.0, item_id=None):
    kwargs = {} if item_id is None else {"id": item_id}
    return MemoryItem(kind=MemoryKind.SEMANTIC,
                      content={"role": role, "fact": fact},
                      salience=salience, **kwargs)


def test_inmemory_upsert_and_query():
    sm = SemanticMemory(InMemorySemanticBackend())
    sm.add(_profile("擅长SQL", item_id="p1"))
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC], role="后端", limit=5)
    facts = [it.content["fact"] for it in sm.recall(q)]
    assert facts == ["擅长SQL"]


def test_inmemory_upsert_overwrites_same_id():
    sm = SemanticMemory(InMemorySemanticBackend())
    sm.add(_profile("弱系统设计", item_id="p1", salience=0.5))
    sm.add(_profile("精通系统设计", item_id="p1", salience=0.9))
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC], role="后端")
    facts = [it.content["fact"] for it in sm.recall(q)]
    assert facts == ["精通系统设计"]


def test_inmemory_query_filters_by_role():
    sm = SemanticMemory(InMemorySemanticBackend())
    sm.add(_profile("a", role="后端", item_id="1"))
    sm.add(_profile("b", role="前端", item_id="2"))
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC], role="前端")
    assert [it.content["fact"] for it in sm.recall(q)] == ["b"]


def _mysql_available():
    if not os.getenv("MYSQL_DATABASE"):
        return False
    try:
        import pymysql
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE"),
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _mysql_available(), reason="no reachable MySQL configured")
def test_mysql_backend_roundtrip():
    from interviewforge.memory.semantic import MySQLSemanticBackend
    backend = MySQLSemanticBackend(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE"),
    )
    backend.ensure_schema()
    backend.clear()
    sm = SemanticMemory(backend)
    sm.add(_profile("擅长Redis", item_id="mysql-p1"))
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC], role="后端")
    facts = [it.content["fact"] for it in sm.recall(q)]
    assert "擅长Redis" in facts
