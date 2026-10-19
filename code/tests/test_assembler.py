from interviewforge.context.assembler import (
    AssembledContext,
    ContextAssembler,
    Segment,
    SessionView,
)
from interviewforge.context.tokens import estimate_tokens
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.memory.working import WorkingMemory
from interviewforge.types import Message, Role


def _memory(tmp_path):
    svc = MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([{"id": "score_in_range", "desc": "1-5"}]),
    )
    svc.remember(MemoryItem(kind=MemoryKind.SEMANTIC,
                            content={"role": "后端", "fact": "擅长SQL"}, id="p1"))
    return svc


def _session():
    return SessionView(
        system_prompt="你是资深面试官",
        tool_defs="search_questions(role, topic)",
        role="后端",
        topic="redis",
        compact_summary="往期: 答对2题",
        recent_messages=[Message(role=Role.USER, content="我用过Redis")],
        tool_outputs=[Message(role=Role.TOOL, content="题库命中3条")],
    )


def test_assemble_produces_seven_ordered_segments(tmp_path):
    asm = ContextAssembler(token_budget=10000)
    ctx = asm.assemble(_session(), _memory(tmp_path))
    assert isinstance(ctx, AssembledContext)
    assert [s.index for s in ctx.segments] == [0, 1, 2, 3, 4, 5, 6]
    assert [s.name for s in ctx.segments] == [
        "system", "rules", "tools", "profile", "compact_summary", "working", "execute"
    ]


def test_segments_0_and_1_are_pinned(tmp_path):
    asm = ContextAssembler(token_budget=10000)
    ctx = asm.assemble(_session(), _memory(tmp_path))
    assert ctx.segments[0].pinned is True
    assert ctx.segments[1].pinned is True
    assert ctx.segments[3].pinned is False


def test_rules_and_profile_recalled(tmp_path):
    asm = ContextAssembler(token_budget=10000)
    ctx = asm.assemble(_session(), _memory(tmp_path))
    assert "score_in_range" in ctx.segments[1].content
    assert "擅长SQL" in ctx.segments[3].content


def test_cache_prefix_len_is_leading_stable_segments(tmp_path):
    session = _session()
    asm = ContextAssembler(token_budget=10000)
    ctx = asm.assemble(session, _memory(tmp_path))
    expected = ctx.segments[0].tokens() + ctx.segments[1].tokens() + ctx.segments[2].tokens()
    assert ctx.cache_prefix_len == expected


def test_lazy_tools_empties_segment_2(tmp_path):
    asm = ContextAssembler(token_budget=10000, lazy_tools=True)
    ctx = asm.assemble(_session(), _memory(tmp_path))
    assert ctx.segments[2].content == ""


def test_needs_compaction_threshold(tmp_path):
    asm = ContextAssembler(token_budget=10, compaction_ratio=0.85)
    ctx = asm.assemble(_session(), _memory(tmp_path))
    assert asm.needs_compaction(ctx) is True
    assert asm.estimate_tokens(ctx) == ctx.total_tokens
