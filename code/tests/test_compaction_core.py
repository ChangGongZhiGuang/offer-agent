from interviewforge.context.compaction import (
    BudgetReductionLayer,
    CompactionLayer,
    CompactionResult,
    ContextState,
    SnipLayer,
)
from interviewforge.types import Message, Role


def _msgs(*pairs):
    return [Message(role=r, content=c) for r, c in pairs]


def test_context_state_recompute_tokens():
    ctx = ContextState(messages=_msgs((Role.USER, "abcd"), (Role.ASSISTANT, "分布式")))
    assert ctx.recompute_tokens() == 4
    assert ctx.current_tokens == 4


def test_compaction_layer_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        CompactionLayer()


def test_l1_triggers_on_oversized_tool_output():
    big = "x" * 4000
    ctx = ContextState(messages=_msgs((Role.TOOL, big)))
    layer = BudgetReductionLayer(single_output_cap=100)
    assert layer.should_trigger(ctx) is True


def test_l1_truncates_keeping_head_and_tail():
    big = "HEAD" + "x" * 4000 + "TAIL"
    ctx = ContextState(messages=_msgs((Role.TOOL, big)))
    layer = BudgetReductionLayer(single_output_cap=100)
    result = layer.apply(ctx)
    new_content = ctx.messages[0].content
    assert "[... elided ...]" in new_content
    assert new_content.startswith("HEAD")
    assert new_content.endswith("TAIL")
    assert result.tokens_after < result.tokens_before
    assert result.messages_affected == 1


def test_l1_ignores_non_tool_and_small_outputs():
    ctx = ContextState(messages=_msgs((Role.USER, "x" * 4000), (Role.TOOL, "small")))
    layer = BudgetReductionLayer(single_output_cap=100)
    assert layer.should_trigger(ctx) is False


def test_l1_does_not_touch_pinned():
    big = "x" * 4000
    ctx = ContextState(messages=_msgs((Role.TOOL, big), (Role.TOOL, big)), pinned={0})
    layer = BudgetReductionLayer(single_output_cap=100)
    layer.apply(ctx)
    assert ctx.messages[0].content == big
    assert "[... elided ...]" in ctx.messages[1].content


def test_l2_triggers_when_history_exceeds_threshold():
    ctx = ContextState(messages=_msgs(*[(Role.TOOL, "r")] * 5))
    layer = SnipLayer(snip_after_turns=3)
    assert layer.should_trigger(ctx) is True


def test_l2_snips_early_tools_keeping_recent():
    ctx = ContextState(messages=_msgs(
        (Role.TOOL, "old1"), (Role.USER, "q"), (Role.TOOL, "old2"), (Role.TOOL, "recent")
    ))
    layer = SnipLayer(snip_after_turns=1, keep_recent_tools=1)
    result = layer.apply(ctx)
    assert ctx.messages[0].content == "[tool result discarded]"
    assert ctx.messages[2].content == "[tool result discarded]"
    assert ctx.messages[3].content == "recent"
    assert ctx.messages[1].content == "q"
    assert result.messages_affected == 2
