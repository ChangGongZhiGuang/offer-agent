"""五层压缩管道。pinned 为前缀索引集, 压缩层只动其后的尾部。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from interviewforge.context.tokens import estimate_messages_tokens, estimate_tokens
from interviewforge.types import Message, Role

_ELIDED = "\n[... elided ...]\n"
_DISCARDED = "[tool result discarded]"


@dataclass
class ContextState:
    messages: list[Message]
    pinned: set[int] = field(default_factory=set)  # 前缀索引集: {0..k-1}
    token_budget: int = 24000
    current_tokens: int = 0

    def recompute_tokens(self) -> int:
        self.current_tokens = estimate_messages_tokens(self.messages)
        return self.current_tokens


@dataclass
class CompactionResult:
    layer_name: str
    tokens_before: int
    tokens_after: int
    messages_affected: int
    summary_text: str | None = None


class CompactionLayer(ABC):
    name: str
    cost: int

    @abstractmethod
    def should_trigger(self, ctx: ContextState) -> bool: ...

    @abstractmethod
    def apply(self, ctx: ContextState) -> CompactionResult: ...


def _first_compactable_index(ctx: ContextState) -> int:
    """pinned 是前缀集, 第一个可压缩索引 = max(pinned)+1。"""
    return (max(ctx.pinned) + 1) if ctx.pinned else 0


def _truncate(text: str, cap: int) -> str:
    """保头尾, 中间替占位符。cap 作字符预算近似。"""
    head = text[:cap]
    tail = text[-cap:]
    return head + _ELIDED + tail


class BudgetReductionLayer(CompactionLayer):
    """L1: 截断溢出 single_output_cap 的单个 TOOL 输出。不调模型。"""
    name = "L1_budget"
    cost = 1

    def __init__(self, single_output_cap: int):
        self.cap = single_output_cap

    def _oversized(self, m: Message) -> bool:
        return m.role == Role.TOOL and estimate_tokens(m.content) > self.cap

    def should_trigger(self, ctx: ContextState) -> bool:
        start = _first_compactable_index(ctx)
        return any(self._oversized(m) for m in ctx.messages[start:])

    def apply(self, ctx: ContextState) -> CompactionResult:
        before = ctx.recompute_tokens()
        start = _first_compactable_index(ctx)
        affected = 0
        for i in range(start, len(ctx.messages)):
            m = ctx.messages[i]
            if self._oversized(m):
                ctx.messages[i] = Message(role=Role.TOOL, content=_truncate(m.content, self.cap))
                affected += 1
        after = ctx.recompute_tokens()
        return CompactionResult(self.name, before, after, affected)


class SnipLayer(CompactionLayer):
    """L2: 历史过长时把早期 TOOL 往返删成占位符。不调模型。"""
    name = "L2_snip"
    cost = 2

    def __init__(self, snip_after_turns: int, keep_recent_tools: int = 1):
        self.threshold = snip_after_turns
        self.keep = keep_recent_tools

    def should_trigger(self, ctx: ContextState) -> bool:
        start = _first_compactable_index(ctx)
        return (len(ctx.messages) - start) > self.threshold

    def apply(self, ctx: ContextState) -> CompactionResult:
        before = ctx.recompute_tokens()
        start = _first_compactable_index(ctx)
        tool_idx = [i for i in range(start, len(ctx.messages)) if ctx.messages[i].role == Role.TOOL]
        to_snip = tool_idx[: -self.keep] if self.keep > 0 else tool_idx
        affected = 0
        for i in to_snip:
            if ctx.messages[i].content != _DISCARDED:
                ctx.messages[i] = Message(role=Role.TOOL, content=_DISCARDED)
                affected += 1
        after = ctx.recompute_tokens()
        return CompactionResult(self.name, before, after, affected)


class MicrocompactLayer(CompactionLayer):
    """L3: 滑窗合并相邻同角色短消息, 稳定缓存前缀。降的是消息条数而非 token。"""
    name = "L3_micro"
    cost = 2

    def __init__(self, small_token_threshold: int = 20):
        self.small = small_token_threshold

    def _is_short(self, m: Message) -> bool:
        return estimate_tokens(m.content) <= self.small

    def should_trigger(self, ctx: ContextState) -> bool:
        start = _first_compactable_index(ctx)
        region = ctx.messages[start:]
        return any(
            a.role == b.role and self._is_short(a) and self._is_short(b)
            for a, b in zip(region, region[1:])
        )

    def apply(self, ctx: ContextState) -> CompactionResult:
        before = ctx.recompute_tokens()
        start = _first_compactable_index(ctx)
        head = ctx.messages[:start]
        merged: list[Message] = []
        affected = 0
        for m in ctx.messages[start:]:
            if (merged and merged[-1].role == m.role
                    and self._is_short(merged[-1]) and self._is_short(m)):
                prev = merged.pop()
                merged.append(Message(role=m.role, content=prev.content + "\n" + m.content))
                affected += 1
            else:
                merged.append(m)
        ctx.messages = head + merged
        after = ctx.recompute_tokens()
        return CompactionResult(self.name, before, after, affected)


def _extract_summary(messages: list[Message]) -> str:
    """抽取式摘要: 紧凑概述折叠区 (Phase 2 用消息前缀; 后续可接结构化题/分/弱点)。"""
    heads = "; ".join(m.content[:20] for m in messages[:5])
    return f"[折叠 {len(messages)} 条历史] {heads}"


class ContextCollapseLayer(CompactionLayer):
    """L4: 超长历史抽取式折叠 + 触发记忆 consolidation 钩子。"""
    name = "L4_collapse"
    cost = 3

    def __init__(self, collapse_ratio: float = 0.85, keep_recent: int = 2, consolidation_hook=None):
        self.ratio = collapse_ratio
        self.keep_recent = keep_recent
        self.hook = consolidation_hook  # Callable[[], None] | None

    def should_trigger(self, ctx: ContextState) -> bool:
        return ctx.recompute_tokens() > ctx.token_budget * self.ratio

    def apply(self, ctx: ContextState) -> CompactionResult:
        before = ctx.recompute_tokens()
        start = _first_compactable_index(ctx)
        region = ctx.messages[start:]
        if len(region) <= self.keep_recent:
            return CompactionResult(self.name, before, before, 0)
        collapse = region[: -self.keep_recent] if self.keep_recent > 0 else region
        recent = region[-self.keep_recent:] if self.keep_recent > 0 else []
        summary = _extract_summary(collapse)
        ctx.messages = ctx.messages[:start] + [Message(role=Role.SYSTEM, content=summary)] + recent
        if self.hook is not None:
            self.hook()
        after = ctx.recompute_tokens()
        return CompactionResult(self.name, before, after, len(collapse), summary_text=summary)


class AutoCompactLayer(CompactionLayer):
    """L5: 兜底。前四层仍超 budget 时, fork 子上下文调模型语义摘要, 只留画像+进行中。"""
    name = "L5_auto"
    cost = 4

    def __init__(self, summarizer, keep_recent: int = 1):
        self.summarizer = summarizer  # Callable[[list[Message]], str]
        self.keep_recent = keep_recent

    def should_trigger(self, ctx: ContextState) -> bool:
        return ctx.recompute_tokens() > ctx.token_budget

    def apply(self, ctx: ContextState) -> CompactionResult:
        before = ctx.recompute_tokens()
        start = _first_compactable_index(ctx)
        region = ctx.messages[start:]
        if not region:
            return CompactionResult(self.name, before, before, 0)
        keep = region[-self.keep_recent:] if self.keep_recent > 0 else []
        to_summarize = region[: -self.keep_recent] if self.keep_recent > 0 else region
        summary = self.summarizer(to_summarize)
        ctx.messages = ctx.messages[:start] + [Message(role=Role.SYSTEM, content=summary)] + keep
        after = ctx.recompute_tokens()
        return CompactionResult(self.name, before, after, len(to_summarize), summary_text=summary)


class CompactionPipeline:
    """有序级联: 按 cost 升序, 逐层触发即应用, 跑完重估。便宜先跑。"""

    def __init__(self, layers: list[CompactionLayer]):
        self.layers = sorted(layers, key=lambda layer: layer.cost)

    def run(self, ctx: ContextState) -> list[CompactionResult]:
        ctx.recompute_tokens()
        results: list[CompactionResult] = []
        for layer in self.layers:
            if layer.should_trigger(ctx):
                results.append(layer.apply(ctx))
                ctx.recompute_tokens()
        return results


def make_model_summarizer(model_client):
    """L5 兜底摘要器: fork 一段 prompt 调模型做语义摘要; 模型不可用时退化为抽取式。"""
    def _summarize(messages: list[Message]) -> str:
        convo = "\n".join(f"{m.role.value}: {m.content}" for m in messages)
        prompt = ("把以下面试对话历史压缩成一段不超过 200 字的要点摘要, "
                  "保留已考察的知识点、候选人表现与暴露的弱点:\n" + convo)
        try:
            return model_client.chat([
                Message(role=Role.SYSTEM, content="你是上下文压缩器, 只输出摘要正文。"),
                Message(role=Role.USER, content=prompt),
            ])
        except Exception:  # noqa: BLE001 - 模型故障不应阻断压缩, 退化为抽取式
            return _extract_summary(messages)
    return _summarize


def build_pipeline(*, model_client=None, token_budget: int = 24000,
                   consolidation_hook=None) -> CompactionPipeline:
    """装配生产用五层压缩管道。model_client=None 时 L5 退化为抽取式摘要。"""
    summarizer = (make_model_summarizer(model_client) if model_client is not None
                  else _extract_summary)
    single_output_cap = max(256, token_budget // 8)
    return CompactionPipeline([
        BudgetReductionLayer(single_output_cap=single_output_cap),       # L1
        SnipLayer(snip_after_turns=50, keep_recent_tools=1),             # L2
        MicrocompactLayer(small_token_threshold=20),                     # L3
        ContextCollapseLayer(collapse_ratio=0.85, keep_recent=2,
                             consolidation_hook=consolidation_hook),     # L4
        AutoCompactLayer(summarizer=summarizer, keep_recent=1),          # L5
    ])
