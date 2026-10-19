from interviewforge.context.compaction import ContextCollapseLayer, ContextState
from interviewforge.types import Message, Role


def _big(n):
    return [Message(role=Role.ASSISTANT, content="x" * 400) for _ in range(n)]


def test_l4_triggers_over_ratio():
    ctx = ContextState(messages=_big(10), token_budget=200)
    layer = ContextCollapseLayer(collapse_ratio=0.85)
    assert layer.should_trigger(ctx) is True


def test_l4_no_trigger_under_ratio():
    ctx = ContextState(messages=_big(1), token_budget=10000)
    layer = ContextCollapseLayer(collapse_ratio=0.85)
    assert layer.should_trigger(ctx) is False


def test_l4_collapses_and_fires_hook_and_keeps_recent():
    calls = []
    ctx = ContextState(messages=_big(6), token_budget=200)
    layer = ContextCollapseLayer(collapse_ratio=0.85, keep_recent=2,
                                 consolidation_hook=lambda: calls.append(1))
    result = layer.apply(ctx)
    assert len(ctx.messages) == 3
    assert result.summary_text is not None
    assert result.tokens_after < result.tokens_before
    assert result.messages_affected == 4
    assert calls == [1]


def test_l4_preserves_pinned_prefix():
    msgs = [Message(role=Role.SYSTEM, content="PINNED")] + _big(5)
    ctx = ContextState(messages=msgs, token_budget=200, pinned={0})
    layer = ContextCollapseLayer(collapse_ratio=0.85, keep_recent=1)
    layer.apply(ctx)
    assert ctx.messages[0].content == "PINNED"


def test_l4_hook_optional():
    ctx = ContextState(messages=_big(6), token_budget=200)
    layer = ContextCollapseLayer(collapse_ratio=0.85, keep_recent=2)
    result = layer.apply(ctx)
    assert result.summary_text is not None
