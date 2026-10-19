"""登录凭证 TokenStore 的单测。"""
from __future__ import annotations

from interviewforge.auth.tokens import TokenStore


def test_issue_resolve():
    store = TokenStore()
    token = store.issue("u-1")
    assert store.resolve(token) == "u-1"


def test_resolve_missing_or_empty():
    store = TokenStore()
    assert store.resolve(None) is None
    assert store.resolve("") is None
    assert store.resolve("unknown") is None


def test_multiple_tokens_same_user():
    store = TokenStore()
    t1 = store.issue("u-1")
    t2 = store.issue("u-1")
    assert t1 != t2
    assert store.resolve(t1) == "u-1" == store.resolve(t2)


def test_revoke():
    store = TokenStore()
    token = store.issue("u-9")
    store.revoke(token)
    assert store.resolve(token) is None
