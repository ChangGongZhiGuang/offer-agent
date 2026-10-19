"""Phase 0 共享数据类型。其余类型在各自所属阶段定义。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str

    def __post_init__(self):
        # 允许传入字符串, 归一化为 Role; 非法值抛 ValueError
        object.__setattr__(self, "role", Role(self.role))

    def to_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(role=Role(d["role"]), content=d["content"])


@dataclass(frozen=True)
class TranscriptEvent:
    """转录中的一行。type 取值: user/assistant/tool_call/tool_result/compact/transition。"""
    type: str
    payload: dict
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"type": self.type, "ts": self.ts, "payload": self.payload}

    @classmethod
    def from_dict(cls, d: dict) -> "TranscriptEvent":
        return cls(type=d["type"], ts=d["ts"], payload=d["payload"])
