from interviewforge.rag.position_bank import InMemoryPositionBank, Position


def test_inmemory_position_list_empty():
    bank = InMemoryPositionBank()
    assert bank.list_all() == []


def test_inmemory_position_add_and_list():
    bank = InMemoryPositionBank()
    bank.add(Position(id="p1", name="后端", color="#4F46E5"))
    result = bank.list_all()
    assert len(result) == 1
    assert result[0].name == "后端"
    assert result[0].color == "#4F46E5"


def test_inmemory_position_add_multiple():
    bank = InMemoryPositionBank()
    bank.add(Position(id="p1", name="后端", color="#4F46E5"))
    bank.add(Position(id="p2", name="前端", color="#0284C7"))
    assert len(bank.list_all()) == 2


def test_inmemory_position_overwrite_same_id():
    bank = InMemoryPositionBank()
    bank.add(Position(id="p1", name="后端", color="#4F46E5"))
    bank.add(Position(id="p1", name="后端工程师", color="#4F46E5"))
    result = bank.list_all()
    assert len(result) == 1
    assert result[0].name == "后端工程师"


def test_inmemory_position_delete():
    bank = InMemoryPositionBank()
    bank.add(Position(id="p1", name="后端", color="#4F46E5"))
    bank.add(Position(id="p2", name="前端", color="#0284C7"))
    bank.delete("p1")
    result = bank.list_all()
    assert len(result) == 1 and result[0].id == "p2"


def test_inmemory_position_delete_missing_is_noop():
    bank = InMemoryPositionBank()
    bank.add(Position(id="p1", name="后端"))
    bank.delete("nope")
    assert len(bank.list_all()) == 1


def test_position_default_color():
    p = Position(id="p1", name="后端")
    assert p.color == "#4F46E5"
