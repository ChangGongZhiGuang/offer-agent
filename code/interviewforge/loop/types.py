"""PEV 状态机的纯数据类型。无 IO。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from typing import TYPE_CHECKING

from interviewforge.types import Message

if TYPE_CHECKING:
    from interviewforge.loop.session_plan import SessionPlan
    from interviewforge.resume.types import CandidateProfile


class Phase(str, Enum):
    IDLE = "idle"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    COMPACT = "compact"
    RESPOND = "respond"
    HALT = "halt"


class HaltReason(str, Enum):
    COMPLETED = "completed"      # 正常收尾
    MAX_TURNS = "max_turns"      # 触整场硬上限
    MAX_REPLANS = "max_replans"  # 单轮重规划死循环
    ERROR = "error"             # 致命错误


@dataclass
class Plan:
    intent: str                 # "ask" | "grade" | "finish"
    tool_calls: list[str]       # 本轮声明要调的工具
    expected_outcome: str = ""
    query: str | None = None    # A: 出题时给 SearchAdapter 用的检索 query (含维度/JD/简历)


@dataclass
class Bounds:
    max_turns: int = 30                 # 整场对话硬上限
    max_replans: int = 3                # 单轮重规划上限
    max_tool_calls_per_turn: int = 5    # 防单轮工具风暴
    max_questions: int = 3              # 本场计划出题数 (主题, 不含追问)
    # 追问边界: 追问不占主题额度, 但受每问深度与全场总量双重约束; 0 = 关闭追问
    max_follow_ups_per_question: int = 1   # 每道主题最多追问次数
    max_total_follow_ups: int = 0          # 全场追问总量上限 (0 = 自动取 max_questions)

    @classmethod
    def from_settings(cls, settings, *, max_questions: int = 3,
                      max_follow_ups_per_question: int = 1) -> "Bounds":
        return cls(
            max_turns=settings.max_turns,
            max_replans=settings.max_replans,
            max_tool_calls_per_turn=settings.max_tool_calls_per_turn,
            max_questions=max_questions,
            max_follow_ups_per_question=max_follow_ups_per_question,
        )

    def total_follow_up_cap(self) -> int:
        """全场追问总量: 显式配置优先, 0 时自动取主题数。"""
        return self.max_total_follow_ups or self.max_questions


@dataclass
class LoopState:
    role: str
    topic: str
    profile: str = ""                   # 候选人画像 (显式注入子 Agent)
    difficulty: str = "medium"
    # A: 检索 query 的两类语义抓手——JD 技能 + 本轮考察维度。intake 阶段产出。
    jd_keywords: list[str] = field(default_factory=list)
    dimension: str | None = None
    phase: Phase = Phase.IDLE
    turn: int = 0                       # 已出题轮数
    replan_count: int = 0               # 当前轮重规划计数
    asked_ids: list[str] = field(default_factory=list)   # 本场已问题 id (dedup)
    current_question: dict | None = None # 当前待答题的 structured
    last_error: str | None = None        # 最近一次门失败原因 (反馈给 PLAN)
    recent_messages: list[Message] = field(default_factory=list)  # 对话窗口 (供组装/压缩)
    halted: HaltReason | None = None
    session_plan: "SessionPlan | None" = None        # 开场规划的整场题序
    profile_struct: "CandidateProfile | None" = None  # 结构化简历画像
    # 逐题问答流水 (供历史回看): 每次作答成功后追加一条;
    # 追问回合额外带 is_follow_up/parent_question_id 标记
    # {question_id, question, answer, score, feedback, dimension, is_follow_up}
    qa_log: list[dict] = field(default_factory=list)
    # ── 追问链状态 ──
    # 待答追问的 structured (含 question/rubric/question_id/parent_question_id/depth);
    # 非空时下一次 submit_answer 走追问作答路径
    pending_follow_up: dict | None = None
    follow_up_counts: dict[str, int] = field(default_factory=dict)  # 主问 qid -> 已追问次数
    total_follow_ups: int = 0                                        # 全场已生成追问总数
