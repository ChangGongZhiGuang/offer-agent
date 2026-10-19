"""把 Phase 4 Retriever 适配成 search_questions 工具回调; 第⑤步按 episodic 去重。"""
from __future__ import annotations

from typing import Callable

from interviewforge.memory.base import MemoryService
from interviewforge.rag.retriever import Retriever


def collect_asked_ids(memory: MemoryService) -> list[str]:
    """从 episodic 记忆收集本场已问过的 question_id (检索去重的关键)。"""
    ids: list[str] = []
    for item in memory.episodic.all():
        qid = item.content.get("question_id")
        if qid is not None:
            ids.append(qid)
    return ids


class SearchAdapter:
    """search_questions(role, topic) 的 RAG 适配器。

    被 build_default_registry 当作 retriever 注入工具系统,
    以 retriever(role=..., topic=...) 关键字参数调用。
    内部流程: 构建查询 → 向量召回 → 去重 → 降级 → 缓存当轮结果供评分引用。

    职责:
      - 包装 Retriever, 屏蔽细节
      - 自动剔除已问题目 (避免一场面试出现重复题)
      - 缓存 last_id / last_reference_answer, 供状态机和 Grader 关联
      - 支持 Planner 注入一次性 query (如追问场景)
    """

    def __init__(self, retriever: Retriever, memory: MemoryService, *,
                 top_k: int = 5, build_query: Callable[[str, str], str] | None = None,
                 hard_filter_by_role: bool = True):
        self.retriever = retriever                              # 底层 RAG 检索器 (InMemory 或 MySQL)
        self.memory = memory                                    # 当前会话的记忆系统, 用于查已问题目
        self.top_k = top_k                                      # 向量召回候选数
        # 查询文本构造器: 默认 "role topic", 可自定义 (如追问时只用 topic)
        self.build_query = build_query or (lambda role, topic: f"{role} {topic}")
        # 是否在向量库阶段就按 role 元数据硬过滤 (减噪声)
        self.hard_filter_by_role = hard_filter_by_role
        # ── 当轮缓存 (被 __call__ 设置, 供状态机/Grader 读取) ────────
        self.last_id: str | None = None                         # 当轮命中的题目 ID
        self.last_question: str | None = None                   # 当轮命中的题目原文
        self.last_reference_answer: str | None = None           # 参考答案, 回流给 Grader 做评分依据
        self._next_query: str | None = None                     # Planner 注入的一次性 query (用完即清)

    def set_next_query(self, query: str | None) -> None:
        """由 Planner 在 PLAN 阶段注入; 用完即清, 防止后续轮误用旧 query。

        典型场景: 追问时注入具体问题文本取代默认 "role topic" 查询。
        """
        self._next_query = query or None

    def __call__(self, role: str, topic: str,
                 difficulty: str | None = None) -> list[dict]:
        """执行一次题目检索。

        流程: 收集已问 ID → 构造查询 → 硬过滤 → 向量检索 → 角色降级 → 返回

        返回: [{"question_id", "question", "difficulty"}]
              无结果时返回空列表并将 last_* 置空。
        """
        # 1) 从 episodic 记忆收集已问题目 ID, 传给底层去重
        asked = collect_asked_ids(self.memory)

        # 2) 确定查询文本: Planner 注入优先, 否则默认 "role topic"
        query_text = self._next_query or self.build_query(role, topic)
        self._next_query = None  # one-shot: 用完立即清除

        # 3) 向量检索: 可选按 role 硬过滤元数据
        where = {"role": role} if (self.hard_filter_by_role and role) else None
        q = self.retriever.retrieve_one(
            query_text, top_k=self.top_k, asked_ids=asked,
            target_difficulty=difficulty, where=where)

        # 4) 降级: 角色过滤后无结果 → 去掉 role 过滤再试一次
        #    避免角色名文字不匹配 (如"资深后端工程师"≠"后端") 导致空结果
        if q is None and where is not None:
            q = self.retriever.retrieve_one(
                query_text, top_k=self.top_k, asked_ids=asked,
                target_difficulty=difficulty, where=None)

        # 5) 缓存结果: 供 InterviewLoop 状态机和 Grader 引用
        if q is None:
            self.last_id = None
            self.last_question = None
            self.last_reference_answer = None
            return []
        self.last_id = q.id
        self.last_question = q.stem
        self.last_reference_answer = q.answer
        return [{"question_id": q.id, "question": q.stem,
                 "difficulty": q.difficulty}]
