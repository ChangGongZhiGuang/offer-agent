"""用户"我的简历"正文存储 (InMemory) 的单测。"""
from __future__ import annotations

import pytest

from interviewforge.auth.resume_store import (
    MAX_RESUME_CHARS, InMemoryResumeStore, StoredResume)


def test_put_then_get():
    store = InMemoryResumeStore()
    sr = store.put("u1", "3 年 Java 后端, 秒杀系统", filename="a.pdf")
    assert isinstance(sr, StoredResume)
    got = store.get("u1")
    assert got is not None
    assert got.text == "3 年 Java 后端, 秒杀系统"
    assert got.filename == "a.pdf"
    assert got.updated_at  # 自动补时间戳


def test_get_missing_returns_none():
    store = InMemoryResumeStore()
    assert store.get("ghost") is None


def test_put_overwrites_previous():
    store = InMemoryResumeStore()
    store.put("u1", "旧版简历", filename="old.pdf")
    store.put("u1", "新版简历", filename="new.docx")
    got = store.get("u1")
    assert got.text == "新版简历"
    assert got.filename == "new.docx"
    # 每人仅一份: 覆盖后不残留旧内容
    assert len(store._items) == 1


def test_size_defaults_to_utf8_byte_length():
    store = InMemoryResumeStore()
    sr = store.put("u1", "你好世界")   # 4 个汉字 * 3 字节 = 12
    assert sr.size == len("你好世界".encode("utf-8"))


def test_delete_removes_and_flags():
    store = InMemoryResumeStore()
    store.put("u1", "内容")
    assert store.delete("u1") is True
    assert store.get("u1") is None
    assert store.delete("u1") is False   # 再删返回 False


def test_empty_text_rejected():
    store = InMemoryResumeStore()
    with pytest.raises(ValueError):
        store.put("u1", "   ")


def test_overlong_text_rejected():
    store = InMemoryResumeStore()
    with pytest.raises(ValueError):
        store.put("u1", "x" * (MAX_RESUME_CHARS + 1))


def test_summary_excludes_text():
    sr = StoredResume(user_id="u1", text="正文很长", filename="f.pdf",
                      size=12, updated_at="2026-01-01 10:00:00")
    s = sr.summary()
    assert "text" not in s
    assert s["filename"] == "f.pdf" and s["size"] == 12
    # to_dict 含正文
    assert sr.to_dict()["text"] == "正文很长"


def test_protocol_surface():
    store = InMemoryResumeStore()
    for name in ("get", "put", "delete"):
        assert hasattr(store, name)
