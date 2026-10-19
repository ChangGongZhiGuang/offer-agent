import pytest

from interviewforge.api import factory


def _embedder(texts):
    return [[float(len(t))] for t in texts]


def test_default_is_inmemory(monkeypatch):
    monkeypatch.delenv("INTERVIEWFORGE_QUESTION_BANK", raising=False)
    r = factory.build_retriever(_embedder)
    from interviewforge.rag.question_bank import InMemoryQuestionBank
    assert isinstance(r.question_bank, InMemoryQuestionBank)


def test_inmemory_explicit(monkeypatch):
    monkeypatch.setenv("INTERVIEWFORGE_QUESTION_BANK", "inmemory")
    r = factory.build_retriever(_embedder)
    assert r.question_bank is not None


def test_unknown_bank_raises(monkeypatch):
    monkeypatch.setenv("INTERVIEWFORGE_QUESTION_BANK", "redis")
    with pytest.raises(ValueError):
        factory.build_retriever(_embedder)


def test_memory_mode_default(monkeypatch):
    """未设 VECTOR_STORE 时走旧行为: build_vector_store 返回 InMemory。"""
    monkeypatch.delenv("INTERVIEWFORGE_VECTOR_STORE", raising=False)
    monkeypatch.setenv("INTERVIEWFORGE_QUESTION_BANK", "inmemory")
    from interviewforge.rag.vector_store import InMemoryVectorStore
    r = factory.build_retriever(_embedder)
    assert isinstance(r.vector_store, InMemoryVectorStore)
    assert factory.is_chroma_mode() is False


def test_chroma_mode_routes_through_ensure_index(monkeypatch):
    """VECTOR_STORE=chroma 时 build_retriever 使用 build_vector_store 的实例,
    并对题库全量跑增量 ensure_index (元数据含 stem_hash)。"""
    monkeypatch.setenv("INTERVIEWFORGE_QUESTION_BANK", "inmemory")
    monkeypatch.setenv("INTERVIEWFORGE_VECTOR_STORE", "chroma")
    from interviewforge.rag.vector_store import InMemoryVectorStore
    marker = InMemoryVectorStore()
    monkeypatch.setattr(factory, "build_vector_store", lambda: marker)
    r = factory.build_retriever(_embedder)
    assert r.vector_store is marker
    entries = marker.all_entries()
    assert entries  # SEED 题已入索引
    assert all("stem_hash" in m for m in entries.values())
