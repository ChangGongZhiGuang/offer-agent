"""Procedural memory: 全局规则 (来自 roles.yaml), 只读常驻, 概念上 pinned。"""
from __future__ import annotations

from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery, matches_filter

# 规则的 salience 设为极高, 确保 recall 合并排序时永远靠前 (常驻语义)。
_RULE_SALIENCE = 1000.0


class ProceduralMemory:
    def __init__(self, rules: list[dict]):
        self._rules = rules

    def add(self, item: MemoryItem) -> None:
        raise NotImplementedError("procedural memory is read-only (edit roles.yaml instead)")

    def recall(self, query: RecallQuery) -> list[MemoryItem]:
        items = [
            MemoryItem(kind=MemoryKind.PROCEDURAL, content=dict(rule), salience=_RULE_SALIENCE)
            for rule in self._rules
        ]
        return [it for it in items if matches_filter(it, query.role, query.topic)]
