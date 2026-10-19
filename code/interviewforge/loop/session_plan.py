"""SessionPlan: 面试开场时确定性规划整场题序。

在面试一开始就确定好整场面试的提问计划——每道题的主题 (topic)、
考核维度 (dimension)、难度阶梯 (difficulty)。纯函数设计, 不依赖
任何外部状态, 方便测试和结果断言。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from interviewforge.resume.types import CandidateProfile

# 难度阶梯: 按题号均匀分配, 前 1/3 easy, 中间 1/3 medium, 后 1/3 hard
# 给候选人逐步加压的自然节奏, 开场不会因太难而冷场
_DIFF_RAMP = ["easy", "medium", "hard"]


@dataclass
class PlanItem:
    """单道面试题的规划信息。"""
    topic: str                    # 考察主题 (如 "分布式系统"、"排序算法")
    dimension: str | None = None  # 考核维度 (如 "深度"、"广度"), None 表示不区分
    difficulty: str = "medium"    # 难度级别: "easy" | "medium" | "hard"


@dataclass
class SessionPlan:
    """整场面试的完整提问计划。"""
    items: list[PlanItem] = field(default_factory=list)


def _ramped_difficulty(index: int, total: int) -> str:
    """根据题号 index (0-based) 和总题数 total 分配难度。

    将题号线性映射到 _DIFF_RAMP 下标区间, 实现:
      - 前 1/3 题目 → "easy"
      - 中 1/3 题目 → "medium"
      - 后 1/3 题目 → "hard"

    边界情况:
      - 只有 1 题 → 固定 "medium" (不冷不热)
      - total 很小 → 保证至少每档有一题 (clamp 到最后一档)
    """
    if total <= 1:
        return "medium"
    # bucket = floor(index / total * 3), 把 [0, total) 映射到 [0, 1, 2]
    bucket = min(len(_DIFF_RAMP) - 1, index * len(_DIFF_RAMP) // total)
    return _DIFF_RAMP[bucket]


def build_session_plan(profile: CandidateProfile, dimensions: list[str],
                       num_questions: int, *, fallback_topic: str = "通用") -> SessionPlan:
    """构建整场面试的提问计划。

    1. 取候选人的简历主题 (topic_plan) 作为题库; 若简历无可提取的主题,
       则使用 fallback_topic (默认 "通用")。
    2. 按 num_questions 道题循环分配 topic 和 dimension:
       - topic:   按简历主题轮流 (i % len(topics))
       - dimension:按传入维度轮流 (若有); 无维度时留 None
       - difficulty:按 _ramped_difficulty 走 easy→medium→hard 递增
    3. 返回一个 SessionPlan, 面试过程遍历 items 依次提问。

    设计原则: 确定性规划, 同一 profile + 参数永远产生相同题序,
    保证可复现和可测。后来者可在这一层做更精细的调度策略
    (如自适应难度、冷门主题加权) 而不影响下游。
    """
    # 简历主题为空时兜底, 确保至少有东西可以循环
    topics = list(profile.topic_plan) or [fallback_topic]

    items: list[PlanItem] = []
    for i in range(num_questions):
        # 循环分配: 主题和维度都按余数轮转, 保证均匀覆盖
        topic = topics[i % len(topics)]
        dimension = dimensions[i % len(dimensions)] if dimensions else None
        items.append(PlanItem(
            topic=topic,
            dimension=dimension,
            difficulty=_ramped_difficulty(i, num_questions),
        ))

    return SessionPlan(items=items)
