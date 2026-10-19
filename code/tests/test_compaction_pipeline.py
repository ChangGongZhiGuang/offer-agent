from interviewforge.context.compaction import (
    AutoCompactLayer,
    BudgetReductionLayer,
    CompactionPipeline,
    ContextCollapseLayer,
    ContextState,
    MicrocompactLayer,
    SnipLayer,
    build_pipeline,
    make_model_summarizer,
)
from interviewforge.types import Message, Role


def _full_pipeline(consolidation_hook=None):
    return CompactionPipeline([
        AutoCompactLayer(summarizer=lambda msgs: "AUTOSUMMARY", keep_recent=1),  # cost 4
        ContextCollapseLayer(collapse_ratio=0.85, keep_recent=2,
                             consolidation_hook=consolidation_hook),             # cost 3
        BudgetReductionLayer(single_output_cap=100),                            # cost 1
        SnipLayer(snip_after_turns=50, keep_recent_tools=1),                    # cost 2
        MicrocompactLayer(small_token_threshold=20),                           # cost 2
    ])


def test_pipeline_orders_by_cost():
    pipe = _full_pipeline()
    assert [l.cost for l in pipe.layers] == [1, 2, 2, 3, 4]


def test_pipeline_runs_only_triggered_layers():
    ctx = ContextState(messages=[Message(role=Role.TOOL, content="x" * 4000)],
                       token_budget=100000)
    results = _full_pipeline().run(ctx)
    assert [r.layer_name for r in results] == ["L1_budget"]


def test_pipeline_brings_over_budget_down_and_fires_hook():
    calls = []
    msgs = [Message(role=Role.SYSTEM, content="PINNED RULES")]
    msgs += [Message(role=Role.ASSISTANT, content="x" * 400) for _ in range(20)]
    ctx = ContextState(messages=msgs, token_budget=300, pinned={0})
    results = _full_pipeline(consolidation_hook=lambda: calls.append(1)).run(ctx)
    assert ctx.recompute_tokens() <= ctx.token_budget
    assert ctx.messages[0].content == "PINNED RULES"
    assert calls == [1]
    assert any(r.layer_name == "L4_collapse" for r in results)


def test_pipeline_noop_when_small():
    ctx = ContextState(messages=[Message(role=Role.USER, content="hi")], token_budget=100000)
    assert _full_pipeline().run(ctx) == []


class _FakeModel:
    def __init__(self, reply="MODEL SUMMARY"): self.reply = reply
    def chat(self, messages): return self.reply


def test_build_pipeline_orders_layers_by_cost():
    pipe = build_pipeline(model_client=_FakeModel(), token_budget=24000)
    assert [l.cost for l in pipe.layers] == [1, 2, 2, 3, 4]


def test_build_pipeline_brings_over_budget_down():
    msgs = [Message(role=Role.SYSTEM, content="PINNED")]
    msgs += [Message(role=Role.ASSISTANT, content="x" * 400) for _ in range(20)]
    ctx = ContextState(messages=msgs, token_budget=300, pinned={0})
    build_pipeline(model_client=_FakeModel(), token_budget=300).run(ctx)
    assert ctx.recompute_tokens() <= ctx.token_budget
    assert ctx.messages[0].content == "PINNED"


def test_model_summarizer_falls_back_when_model_raises():
    class _Boom:
        def chat(self, messages): raise RuntimeError("401")
    summ = make_model_summarizer(_Boom())
    out = summ([Message(role=Role.ASSISTANT, content="abc")])
    assert isinstance(out, str) and out  # 退化为抽取式摘要, 不抛异常


def test_model_summarizer_uses_model_reply():
    summ = make_model_summarizer(_FakeModel("SEMANTIC SUMMARY"))
    assert summ([Message(role=Role.USER, content="hi")]) == "SEMANTIC SUMMARY"
