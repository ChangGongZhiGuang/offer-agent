"""MemoryService: 记忆即服务的门面, 协调四种记忆子系统的唯一入口。

这个文件实现了一种受认知科学启发的分层记忆架构:
  - Working      (工作记忆, 短期, 随 session 销毁)
  - Episodic     (情景记忆, 短期→中期, 按 salience 自动淘汰)
  - Semantic     (语义记忆, 长期, 持续累积)
  - Procedural   (程序记忆, 长期, 存储行为模式 / 策略偏好)

MemoryService 是上层代码接触记忆的唯一门面——不管读、写还是
跨层提升 (consolidate), 都经过这里分发到对应的子系统。
"""
from __future__ import annotations

import dataclasses
import time
from typing import Callable

from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import SemanticMemory
from interviewforge.memory.types import (
    ConsolidateTrigger,
    MemoryItem,
    MemoryKind,
    RecallQuery,
    effective_salience,
)
from interviewforge.memory.working import WorkingMemory


def _with_kind(item: MemoryItem, kind: MemoryKind) -> MemoryItem:
    """复制一条记忆, 仅改变其 kind 字段, 其余字段 (content / salience / time 等) 保持不变。

    用于记忆提升 (consolidation): 将一条工作记忆升级为情景记忆,
    或将情景记忆升级为语义记忆时, 保留内容本体, 只改类别标记。
    """
    return dataclasses.replace(item, kind=kind)


class MemoryService:
    """门面: 统一管理四种记忆子系统的读、写、跨层提升。

    调用方不需要关心记忆具体存在哪个子系统——按业务意图调用
    recall / remember / consolidate 即可。
    """

    def __init__(
        self,
        *,
        working: WorkingMemory,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        procedural: ProceduralMemory,
        salience_floor: float = 0.1,
        now_fn: Callable[[], float] = time.time,
    ):
        """注入四种记忆子系统实例。

        Args:
            working:       工作记忆 (session 级, 短时)
            episodic:      情景记忆 (session 间, 按重要性衰减)
            semantic:      语义记忆 (跨 session 累积的知识)
            procedural:    程序记忆 (策略 / 行为模式, 暂未实现)
            salience_floor:提升到语义记忆的最低 salience 阈值,
                           低于此的 E 级记忆在 consolidate 时被丢弃
            now_fn:        获取当前时间戳, 可注入 mock 用于测试
        """
        self.working = working
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.salience_floor = salience_floor
        self._now = now_fn

    # ---- 读: 多源召回 + salience 排序 + 截断 ----

    def recall(self, query: RecallQuery) -> list[MemoryItem]:
        """根据查询条件从多个记忆子系统召回, 按 salience 降序返回。

        流程:
          1. 按 query.kinds 逐一查对应的子系统
          2. 合并候选列表
          3. 按 effective_salience (salience × 时间衰减) 降序排列
          4. 仅返回 query.limit 条

        语义: 不管记忆存在哪个层级, 召回时总是先捞最"有用"的那些。
        """
        now = self._now()
        candidates: list[MemoryItem] = []

        # 按查询指定的记忆种类分别从各子系统收集
        for kind in query.kinds:
            if kind == MemoryKind.EPISODIC:
                candidates.extend(self.episodic.recall(query, now=now))
            elif kind == MemoryKind.WORKING:
                candidates.extend(self.working.recall(query))
            elif kind == MemoryKind.SEMANTIC:
                candidates.extend(self.semantic.recall(query))
            elif kind == MemoryKind.PROCEDURAL:
                candidates.extend(self.procedural.recall(query))

        # 按综合显著性倒排, 最相关的记忆排最前
        candidates.sort(key=lambda it: effective_salience(it, now), reverse=True)
        # 只取上限, 防止单次 recall 膨胀上下文
        return candidates[: query.limit]

    # ---- 写: 按 kind 路由到对应子系统 ----

    def remember(self, item: MemoryItem) -> None:
        """存入一条记忆, 根据 item.kind 自动路由到正确的子系统。

        调用方只需说"记住这件事", 不需要知道具体存在哪。
        当前 procedural 存储尚未实现, 会抛 NotImplementedError。
        """
        if item.kind == MemoryKind.WORKING:
            self.working.add(item)
        elif item.kind == MemoryKind.EPISODIC:
            self.episodic.add(item)
        elif item.kind == MemoryKind.SEMANTIC:
            self.semantic.add(item)
        elif item.kind == MemoryKind.PROCEDURAL:
            self.procedural.add(item)  # 抛 NotImplementedError

    # ---- 编排: 跨层记忆提升 (Consolidation) ----

    def consolidate(self, trigger: ConsolidateTrigger) -> None:
        """根据触发类型执行一次记忆跨层提升。

        类比人类的睡眠 / 复习机制: 短期记忆不断向长期沉淀。
        有三种触发:

        WORKING → EPISODIC (短期→中期):
           将工作记忆全部复制进情景记忆, 然后清空工作记忆。
           时机: 一道题作答完毕、一个 session 结束时。

        EPISODIC → SEMANTIC (中期→长期):
           将 salience 高于阈值的 E 级记忆提升为 S 级,
           并淘汰低 salience 的 E 级记忆 (prune)。
           时机: session 结束 / 定时触发。

        SEMANTIC → PERSIST (长期→持久化):
           MySQL 后端在写入时即已落库, 无需额外操作。
           纯内存后端在此处可接入序列化逻辑。
        """
        if trigger == ConsolidateTrigger.WORKING_TO_EPISODIC:
            # 把工作记忆的全部内容搬进情景记忆 (保留内容, 改 kind)
            for it in self.working.all():
                self.episodic.add(_with_kind(it, MemoryKind.EPISODIC))
            # 搬完后清空工作记忆, 为下一轮腾出空间
            self.working.clear()

        elif trigger == ConsolidateTrigger.EPISODIC_TO_SEMANTIC:
            # 只保留"足够重要"的 E 级记忆, 提升为 S 级
            now = self._now()
            for it in self.episodic.all():
                if effective_salience(it, now) >= self.salience_floor:
                    self.semantic.add(_with_kind(it, MemoryKind.SEMANTIC))
            # 低于阈值的 E 级记忆被 prune 掉, 避免无限膨胀
            self.episodic.prune(self.salience_floor, now)

        elif trigger == ConsolidateTrigger.SEMANTIC_TO_PERSIST:
            # MySQL backend 已落库即固化, 无额外操作
            pass
