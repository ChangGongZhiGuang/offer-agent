"""面试历史记录 (InMemory) 的单测。"""
from __future__ import annotations

from interviewforge.auth.history import HistoryEntry, InMemoryHistoryBank


def _entry(sid, uid, role="后端", topic="redis", overall=4.0, avg=3.5, answered=2):
    return HistoryEntry(session_id=sid, user_id=uid, role=role, topic=topic,
                        overall_score=overall, avg_score=avg, answered=answered,
                        report={"answered": answered, "avg_score": avg,
                                "overall_score": overall, "summary": "s"})


def test_add_and_list_newest_first():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    bank._items["s1"].created_at = "2026-01-01T10:00:00"
    bank.add(_entry("s2", "u1"))
    bank._items["s2"].created_at = "2026-01-02T10:00:00"
    items = bank.list_by_user("u1")
    assert [e.session_id for e in items] == ["s2", "s1"]  # 倒序


def test_list_isolated_per_user():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    bank.add(_entry("s2", "u2"))
    assert [e.session_id for e in bank.list_by_user("u1")] == ["s1"]
    assert [e.session_id for e in bank.list_by_user("u2")] == ["s2"]


def test_get_by_session_returns_full_report():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    e = bank.get_by_session("u1", "s1")
    assert e is not None
    assert e.report["summary"] == "s"


def test_get_by_session_other_user_is_none():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    # u2 试图读 u1 的 session: 隔离, 返回 None
    assert bank.get_by_session("u2", "s1") is None


def test_summary_excludes_report():
    e = _entry("s1", "u1")
    s = e.summary()
    assert "report" not in s
    assert s["session_id"] == "s1" and s["role"] == "后端"


def test_protocol_surface():
    # InMemory 实现满足 HistoryBank 协议方法
    bank = InMemoryHistoryBank()
    for name in ("add", "list_by_user", "get_by_session", "delete"):
        assert hasattr(bank, name)


def test_delete_removes_own_entry():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    assert bank.delete("u1", "s1") is True
    assert bank.get_by_session("u1", "s1") is None
    assert bank.list_by_user("u1") == []


def test_delete_respects_user_isolation():
    bank = InMemoryHistoryBank()
    bank.add(_entry("s1", "u1"))
    # u2 删不到 u1 的记录, 返回 False 且原记录仍在
    assert bank.delete("u2", "s1") is False
    assert bank.get_by_session("u1", "s1") is not None


def test_delete_missing_returns_false():
    bank = InMemoryHistoryBank()
    assert bank.delete("u1", "ghost") is False
