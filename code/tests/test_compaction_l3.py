from interviewforge.context.compaction import MicrocompactLayer, ContextState
from interviewforge.types import Message, Role


def _msgs(*pairs):
    return [Message(role=r, content=c) for r, c in pairs]


def test_l3_triggers_on_adjacent_same_role_short():
    ctx = ContextState(messages=_msgs((Role.TOOL, "a"), (Role.TOOL, "b")))
    assert MicrocompactLayer(small_token_threshold=20).should_trigger(ctx) is True


def test_l3_no_trigger_on_different_roles():
    ctx = ContextState(messages=_msgs((Role.USER, "a"), (Role.TOOL, "b")))
    assert MicrocompactLayer(small_token_threshold=20).should_trigger(ctx) is False


def test_l3_merges_adjacent_short_same_role():
    ctx = ContextState(messages=_msgs(
        (Role.USER, "q"), (Role.TOOL, "a"), (Role.TOOL, "b"), (Role.TOOL, "c"),
    ))
    result = MicrocompactLayer(small_token_threshold=20).apply(ctx)
    roles = [m.role for m in ctx.messages]
    assert roles == [Role.USER, Role.TOOL]
    assert ctx.messages[1].content == "a\nb\nc"
    assert result.messages_affected == 2


def test_l3_does_not_merge_across_pinned():
    ctx = ContextState(messages=_msgs((Role.TOOL, "pinned"), (Role.TOOL, "a"), (Role.TOOL, "b")),
                       pinned={0})
    MicrocompactLayer(small_token_threshold=20).apply(ctx)
    assert ctx.messages[0].content == "pinned"
    assert ctx.messages[1].content == "a\nb"
