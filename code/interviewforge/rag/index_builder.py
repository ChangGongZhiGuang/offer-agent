"""从题库构建向量索引: 全量 (内存) 与增量 (持久库 Chroma) 两条路径。

- build_index_from_bank: 默认全量灌入内存向量库 (离线测试 / FAKE embed)。
- metadata_for: 向量条目元数据唯一构造源 (role/topic/difficulty/stem_hash),
  写入与比对均复用它, 避免多处字段清单不同步导致每次重启都重 embed 的"永久脏"。
- ensure_index: 对传入的 (可持久化) vector_store 按 id+全量元数据比对增量补齐:
  缺失或题干变更的题重新 embed 后 upsert; 仅过滤元数据漂移的题走
  update_metadata 只刷元数据 (不调 embedding); 题库已删除的残留 id 被清除。
与 factory.build_retriever 旧行为不同: 这里覆盖题库全部题目, 让检索能命中
MySQL 里的全部题 (而非仅 SEED_QUESTIONS)。
"""
from __future__ import annotations

from typing import Callable

from interviewforge.rag.chunking import embeddable_text, stem_hash
from interviewforge.rag.question_bank import QuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.vector_store import InMemoryVectorStore, VectorStore


def metadata_for(q) -> dict:
    """向量条目元数据唯一构造源: role/topic/difficulty/stem_hash。

    ensure_index / build_index_from_bank / factory.QuestionIndexSyncer 三条写入
    路径统一复用本函数, 增量判定也用其返回值整体比对 —— 字段增删只改这一处,
    消除多处硬编码清单不同步导致的"永久脏"重 embed。
    """
    return {"role": q.role, "topic": q.topic, "difficulty": q.difficulty,
            "stem_hash": stem_hash(embeddable_text(q))}


def ensure_index(question_bank: QuestionBank,
                 embedder: Callable[[list[str]], list[list[float]]],
                 vector_store: VectorStore) -> int:
    """按 id+元数据整体比对增量补齐 vector_store, 返回本次新 embed 的题数。

    - 题库新增 / 题干变更的题: 向量本身已失效, 重新 embed 后 upsert。
    - 题干未变、仅 role/topic/difficulty 漂移的题: 走 update_metadata 只刷
      元数据, 不调 embedding 接口 (省去可避免的外部 API 成本)。
    - 题库已删除、但 vector_store 残留的 id: delete 掉。
    """
    questions = question_bank.list_all()
    bank_ids = {q.id for q in questions}
    stored = vector_store.all_entries()          # id -> metadata
    to_embed: list = []
    meta_only: list = []
    for q in questions:
        meta = metadata_for(q)
        if q.id not in stored:                   # 新增: 必须走向量写入
            to_embed.append(q)
        elif stored[q.id] != meta:               # 整体比对, 不逐字段硬编码
            if stored[q.id].get("stem_hash") != meta["stem_hash"]:
                to_embed.append(q)               # 题干已变, 向量需重算
            else:
                meta_only.append(q)              # 纯元数据漂移, 免 embedding
    if to_embed:
        embeddings = embedder([embeddable_text(q) for q in to_embed])
        vector_store.upsert(
            ids=[q.id for q in to_embed],
            embeddings=embeddings,
            metadatas=[metadata_for(q) for q in to_embed],
        )
    if meta_only:
        vector_store.update_metadata([q.id for q in meta_only],
                                     [metadata_for(q) for q in meta_only])
    stale = [i for i in stored if i not in bank_ids]
    if stale:
        vector_store.delete(stale)
    return len(to_embed)


def build_index_from_bank(question_bank: QuestionBank,
                          embedder: Callable[[list[str]], list[list[float]]],
                          vector_store: VectorStore | None = None) -> Retriever:
    """构建可检索的 Retriever。

    vector_store=None: 全量灌入新建 InMemoryVectorStore (离线/FAKE, 每次重建)。
    传入 vector_store: 在其上跑增量 ensure_index (持久库首启全量、之后增量)。
    """
    if vector_store is None:
        vector_store = InMemoryVectorStore()
        questions = question_bank.list_all()
        if questions:
            embeddings = embedder([embeddable_text(q) for q in questions])
            vector_store.add(
                ids=[q.id for q in questions],
                embeddings=embeddings,
                metadatas=[metadata_for(q) for q in questions],
            )
    else:
        ensure_index(question_bank, embedder, vector_store)
    return Retriever(vector_store, question_bank, embedder)
