import pytest

from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery


RULES = [
    {"id": "score_in_range", "desc": "评分必须落在 1-5"},
    {"id": "no_duplicate_question", "desc": "不得重复出题"},
]


def test_recall_returns_all_rules_as_procedural_items():
    pm = ProceduralMemory(RULES)
    q = RecallQuery(kinds=[MemoryKind.PROCEDURAL])
    items = pm.recall(q)
    assert all(it.kind == MemoryKind.PROCEDURAL for it in items)
    assert {it.content["id"] for it in items} == {"score_in_range", "no_duplicate_question"}


def test_rules_have_high_salience():
    pm = ProceduralMemory(RULES)
    items = pm.recall(RecallQuery(kinds=[MemoryKind.PROCEDURAL]))
    assert all(it.salience >= 1.0 for it in items)


def test_add_is_not_supported():
    pm = ProceduralMemory(RULES)
    with pytest.raises(NotImplementedError):
        pm.add(MemoryItem(kind=MemoryKind.PROCEDURAL, content={}))
