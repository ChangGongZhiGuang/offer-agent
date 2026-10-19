"""向量库抽象。InMemory 余弦 (单测) + Chroma 嵌入式 (生产)。换库不动检索逻辑。

支持 where 元数据等值过滤 —— 检索阶段先按硬约束 (如 role=后端) 剪枝再做相似度,
避免向量库返回跨岗位噪声题。
"""
from __future__ import annotations

import math
from typing import Protocol


# ── 向量库协议 ─────────────────────────────────────────────────────────────
# 只要实现 add / query 就可以替换底层引擎 (InMemory / Chroma / …)
# 上层 Retriever 只依赖这个协议, 不关心具体实现

class VectorStore(Protocol):
    def add(self, ids: list[str], embeddings: list[list[float]],
            metadatas: list[dict] | None = None) -> None: ...
    def query(self, embedding: list[float], top_k: int,
              where: dict | None = None) -> list[str]: ...
    def all_entries(self) -> dict[str, dict]: ...
    def upsert(self, ids: list[str], embeddings: list[list[float]],
               metadatas: list[dict] | None = None) -> None: ...
    def update_metadata(self, ids: list[str],
                        metadatas: list[dict]) -> None: ...
    def delete(self, ids: list[str]) -> None: ...


# ═══════════════════════════════════════════════════════════════════════════
#  余弦相似度 + 元数据过滤工具函数
# ═══════════════════════════════════════════════════════════════════════════

def _cosine(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度, 返回 [-1, 1]。

    余弦 = (A·B) / (|A| * |B|); 零向量返回 0.0。
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _matches_where(meta: dict | None, where: dict | None) -> bool:
    """判断一条记录的 metadata 是否满足 where 条件 (等值匹配)。

    行为对齐 Chroma: meta 缺字段视为不匹配。
    where 为空字典/None 时接受所有记录。
    """
    if not where:
        return True
    if meta is None:
        return False
    for k, v in where.items():
        if meta.get(k) != v:
            return False
    return True


def _chroma_where(where: dict | None) -> dict | None:
    """把扁平等值过滤 dict 转成 Chroma where 语法, 与 InMemory 多键语义对齐。

    Chroma 顶层只接受单个操作符: 单键直传, 多键用 $and 组合。
    空/None 返回 None (不过滤)。
    """
    if not where:
        return None
    items = list(where.items())
    if len(items) == 1:
        k, v = items[0]
        return {k: v}
    return {"$and": [{k: v} for k, v in items]}


# ═══════════════════════════════════════════════════════════════════════════
#  InMemory 实现 (开发 / 单测)
# ═══════════════════════════════════════════════════════════════════════════

class InMemoryVectorStore:
    """全内存向量库, 余弦相似度暴力排序。

    适用于: 单元测试、小规模题库、无需持久化的场景。
    每次 query 遍历全部向量做全量排序 (O(n)), 题库量大时建议换 Chroma。
    内部用 dict[id] -> (embedding, metadata), 同 id 写入即覆盖。
    """

    def __init__(self):
        # id -> (embedding, metadata), 保留 metadata 以支持 where 过滤
        self._data: dict[str, tuple[list[float], dict | None]] = {}

    def add(self, ids, embeddings, metadatas=None):
        """批量添加向量: ids 和 embeddings 一一对应, metadatas 可选; 同 id 覆盖。"""
        metas = metadatas if metadatas is not None else [None] * len(ids)
        for i, emb, meta in zip(ids, embeddings, metas):
            self._data[i] = (list(emb), meta)

    def upsert(self, ids, embeddings, metadatas=None):
        """语义同 add (内存版本就是 dict 赋值覆盖)。"""
        self.add(ids, embeddings, metadatas)

    def update_metadata(self, ids, metadatas):
        """只更新元数据, 保留已有向量 (纯元数据漂移免重 embed)。

        不存在的 id 忽略 (与 delete 语义对称)。
        """
        for i, meta in zip(ids, metadatas):
            if i in self._data:
                emb, _ = self._data[i]
                self._data[i] = (emb, dict(meta))

    def delete(self, ids):
        """删除指定 id 集合; 不存在的 id 忽略。"""
        for i in ids:
            self._data.pop(i, None)

    def all_entries(self):
        """返回 id -> metadata 映射 (不含 embedding), 供增量判重。"""
        return {i: (meta or {}) for i, (_, meta) in self._data.items()}

    def query(self, embedding, top_k, where=None):
        """按余弦相似度检索 top_k 条; where 可选元数据等值过滤。

        返回匹配记录的 id 列表 (按相似度降序)。
        """
        # 先按 where 条件剪枝, 再对剩余做向量相似度排序
        pool = [(i, emb, meta) for i, (emb, meta) in self._data.items()
                if _matches_where(meta, where)]
        scored = sorted(pool, key=lambda it: _cosine(embedding, it[1]),
                        reverse=True)
        return [i for i, _, _ in scored[:top_k]]


# ═══════════════════════════════════════════════════════════════════════════
#  Chroma 嵌入式实现 (生产)
# ═══════════════════════════════════════════════════════════════════════════

class ChromaVectorStore:
    """生产级向量库: Chroma 嵌入式 (持久化到本地文件)。

    懒导入 chromadb, 不装 chromadb 时该类的导入不会报错。
    适合大规模题库, 内部使用 HNSW 索引, 无需全量遍历。
    """

    def __init__(self, path: str, collection_name: str = "questions"):
        """打开或创建本地 Chroma 数据库。path 为持久化目录。"""
        import chromadb
        self._client = chromadb.PersistentClient(path=path)
        self._col = self._client.get_or_create_collection(collection_name)

    def add(self, ids, embeddings, metadatas=None):
        """批量添加向量; metadatas 中每个 dict 的 key 可用于后续 where 过滤。"""
        self._col.add(ids=list(ids), embeddings=[list(e) for e in embeddings],
                      metadatas=metadatas)

    def query(self, embedding, top_k, where=None):
        """按向量相似度检索; where 传给 Chroma 做元数据过滤。

        Chroma 自动处理距离计算和索引搜索, 比 InMemory 暴力排序快。
        扁平多字段等值过滤 (如 role+topic) 需转成 Chroma 的 $and 语法,
        否则 Chroma 报 "Expected where to have exactly one operator"。
        """
        kw = {"query_embeddings": [list(embedding)], "n_results": top_k}
        chroma_where = _chroma_where(where)
        if chroma_where:
            kw["where"] = chroma_where
        res = self._col.query(**kw)
        return list(res["ids"][0])

    def upsert(self, ids, embeddings, metadatas=None):
        """存在则覆盖, 否则新增 (Chroma upsert)。

        注意: Chroma upsert 必须携带向量, 向量库协议也要求 embeddings 必传;
        纯元数据变更请用 update_metadata, 不必为刷元数据重算 embedding。
        """
        if not ids:
            return
        self._col.upsert(ids=list(ids), embeddings=[list(e) for e in embeddings],
                         metadatas=metadatas)

    def update_metadata(self, ids, metadatas):
        """转调 Chroma collection.update 只刷元数据, 不碰向量。"""
        if not ids:
            return
        self._col.update(ids=list(ids), metadatas=metadatas)

    def delete(self, ids):
        """从集合删除指定 id。"""
        if not ids:
            return
        self._col.delete(ids=list(ids))

    def all_entries(self):
        """返回 id -> metadata 映射, 供增量判重。"""
        res = self._col.get(include=["metadatas"])
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        return {i: (m or {}) for i, m in zip(ids, metas)}
