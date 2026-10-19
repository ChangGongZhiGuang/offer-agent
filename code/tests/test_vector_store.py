import pytest

from interviewforge.rag.vector_store import InMemoryVectorStore


def test_inmemory_query_returns_nearest_first():
    vs = InMemoryVectorStore()
    vs.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    assert vs.query([0.9, 0.1], top_k=2) == ["a", "b"]
    assert vs.query([0.1, 0.9], top_k=1) == ["b"]


def test_inmemory_query_top_k_limits():
    vs = InMemoryVectorStore()
    vs.add(["a", "b", "c"], [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])
    assert len(vs.query([1.0, 0.0], top_k=2)) == 2


def test_inmemory_zero_vector_no_crash():
    vs = InMemoryVectorStore()
    vs.add(["a"], [[0.0, 0.0]])
    assert vs.query([1.0, 0.0], top_k=1) == ["a"]


def test_inmemory_where_filters_by_metadata():
    """E: where={'role': '后端'} 只保留 role=后端 的候选, 再做相似度。"""
    vs = InMemoryVectorStore()
    vs.add(
        ids=["be", "algo"],
        embeddings=[[1.0, 0.0], [0.99, 0.01]],  # algo 更相似
        metadatas=[{"role": "后端"}, {"role": "算法"}],
    )
    assert vs.query([1.0, 0.0], top_k=2) == ["be", "algo"]
    assert vs.query([1.0, 0.0], top_k=2, where={"role": "后端"}) == ["be"]
    assert vs.query([1.0, 0.0], top_k=2, where={"role": "算法"}) == ["algo"]


def test_inmemory_where_missing_metadata_excluded():
    """没写 metadata 的条目, 当 where 指定时应被排除 (与 Chroma 行为对齐)。"""
    vs = InMemoryVectorStore()
    vs.add(ids=["a"], embeddings=[[1.0, 0.0]])  # 无 metadata
    assert vs.query([1.0, 0.0], top_k=1) == ["a"]
    assert vs.query([1.0, 0.0], top_k=1, where={"role": "x"}) == []


def _has_chromadb():
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_chromadb(), reason="chromadb not installed")
def test_chroma_roundtrip(tmp_path):
    from interviewforge.rag.vector_store import ChromaVectorStore
    vs = ChromaVectorStore(path=str(tmp_path / "chroma"), collection_name="test")
    vs.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    assert vs.query([0.9, 0.1], top_k=1) == ["a"]
