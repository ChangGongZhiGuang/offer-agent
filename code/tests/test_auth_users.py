"""用户账号存储 (InMemory) 的单测。"""
from __future__ import annotations

import pytest

from interviewforge.auth.users import (
    DuplicateUserError, InMemoryUserBank)


def test_create_and_get():
    bank = InMemoryUserBank()
    user = bank.create("alice", "pbkdf2$1$aa$bb")
    assert user.id and user.username == "alice"
    assert bank.get_by_username("alice") is user
    assert bank.get_by_id(user.id) is user


def test_duplicate_username_raises():
    bank = InMemoryUserBank()
    bank.create("bob", "h1")
    with pytest.raises(DuplicateUserError):
        bank.create("bob", "h2")


def test_get_missing_returns_none():
    bank = InMemoryUserBank()
    assert bank.get_by_username("ghost") is None
    assert bank.get_by_id("nope") is None


def test_default_role_is_user():
    bank = InMemoryUserBank()
    user = bank.create("carol", "h")
    assert user.role == "user"
    assert user.to_dict()["role"] == "user"


def test_create_with_role():
    bank = InMemoryUserBank()
    admin = bank.create("root", "h", role="root")
    assert admin.role == "root"
    assert bank.get_by_username("root").role == "root"


def test_set_role_and_list_all():
    bank = InMemoryUserBank()
    u = bank.create("dave", "h")
    assert bank.set_role(u.id, "admin") is True
    assert u.role == "admin"
    assert bank.get_by_id(u.id).role == "admin"   # 同一对象
    assert bank.set_role("missing", "admin") is False
    names = {x.username for x in bank.list_all()}
    assert names == {"dave"}
