"""RAG 数据类型: Question + 难度分级。"""
from __future__ import annotations

from dataclasses import dataclass

_DIFFICULTY_RANK = {"easy": 1, "medium": 2, "hard": 3}


@dataclass
class Question:
    id: str
    role: str
    topic: str
    stem: str
    answer: str
    difficulty: str = "medium"
    fu: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "topic": self.topic,
            "stem": self.stem, "answer": self.answer,
            "difficulty": self.difficulty, "fu": self.fu,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(
            id=d["id"], role=d["role"], topic=d["topic"],
            stem=d["stem"], answer=d["answer"],
            difficulty=d.get("difficulty", "medium"),
            fu=d.get("fu", ""),
        )


def difficulty_rank(difficulty: str) -> int:
    """easy<medium<hard; 未知按 medium。"""
    return _DIFFICULTY_RANK.get(difficulty, _DIFFICULTY_RANK["medium"])
