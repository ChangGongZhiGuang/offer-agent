"""Episodic memory: 事件记忆, JSONL 持久化 (append-only 写, prune 时重写)。"""
from __future__ import annotations

import json
from pathlib import Path

from interviewforge.memory.types import (
    MemoryItem,
    RecallQuery,
    effective_salience,
    matches_filter,
)


class EpisodicMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items: list[MemoryItem] = self._load()

    def _load(self) -> list[MemoryItem]:
        if not self.path.exists():
            return []
        items: list[MemoryItem] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(MemoryItem.from_dict(json.loads(line)))
        return items

    def _rewrite(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for it in self._items:
                f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")

    def add(self, item: MemoryItem) -> None:
        self._items.append(item)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> list[MemoryItem]:
        return list(self._items)

    def recall(self, query: RecallQuery, now: float) -> list[MemoryItem]:
        matched = [it for it in self._items if matches_filter(it, query.role, query.topic)]
        matched.sort(key=lambda it: effective_salience(it, now), reverse=True)
        return matched[: query.limit]

    def prune(self, salience_floor: float, now: float) -> None:
        """删除有效 salience 低于阈值的项, 并重写文件。蒸馏即遗忘。"""
        self._items = [
            it for it in self._items if effective_salience(it, now) >= salience_floor
        ]
        self._rewrite()
