"""口令哈希与用户名/密码规则的单测。"""
from __future__ import annotations

from interviewforge.auth.password import (
    hash_password, validate_password, validate_username, verify_password)


def test_hash_verify_roundtrip():
    enc = hash_password("s3cret-pass")
    assert enc.startswith("pbkdf2$")
    assert verify_password("s3cret-pass", enc)
    assert not verify_password("wrong-pass", enc)


def test_hash_is_salted_unique():
    # 同一密码两次哈希应因随机盐而不同
    assert hash_password("abc123") != hash_password("abc123")


def test_verify_rejects_malformed():
    assert not verify_password("x", "not-a-valid-encoded-hash")
    assert not verify_password("x", "")


def test_validate_username_rules():
    # 合法: 3-16 位 字母/数字/-/_
    assert validate_username("abc")
    assert validate_username("user_123")
    assert validate_username("a-b-c")
    assert validate_username("Ab3_" + "x" * 12)  # 16 位
    # 非法: 太短 / 太长 / 非法字符 / 空
    assert not validate_username("ab")
    assert not validate_username("a" * 17)
    assert not validate_username("user@name")
    assert not validate_username("用户名")
    assert not validate_username("")


def test_validate_password_min_length():
    assert validate_password("abcdef")
    assert not validate_password("12345")
    assert not validate_password("")
