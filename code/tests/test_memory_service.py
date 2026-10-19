from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import (
    ConsolidateTrigger,
    MemoryItem,
    MemoryKind,
    RecallQuery,
)
from interviewforge.memory.working import WorkingMemory


def _service(tmp_path, now=0.0):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([{"id": "r1", "desc": "rule one"}]),
        salience_floor=0.1,
        now_fn=lambda: now,
    )


def _item(kind, note, salience=1.0, role=None, created_at=0.0):
    content = {"note": note}
    if role:
        content["role"] = role
    return MemoryItem(kind=kind, content=content, salience=salience, created_at=created_at)


def test_remember_dispatches_by_kind(tmp_path):
    svc = _service(tmp_path)
    svc.remember(_item(MemoryKind.WORKING, "w"))
    svc.remember(_item(MemoryKind.EPISODIC, "e"))
    assert [it.content["note"] for it in svc.working.all()] == ["w"]
    assert [it.content["note"] for it in svc.episodic.all()] == ["e"]


def test_recall_merges_and_ranks_across_kinds(tmp_path):
    svc = _service(tmp_path)
    svc.remember(_item(MemoryKind.EPISODIC, "ep-low", salience=0.3))
    svc.remember(_item(MemoryKind.SEMANTIC, "sem-high", salience=0.9))
    q = RecallQuery(kinds=[MemoryKind.SEMANTIC, MemoryKind.EPISODIC], limit=5)
    notes = [it.content["note"] for it in svc.recall(q)]
    assert notes == ["sem-high", "ep-low"]


def test_recall_respects_limit(tmp_path):
    svc = _service(tmp_path)
    for i in range(5):
        svc.remember(_item(MemoryKind.EPISODIC, f"e{i}", salience=0.5))
    q = RecallQuery(kinds=[MemoryKind.EPISODIC], limit=2)
    assert len(svc.recall(q)) == 2


def test_recall_procedural_rules_surface_first(tmp_path):
    svc = _service(tmp_path)
    svc.remember(_item(MemoryKind.EPISODIC, "ep", salience=0.9))
    q = RecallQuery(kinds=[MemoryKind.PROCEDURAL, MemoryKind.EPISODIC], limit=5)
    notes_or_ids = [it.content.get("note") or it.content.get("id") for it in svc.recall(q)]
    assert notes_or_ids[0] == "r1"


def test_consolidate_working_to_episodic(tmp_path):
    svc = _service(tmp_path)
    svc.remember(_item(MemoryKind.WORKING, "a"))
    svc.remember(_item(MemoryKind.WORKING, "b"))
    svc.consolidate(ConsolidateTrigger.WORKING_TO_EPISODIC)
    assert svc.working.all() == []
    episodic_notes = [it.content["note"] for it in svc.episodic.all()]
    assert episodic_notes == ["a", "b"]
    assert all(it.kind == MemoryKind.EPISODIC for it in svc.episodic.all())


def test_consolidate_episodic_to_semantic_distills_and_forgets(tmp_path):
    svc = _service(tmp_path)
    svc.remember(_item(MemoryKind.EPISODIC, "keep", salience=0.9, created_at=0.0))
    svc.remember(_item(MemoryKind.EPISODIC, "forget", salience=0.05, created_at=0.0))
    svc.consolidate(ConsolidateTrigger.EPISODIC_TO_SEMANTIC)
    sem = svc.semantic.recall(RecallQuery(kinds=[MemoryKind.SEMANTIC], limit=10))
    assert [it.content["note"] for it in sem] == ["keep"]
    assert all(it.kind == MemoryKind.SEMANTIC for it in sem)
    assert [it.content["note"] for it in svc.episodic.all()] == ["keep"]
