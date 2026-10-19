from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery


def _item(note, salience=1.0, role=None, created_at=0.0):
    content = {"note": note}
    if role:
        content["role"] = role
    return MemoryItem(kind=MemoryKind.EPISODIC, content=content,
                      salience=salience, created_at=created_at)


def test_add_persists_and_reloads(tmp_path):
    path = tmp_path / "episodic.jsonl"
    em = EpisodicMemory(path)
    em.add(_item("第3题答错"))
    assert [it.content["note"] for it in EpisodicMemory(path).all()] == ["第3题答错"]


def test_recall_ranks_by_effective_salience(tmp_path):
    em = EpisodicMemory(tmp_path / "e.jsonl")
    em.add(_item("low", salience=0.2, created_at=0.0))
    em.add(_item("high", salience=0.9, created_at=0.0))
    q = RecallQuery(kinds=[MemoryKind.EPISODIC], limit=5)
    notes = [it.content["note"] for it in em.recall(q, now=0.0)]
    assert notes == ["high", "low"]


def test_recall_respects_limit_and_filter(tmp_path):
    em = EpisodicMemory(tmp_path / "e.jsonl")
    em.add(_item("a", salience=0.9, role="后端", created_at=0.0))
    em.add(_item("b", salience=0.8, role="后端", created_at=0.0))
    em.add(_item("c", salience=0.7, role="前端", created_at=0.0))
    q = RecallQuery(kinds=[MemoryKind.EPISODIC], role="后端", limit=1)
    notes = [it.content["note"] for it in em.recall(q, now=0.0)]
    assert notes == ["a"]


def test_prune_drops_low_salience_and_rewrites_file(tmp_path):
    path = tmp_path / "e.jsonl"
    em = EpisodicMemory(path)
    em.add(_item("keep", salience=0.9, created_at=0.0))
    em.add(_item("forget", salience=0.05, created_at=0.0))
    em.prune(salience_floor=0.1, now=0.0)
    assert [it.content["note"] for it in em.all()] == ["keep"]
    assert [it.content["note"] for it in EpisodicMemory(path).all()] == ["keep"]
