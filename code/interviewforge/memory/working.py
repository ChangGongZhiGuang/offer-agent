"""Working memory: 当前会话内的活跃记忆窗口 (内存态, 易失)。

WorkingMemory 存储当前面试轮次内产生的临时信息:
LLM 调用间传递的上下文、当前正在处理的题目、对话历史快照等。
会话结束后即丢弃, 不持久化。
"""
from __future__ import annotations

from interviewforge.memory.types import MemoryItem, RecallQuery, matches_filter


class WorkingMemory:
    """环形/栈式工作记忆: 当前轮次内 LLM 可读写的活跃上下文。

    特性:
      - 内存态: 只存在当前进程中, 重启即失
      - 易失: 不会写入磁盘, 不像 EpisodicMemory 会追加到 jsonl 文件
      - 按 recall 过滤: 支持按 role/topic 筛选, 但通常全量返回

    与 EpisodicMemory 的区别:
      Episodic → 持久化, 跨轮次留存, 用于去重/回溯
      Working  → 内存态, 当前轮次可见, 用于上下文传递
    """

    def __init__(self):
        # 按添加顺序存储的 MemoryItem 列表, 尾部是最新
        self._items: list[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        """写入一条记忆项, 追加到工作窗口末尾。"""
        self._items.append(item)

    def all(self) -> list[MemoryItem]:
        """返回当前工作记忆的全部内容 (按添加顺序)。"""
        return list(self._items)

    def recall(self, query: RecallQuery) -> list[MemoryItem]:
        """按 role/topic 过滤后返回 (当前实现为全量返回, 保留过滤接口供扩展)。"""
        return [it for it in self._items if matches_filter(it, query.role, query.topic)]

    def clear(self) -> None:
        """清空工作记忆 (新轮次开始时调用, 避免上下文污染)。"""
        self._items.clear()
