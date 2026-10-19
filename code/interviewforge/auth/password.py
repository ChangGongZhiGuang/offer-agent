"""口令哈希与用户名/密码校验: 仅用标准库 hashlib, 不引入额外依赖。

- 哈希: pbkdf2_hmac(sha256) + 每用户随机盐, 编码为
  `pbkdf2$<iterations>$<salt_hex>$<hash_hex>`。
- 校验: 解析编码串重算哈希, 用 hmac.compare_digest 常数时间比较。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

_ITERATIONS = 240_000
_SALT_BYTES = 16
_HASH_BYTES = 32
_ALGO = "sha256"

# 用户名: 3-16 位, 仅字母/数字/-/_
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,16}$")


def validate_username(name: str) -> bool:
    """用户名是否符合 3-16 位数字/字母/-/_ 的规则。"""
    return isinstance(name, str) and bool(_USERNAME_RE.match(name))


def validate_password(password: str) -> bool:
    """密码最低要求: 非空且至少 6 位 (避免过度约束)。"""
    return isinstance(password, str) and len(password) >= 6


def hash_password(password: str) -> str:
    """生成带随机盐的 pbkdf2 哈希编码串。"""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt,
                             _ITERATIONS, dklen=_HASH_BYTES)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """校验明文密码是否匹配编码哈希; 格式非法一律返回 False。"""
    try:
        algo, iter_s, salt_hex, hash_hex = encoded.split("$")
        if algo != "pbkdf2":
            return False
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt,
                             iterations, dklen=len(expected))
    return hmac.compare_digest(dk, expected)
