from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery
from interviewforge.memory.working import WorkingMemory


def _item(note, role=None, salience=1.0):
    content = {"note": note}
    if role:
        content["role"] = role
    return MemoryItem(kind=MemoryKind.WORKING, content=content, salience=salience)


def test_add_and_all_preserves_order():
    wm = WorkingMemory()
    wm.add(_item("a"))
    wm.add(_item("b"))
    assert [it.content["note"] for it in wm.all()] == ["a", "b"]


def test_recall_filters_by_role():
    wm = WorkingMemory()
    wm.add(_item("x", role="后端"))
    wm.add(_item("y", role="前端"))
    q = RecallQuery(kinds=[MemoryKind.WORKING], role="后端")
    notes = [it.content["note"] for it in wm.recall(q)]
    assert notes == ["x"]


def test_recall_no_filter_returns_all():
    wm = WorkingMemory()
    wm.add(_item("a"))
    wm.add(_item("b"))
    q = RecallQuery(kinds=[MemoryKind.WORKING])
    assert len(wm.recall(q)) == 2


def test_clear_empties_window():
    wm = WorkingMemory()
    wm.add(_item("a"))
    wm.clear()
    assert wm.all() == []
