"""向量库契约测试: all_entries / upsert / delete 语义在 InMemory 与 Chroma 一致。"""
import pytest

from interviewforge.rag.vector_store import InMemoryVectorStore


def test_inmemory_upsert_overwrites_same_id():
    vs = InMemoryVectorStore()
    vs.upsert(["a"], [[1.0, 0.0]], [{"role": "后端", "stem_hash": "h1"}])
    assert vs.all_entries()["a"]["stem_hash"] == "h1"
    vs.upsert(["a"], [[1.0, 0.0]], [{"role": "后端", "stem_hash": "h2"}])
    assert vs.all_entries()["a"]["stem_hash"] == "h2"
    # 覆盖不应新增条目
    assert set(vs.all_entries()) == {"a"}


def test_inmemory_delete_removes():
    vs = InMemoryVectorStore()
    vs.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]],
           [{"role": "后端"}, {"role": "前端"}])
    vs.delete(["a"])
    assert set(vs.all_entries()) == {"b"}
    # 删不存在的 id 不报错
    vs.delete(["ghost"])
    assert set(vs.all_entries()) == {"b"}


def test_inmemory_query_still_works_after_refactor():
    vs = InMemoryVectorStore()
    vs.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]],
           [{"role": "后端"}, {"role": "前端"}])
    assert vs.query([1.0, 0.0], top_k=1) == ["a"]
    assert vs.query([1.0, 0.0], top_k=2, where={"role": "前端"}) == ["b"]


# ── Chroma 契约 (仅在装了 chromadb 时跑) ──────────────────────────

@pytest.fixture()
def chroma_store(tmp_path):
    chromadb = pytest.importorskip("chromadb")  # noqa: F841
    from interviewforge.rag.vector_store import ChromaVectorStore
    return ChromaVectorStore(path=str(tmp_path / "chroma"), collection_name="questions")


def test_chroma_upsert_overwrites_same_id(chroma_store):
    chroma_store.upsert(["a"], [[1.0, 0.0]], [{"role": "后端", "stem_hash": "h1"}])
    assert chroma_store.all_entries()["a"]["stem_hash"] == "h1"
    chroma_store.upsert(["a"], [[1.0, 0.0]], [{"role": "后端", "stem_hash": "h2"}])
    assert chroma_store.all_entries()["a"]["stem_hash"] == "h2"
    assert set(chroma_store.all_entries()) == {"a"}


def test_chroma_delete_removes(chroma_store):
    chroma_store.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]],
                     [{"role": "后端"}, {"role": "前端"}])
    chroma_store.delete(["a"])
    assert set(chroma_store.all_entries()) == {"b"}


def test_chroma_query_multi_field_where(chroma_store):
    """回归: role+topic 两字段扁平过滤需转 $and, 否则 Chroma 报错。"""
    chroma_store.add(
        ["a", "b", "c"],
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
        [{"role": "后端", "topic": "redis"},
         {"role": "后端", "topic": "mysql"},
         {"role": "前端", "topic": "redis"}],
    )
    hits = chroma_store.query([1.0, 0.0], top_k=3,
                              where={"role": "后端", "topic": "redis"})
    assert hits == ["a"]
    # 单字段仍直传
    assert set(chroma_store.query([1.0, 0.0], top_k=3,
                                  where={"role": "后端"})) == {"a", "b"}


def test_chroma_persistence_reopen(tmp_path):
    chromadb = pytest.importorskip("chromadb")  # noqa: F841
    from interviewforge.rag.vector_store import ChromaVectorStore
    path = str(tmp_path / "chroma")
    s1 = ChromaVectorStore(path=path, collection_name="questions")
    s1.upsert(["a"], [[1.0, 0.0]], [{"role": "后端", "stem_hash": "h1"}])
    # 重开同一目录应能读到已持久化的条目 (不重新 embed)
    s2 = ChromaVectorStore(path=path, collection_name="questions")
    assert s2.all_entries()["a"]["stem_hash"] == "h1"
