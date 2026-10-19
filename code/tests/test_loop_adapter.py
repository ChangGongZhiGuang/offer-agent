from interviewforge.loop.adapter import SearchAdapter, collect_asked_ids
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.memory.working import WorkingMemory
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore

# 确定性关键词 embedder: 维度=vocab, 每维=该词(小写)出现次数
_VOCAB = ["redis", "mysql", "并发", "分布式", "锁", "索引", "缓存"]


def _embed(texts):
    return [[float(t.lower().count(w)) for w in _VOCAB] for t in texts]


def _memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def _retriever():
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    qs = [
        Question(id="be-1", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard"),
        Question(id="be-2", role="后端", topic="mysql",
                 stem="MySQL 聚簇索引和非聚簇索引区别", answer="回表", difficulty="medium"),
    ]
    seed_questions(qb, vs, _embed, qs)
    return Retriever(vs, qb, _embed)


def test_collect_asked_ids_from_episodic(tmp_path):
    mem = _memory(tmp_path)
    mem.remember(MemoryItem(kind=MemoryKind.EPISODIC,
                            content={"question_id": "be-1", "score": 4}))
    mem.remember(MemoryItem(kind=MemoryKind.EPISODIC,
                            content={"question_id": "be-2", "score": 3}))
    assert set(collect_asked_ids(mem)) == {"be-1", "be-2"}


def test_adapter_returns_question_dict(tmp_path):
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    out = adapter(role="后端", topic="redis")
    assert out[0]["question_id"] == "be-1"
    assert "Redis" in out[0]["question"]
    assert adapter.last_id == "be-1"


def test_adapter_dedups_via_episodic(tmp_path):
    mem = _memory(tmp_path)
    # be-1 已问过 -> 检索 redis 时应被排除, 返回次优 be-2
    mem.remember(MemoryItem(kind=MemoryKind.EPISODIC,
                            content={"question_id": "be-1", "score": 4}))
    adapter = SearchAdapter(_retriever(), mem)
    out = adapter(role="后端", topic="redis")
    assert out[0]["question_id"] == "be-2"


def test_adapter_empty_when_all_asked(tmp_path):
    mem = _memory(tmp_path)
    for qid in ("be-1", "be-2"):
        mem.remember(MemoryItem(kind=MemoryKind.EPISODIC,
                                content={"question_id": qid, "score": 4}))
    adapter = SearchAdapter(_retriever(), mem)
    out = adapter(role="后端", topic="redis")
    assert out == [] and adapter.last_id is None


def test_adapter_exposes_last_reference_answer(tmp_path):
    """D: 检索到的题应把参考答案存到 last_reference_answer 供 Grader 用。"""
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    adapter(role="后端", topic="redis")
    assert adapter.last_reference_answer == "SETNX"


def test_adapter_resets_reference_answer_on_empty(tmp_path):
    mem = _memory(tmp_path)
    for qid in ("be-1", "be-2"):
        mem.remember(MemoryItem(kind=MemoryKind.EPISODIC,
                                content={"question_id": qid, "score": 4}))
    adapter = SearchAdapter(_retriever(), mem)
    adapter(role="后端", topic="redis")
    assert adapter.last_reference_answer is None


def test_set_next_query_overrides_build_query_once(tmp_path):
    """A: Planner 注入的 query 应替换默认 build_query, 且用完即清 (one-shot)。"""
    captured: list[str] = []

    class _SpyRetriever:
        def retrieve_one(self, query_text, *, top_k, asked_ids=None,
                         target_difficulty=None, where=None):
            captured.append(query_text)
            return None

    mem = _memory(tmp_path)
    adapter = SearchAdapter(_SpyRetriever(), mem)
    adapter.set_next_query("缓存一致性 redis 后端 MySQL")
    adapter(role="后端", topic="redis")
    assert captured[-1] == "缓存一致性 redis 后端 MySQL"

    # 第二次调用没再 set, 应该回退到默认 build_query
    adapter(role="后端", topic="redis")
    assert captured[-1] == "后端 redis"


def test_set_next_query_none_uses_fallback(tmp_path):
    """显式传 None 不应破坏默认行为。"""
    captured: list[str] = []

    class _SpyRetriever:
        def retrieve_one(self, query_text, *, top_k, asked_ids=None,
                         target_difficulty=None, where=None):
            captured.append(query_text)
            return None

    mem = _memory(tmp_path)
    adapter = SearchAdapter(_SpyRetriever(), mem)
    adapter.set_next_query(None)
    adapter(role="后端", topic="redis")
    assert captured[-1] == "后端 redis"


def test_adapter_auto_builds_where_from_role(tmp_path):
    """E: SearchAdapter 首次检索按 role 做硬过滤, 命中空结果后降级到无过滤。"""
    calls: list = []

    class _SpyRetriever:
        def retrieve_one(self, query_text, *, top_k, asked_ids=None,
                         target_difficulty=None, where=None):
            calls.append(where)
            return None

    adapter = SearchAdapter(_SpyRetriever(), _memory(tmp_path))
    adapter(role="后端", topic="redis")
    # 第一次用 role 过滤, 第二次降级到无过滤
    assert calls[0] == {"role": "后端"}
    assert calls[1] is None


def test_adapter_disable_role_filter(tmp_path):
    """允许关闭硬过滤 (例如跨岗位混合检索场景)。"""
    captured: dict = {}

    class _SpyRetriever:
        def retrieve_one(self, query_text, *, top_k, asked_ids=None,
                         target_difficulty=None, where=None):
            captured["where"] = where
            return None

    adapter = SearchAdapter(_SpyRetriever(), _memory(tmp_path),
                            hard_filter_by_role=False)
    adapter(role="后端", topic="redis")
    assert captured["where"] is None


def test_adapter_forwards_target_difficulty(tmp_path):
    """B: difficulty 应透传给 retriever, 重排后取与目标难度最近的题。"""
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    # be-1(hard) 与 be-2(medium) 同主题; 显式要 medium 应优先 be-2 (二者向量相同时,
    # 难度差 0 < 1)
    out = adapter(role="后端", topic="redis mysql", difficulty="medium")
    # 至少 be-2(medium) 应排在 be-1(hard) 前面
    assert adapter.last_id == "be-2"
    assert out[0]["question_id"] == "be-2"
