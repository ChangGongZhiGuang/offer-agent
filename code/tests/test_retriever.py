from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore


def _setup():
    vs = InMemoryVectorStore()
    vs.add(["q1", "q2"], [[1.0, 0.0], [0.9, 0.1]])
    bank = InMemoryQuestionBank()
    bank.add(Question(id="q1", role="后端", topic="redis", stem="redis锁", answer="A", difficulty="hard"))
    bank.add(Question(id="q2", role="后端", topic="redis", stem="redis持久化", answer="B", difficulty="medium"))
    return vs, bank


def test_retrieve_one_returns_most_similar():
    vs, bank = _setup()
    embedder = lambda texts: [[1.0, 0.0]]
    q = Retriever(vs, bank, embedder).retrieve_one("redis 怎么加锁")
    assert q.id == "q1"


def test_dedup_excludes_asked_ids():
    vs, bank = _setup()
    embedder = lambda texts: [[1.0, 0.0]]
    q = Retriever(vs, bank, embedder).retrieve_one("redis", asked_ids=["q1"])
    assert q.id == "q2"


def test_difficulty_rerank_overrides_similarity():
    vs, bank = _setup()
    embedder = lambda texts: [[1.0, 0.0]]
    q = Retriever(vs, bank, embedder).retrieve_one("redis", target_difficulty="medium")
    assert q.id == "q2"


def test_returns_none_when_all_asked():
    vs, bank = _setup()
    embedder = lambda texts: [[1.0, 0.0]]
    q = Retriever(vs, bank, embedder).retrieve_one("redis", asked_ids=["q1", "q2"])
    assert q is None


def test_retriever_forwards_where_to_vector_store():
    """E: retrieve_one(where=...) 应原样透传给 vector_store.query。"""
    captured = {}

    class _SpyVS:
        def query(self, embedding, top_k, where=None):
            captured["where"] = where
            return []

    bank = InMemoryQuestionBank()
    r = Retriever(_SpyVS(), bank, lambda texts: [[1.0, 0.0]])
    r.retrieve_one("redis", where={"role": "后端"})
    assert captured["where"] == {"role": "后端"}


def test_embedder_called_with_query_text():
    vs, bank = _setup()
    captured = {}
    def embedder(texts):
        captured["texts"] = texts
        return [[1.0, 0.0]]
    Retriever(vs, bank, embedder).retrieve_one("redis 怎么加锁")
    assert captured["texts"] == ["redis 怎么加锁"]


def test_retrieve_many_returns_ranked_unasked():
    from interviewforge.rag.seed import seed_questions
    from interviewforge.loop.driver import make_keyword_embedder

    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    embed = make_keyword_embedder(["redis", "mysql"])
    seed_questions(qb, vs, embed, [
        Question(id="a", role="后端", topic="redis", stem="redis 锁", answer="x", difficulty="hard"),
        Question(id="b", role="后端", topic="redis", stem="redis 过期", answer="y", difficulty="easy"),
    ])
    r = Retriever(vs, qb, embed)
    got = r.retrieve_many("redis", top_k=5, asked_ids=["a"], where={"role": "后端"})
    ids = [q.id for q in got]
    assert "a" not in ids and "b" in ids          # 已问的被去重
