"""ensure_index 增量向量化: 首启全量, 之后只补缺失/变更, 删题清理残留。"""
from interviewforge.rag.chunking import embeddable_text, stem_hash
from interviewforge.rag.index_builder import ensure_index
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore


class _CountingEmbedder:
    """记录每次被请求 embed 的文本, 用于断言增量只算变更题。"""
    def __init__(self, dim=4):
        self.dim = dim
        self.calls: list[list[str]] = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t))] * self.dim for t in texts]


def _q(qid, stem, role="后端", topic="redis", difficulty="medium"):
    return Question(id=qid, role=role, topic=topic, stem=stem,
                    answer="a", difficulty=difficulty)


def test_first_run_embeds_all():
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一"))
    qb.add(_q("q2", "题二"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    n = ensure_index(qb, emb, vs)
    assert n == 2
    assert set(vs.all_entries()) == {"q1", "q2"}
    # 元数据带 stem_hash
    assert vs.all_entries()["q1"]["stem_hash"] == stem_hash(embeddable_text(_q("q1", "题一")))


def test_second_run_skips_unchanged():
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    ensure_index(qb, emb, vs)
    emb.calls.clear()
    n = ensure_index(qb, emb, vs)   # 无变更
    assert n == 0
    assert emb.calls == []          # 完全没调 embedding


def test_changed_stem_reembeds_only_that():
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一"))
    qb.add(_q("q2", "题二"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    ensure_index(qb, emb, vs)
    emb.calls.clear()
    qb.add(_q("q1", "题一被改了"))   # 覆盖同 id, 题干变更
    n = ensure_index(qb, emb, vs)
    assert n == 1
    assert emb.calls == [["题一被改了"]]
    assert vs.all_entries()["q1"]["stem_hash"] == stem_hash("题一被改了")


def test_metadata_only_change_refreshes_meta():
    """题干不变但 role/topic/difficulty 变更: 只刷元数据, 不调 embedding。"""
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一", role="后端", topic="redis", difficulty="medium"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    ensure_index(qb, emb, vs)
    emb.calls.clear()
    qb.add(_q("q1", "题一", role="后端", topic="mysql", difficulty="hard"))  # 题干不变
    n = ensure_index(qb, emb, vs)
    assert n == 0                      # 不计入重 embed 题数
    assert emb.calls == []             # 完全没调 embedding 接口
    meta = vs.all_entries()["q1"]
    assert meta["topic"] == "mysql" and meta["difficulty"] == "hard"
    assert meta["stem_hash"] == stem_hash("题一")
    # 原向量保留: "题一" (len=2) 首启时 embed 为 [2,2,2,2], 刷元数据不应丢向量
    assert vs.query([2.0, 2.0, 2.0, 2.0], top_k=1) == ["q1"]


def test_stem_and_meta_change_reembeds_once():
    """题干与元数据同时变更: 走向量重算通道, 新元数据一并 upsert。"""
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一", topic="redis", difficulty="medium"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    ensure_index(qb, emb, vs)
    emb.calls.clear()
    qb.add(_q("q1", "题一改了", topic="mysql", difficulty="hard"))
    n = ensure_index(qb, emb, vs)
    assert n == 1
    assert emb.calls == [["题一改了"]]
    meta = vs.all_entries()["q1"]
    assert meta["topic"] == "mysql" and meta["difficulty"] == "hard"
    assert meta["stem_hash"] == stem_hash("题一改了")


def test_removed_question_purged_from_store():
    qb = InMemoryQuestionBank()
    qb.add(_q("q1", "题一"))
    qb.add(_q("q2", "题二"))
    vs = InMemoryVectorStore()
    emb = _CountingEmbedder()
    ensure_index(qb, emb, vs)
    qb.delete("q1")
    ensure_index(qb, emb, vs)
    assert set(vs.all_entries()) == {"q2"}
