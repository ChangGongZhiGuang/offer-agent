"""Context Assembler: 多来源按段位 [0]-[6] 固定顺序组装, 稳定在前 (缓存纪律)。"""
from __future__ import annotations

from dataclasses import dataclass, field

from interviewforge.context.tokens import estimate_tokens
from interviewforge.memory.base import MemoryService
from interviewforge.memory.types import MemoryItem, MemoryKind, RecallQuery
from interviewforge.types import Message


@dataclass
class Segment:
    index: int       # 段位 0-6
    name: str
    content: str
    pinned: bool      # 是否禁止压缩 (系统人设/规则)
    stable: bool      # 是否属稳定前缀 (用于 cache_prefix_len)

    def tokens(self) -> int:
        return estimate_tokens(self.content)


@dataclass
class AssembledContext:
    segments: list[Segment]
    total_tokens: int
    cache_prefix_len: int


@dataclass
class SessionView:
    system_prompt: str
    tool_defs: str
    role: str | None = None
    topic: str | None = None
    compact_summary: str | None = None
    recent_messages: list[Message] = field(default_factory=list)
    tool_outputs: list[Message] = field(default_factory=list)


def _render_msgs(msgs: list[Message]) -> str:
    return "\n".join(f"{m.role.value}: {m.content}" for m in msgs)


def _render_rules(items: list[MemoryItem]) -> str:
    return "\n".join(f"- {it.content.get('id')}: {it.content.get('desc')}" for it in items)


def _render_profile(items: list[MemoryItem]) -> str:
    return "\n".join(f"- {it.content.get('fact', it.content)}" for it in items)


class ContextAssembler:
    def __init__(self, token_budget: int, *, lazy_tools: bool = False,
                 compaction_ratio: float = 0.85):
        self.token_budget = token_budget
        self.lazy_tools = lazy_tools
        self.compaction_ratio = compaction_ratio

    def assemble(self, session: SessionView, memory: MemoryService) -> AssembledContext:
        rules = memory.recall(RecallQuery(kinds=[MemoryKind.PROCEDURAL]))  # role=None: 全部规则
        # 画像是角色级事实 (非主题级), 只按 role 召回; topic 留给 episodic
        profile = memory.recall(RecallQuery(
            kinds=[MemoryKind.SEMANTIC], role=session.role, limit=10))

        segments = [
            Segment(0, "system", session.system_prompt, pinned=True, stable=True),
            Segment(1, "rules", _render_rules(rules), pinned=True, stable=True),
            Segment(2, "tools", "" if self.lazy_tools else session.tool_defs,
                    pinned=False, stable=True),
            Segment(3, "profile", _render_profile(profile), pinned=False, stable=False),
            Segment(4, "compact_summary", session.compact_summary or "",
                    pinned=False, stable=False),
            Segment(5, "working", _render_msgs(session.recent_messages),
                    pinned=False, stable=False),
            Segment(6, "execute", _render_msgs(session.tool_outputs),
                    pinned=False, stable=False),
        ]
        total = sum(s.tokens() for s in segments)
        return AssembledContext(segments, total, self._cache_prefix_len(segments))

    def _cache_prefix_len(self, segments: list[Segment]) -> int:
        total = 0
        for s in segments:
            if not s.stable:
                break
            total += s.tokens()
        return total

    def estimate_tokens(self, ctx: AssembledContext) -> int:
        return ctx.total_tokens

    def needs_compaction(self, ctx: AssembledContext) -> bool:
        return ctx.total_tokens > self.token_budget * self.compaction_ratio


def assemble_subagent_system(assembler: ContextAssembler, memory: MemoryService,
                             *, base_system: str, role: str | None) -> str:
    """用 ContextAssembler 把全局规则(procedural) + 候选人画像(semantic) 组进子 Agent
    的系统提示。这是 semantic/procedural 两类记忆在运行链路里的读取入口。

    只取 memory 派生的稳定段 (rules / profile); 工作窗口与执行轨迹由子 Agent 自带。
    """
    view = SessionView(system_prompt=base_system, tool_defs="", role=role)
    ctx = assembler.assemble(view, memory)
    by_name = {s.name: s.content for s in ctx.segments}
    parts = [base_system]
    if by_name.get("rules", "").strip():
        parts.append("【全局规则(必须遵守)】\n" + by_name["rules"])
    if by_name.get("profile", "").strip():
        parts.append("【候选人画像(来自记忆)】\n" + by_name["profile"])
    return "\n\n".join(parts)
