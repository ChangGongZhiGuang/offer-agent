from interviewforge.memory.types import (
    ConsolidateTrigger,
    MemoryItem,
    MemoryKind,
    RecallQuery,
    effective_salience,
    matches_filter,
)


def test_memory_item_roundtrip():
    item = MemoryItem(
        kind=MemoryKind.EPISODIC,
        content={"role": "后端", "topic": "redis", "note": "答对"},
        salience=0.8,
        id="abc",
        created_at=100.0,
    )
    d = item.to_dict()
    assert d == {
        "id": "abc",
        "kind": "episodic",
        "content": {"role": "后端", "topic": "redis", "note": "答对"},
        "salience": 0.8,
        "created_at": 100.0,
    }
    assert MemoryItem.from_dict(d) == item


def test_memory_item_defaults():
    item = MemoryItem(kind=MemoryKind.WORKING, content={})
    assert isinstance(item.id, str) and len(item.id) > 0
    assert item.salience == 1.0
    assert item.created_at > 0


def test_effective_salience_decays_with_age():
    item = MemoryItem(kind=MemoryKind.EPISODIC, content={}, salience=1.0, created_at=0.0)
    assert effective_salience(item, now=3600.0, half_life_seconds=3600.0) == 0.5
    assert effective_salience(item, now=0.0, half_life_seconds=3600.0) == 1.0


def test_matches_filter():
    item = MemoryItem(kind=MemoryKind.EPISODIC, content={"role": "后端", "topic": "redis"})
    assert matches_filter(item, role="后端", topic="redis") is True
    assert matches_filter(item, role="前端") is False
    assert matches_filter(item, topic="mysql") is False
    assert matches_filter(item, role=None, topic=None) is True


def test_recall_query_defaults():
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC, MemoryKind.EPISODIC])
    assert q.role is None and q.topic is None and q.limit == 5


def test_consolidate_trigger_values():
    assert ConsolidateTrigger.WORKING_TO_EPISODIC.value == "working_to_episodic"
    assert ConsolidateTrigger.EPISODIC_TO_SEMANTIC.value == "episodic_to_semantic"
    assert ConsolidateTrigger.SEMANTIC_TO_PERSIST.value == "semantic_to_persist"
