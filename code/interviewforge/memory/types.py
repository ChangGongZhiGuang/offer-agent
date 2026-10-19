"""记忆系统的数据类型与纯函数 (排序/过滤)。

这个文件只定义数据结构和纯函数, 不涉及任何 IO 操作。
所有记忆子系统 (working / episodic / semantic / procedural)
共享这些类型定义, 确保数据格式统一。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class MemoryKind(str, Enum):
    """记忆的四种类别, 对应四层记忆架构。"""
    WORKING = "working"        # 工作记忆: 短期, session 级, 随会话结束清空
    EPISODIC = "episodic"      # 情景记忆: 中期, 按显著性衰减, 自动淘汰
    SEMANTIC = "semantic"      # 语义记忆: 长期, 跨 session 累积, 持续保留
    PROCEDURAL = "procedural"  # 程序记忆: 长期, 存行为模式 / 策略偏好 (暂未实现)


@dataclass
class MemoryItem:
    """一条完整的记忆单元。

    role / topic 等检索维度不单独拆字段, 而是统一放在 content dict 里。
    这样设计让 content 结构可以灵活扩展——不同的记忆来源 (面试回答、
    面试官反馈、系统事件) 可以携带不同的键, 而不需要改动 MemoryItem 本身。
    """
    kind: MemoryKind            # 所属记忆层级 (working / episodic / ...)
    content: dict               # 记忆内容, 语义由写入方定义 (如 {"role": "后端", "topic": "缓存", "summary": "..."})
    salience: float = 1.0       # 固有显著性权重 (0~1), 越高越不容易被遗忘
    id: str = field(default_factory=lambda: uuid.uuid4().hex)   # 唯一标识, 自动生成
    created_at: float = field(default_factory=time.time)        # 创建时间戳, 用于衰减计算

    def __post_init__(self):
        """确保 kind 是 MemoryKind 枚举值 (允许构造时传字符串, 自动转换)。"""
        self.kind = MemoryKind(self.kind)

    def to_dict(self) -> dict:
        """序列化为 dict, 用于 JSON 序列化 / 数据库存储。"""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "content": self.content,
            "salience": self.salience,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryItem":
        """从 dict 反序列化, 与 to_dict 对称。"""
        return cls(
            kind=MemoryKind(d["kind"]),
            content=d["content"],
            salience=d["salience"],
            id=d["id"],
            created_at=d["created_at"],
        )


@dataclass
class RecallQuery:
    """记忆召回查询条件 —— 查什么、从哪查、查几条。"""
    kinds: list[MemoryKind]        # 在哪些记忆层级中查找 (如 [WORKING, EPISODIC])
    role: str | None = None        # 按岗位筛选 (如 "后端工程师"), None 表示不限
    topic: str | None = None       # 按主题筛选 (如 "缓存"), None 表示不限
    limit: int = 5                 # 最多返回条数, 防止上下文膨胀


class ConsolidateTrigger(str, Enum):
    """记忆跨层提升 (consolidation) 的触发时机。

    类比人类的睡眠 / 复习机制——短期记忆逐渐沉淀为长期记忆。
    """
    WORKING_TO_EPISODIC = "working_to_episodic"   # 工作记忆 → 情景记忆: 题目作答完毕 / session 结束
    EPISODIC_TO_SEMANTIC = "episodic_to_semantic" # 情景记忆 → 语义记忆: session 结束 / 定时触发
    SEMANTIC_TO_PERSIST = "semantic_to_persist"   # 语义记忆 → 持久化: MySQL 实时落库, 无需额外触发


def effective_salience(item: MemoryItem, now: float, half_life_seconds: float = 3600.0) -> float:
    """计算记忆的当前有效显著性: salience × 时间衰减。

    衰减模型: 每过一个半衰期 (默认 1 小时), 显著性减半。
    这是指数衰减——越老的记忆权重越低, 但永远不会归零。

    公式: effective = salience * 0.5 ^ (age / half_life)

    Args:
        item:             待计算的记忆
        now:              当前时间戳, 用于计算已存在时长
        half_life_seconds:半衰期 (秒), 默认 3600 秒 = 1 小时

    Returns:
        0 ~ salience 之间的衰减后值
    """
    age = max(0.0, now - item.created_at)  # 记忆已存在时长, 防止时钟回跳
    decay = 0.5 ** (age / half_life_seconds)
    return item.salience * decay


def matches_filter(item: MemoryItem, role: str | None = None, topic: str | None = None) -> bool:
    """检查一条记忆是否与给定的 role / topic 过滤条件匹配。

    用于各子系统的 recall 实现中对候选记忆做预过滤。
    条件为 None 表示不限制 (不检查该字段)。

    Args:
        item:  待检查的记忆
        role:  岗位名, None 表示跳过此过滤
        topic: 主题名, None 表示跳过此过滤

    Returns:
        全部非 None 条件都匹配时返回 True
    """
    if role is not None and item.content.get("role") != role:
        return False
    if topic is not None and item.content.get("topic") != topic:
        return False
    return True
