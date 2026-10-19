from interviewforge.context.compaction import AutoCompactLayer, ContextState
from interviewforge.types import Message, Role


def _big(n):
    return [Message(role=Role.ASSISTANT, content="x" * 400) for _ in range(n)]


def test_l5_triggers_over_budget():
    ctx = ContextState(messages=_big(10), token_budget=200)
    layer = AutoCompactLayer(summarizer=lambda msgs: "S")
    assert layer.should_trigger(ctx) is True


def test_l5_no_trigger_under_budget():
    ctx = ContextState(messages=_big(1), token_budget=10000)
    layer = AutoCompactLayer(summarizer=lambda msgs: "S")
    assert layer.should_trigger(ctx) is False


def test_l5_collapses_to_summary_plus_recent():
    seen = {}
    def fake_summarizer(msgs):
        seen["n"] = len(msgs)
        return "SUMMARY"
    ctx = ContextState(messages=_big(5), token_budget=200)
    layer = AutoCompactLayer(summarizer=fake_summarizer, keep_recent=1)
    result = layer.apply(ctx)
    assert ctx.messages[0].content == "SUMMARY"
    assert len(ctx.messages) == 2
    assert seen["n"] == 4
    assert result.tokens_after < result.tokens_before
    assert result.summary_text == "SUMMARY"


def test_l5_preserves_pinned_prefix():
    msgs = [Message(role=Role.SYSTEM, content="PINNED")] + _big(5)
    ctx = ContextState(messages=msgs, token_budget=200, pinned={0})
    layer = AutoCompactLayer(summarizer=lambda m: "S", keep_recent=1)
    layer.apply(ctx)
    assert ctx.messages[0].content == "PINNED"
    assert ctx.messages[1].content == "S"
