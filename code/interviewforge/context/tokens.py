"""确定性 token 估算 (启发式)。真实分词器可后续在此替换。"""
from __future__ import annotations

import re
from typing import Iterable

from interviewforge.types import Message

_CJK = re.compile(r"[一-鿿]")


def estimate_tokens(text: str) -> int:
    """CJK 字符按 1 token, 其余按 ~4 字符/token (向上取整)。"""
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    rest = _CJK.sub("", text)
    rest_tokens = (len(rest) + 3) // 4  # ceil(len/4)
    return cjk + rest_tokens


def estimate_messages_tokens(messages: Iterable[Message]) -> int:
    return sum(estimate_tokens(m.content) for m in messages)
