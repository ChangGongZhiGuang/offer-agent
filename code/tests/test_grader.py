import pytest

from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.working import WorkingMemory
from interviewforge.subagents.base import SubTask, ToolPermissionError
from interviewforge.subagents.grader import Grader
from interviewforge.tools.interview_tools import build_default_registry


class _FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.seen = []

    def chat(self, messages):
        self.seen = messages
        return self.reply


_GRADER_JSON = '{"score": 4, "weakness_tags": ["边界条件"], "feedback": "整体不错, 注意边界。"}'


def _memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def test_grader_returns_structured():
    g = Grader(_FakeModel(_GRADER_JSON), tool_registry=None)
    res = g.run(SubTask(goal="评分", inputs={
        "question": "如何实现分布式锁?", "rubric": "看过期时间", "answer": "我会用 SETNX"}))
    assert res.structured["score"] == 4
    assert res.structured["weakness_tags"] == ["边界条件"]
    assert "4" in res.summary


def test_grader_defaults_follow_up_fields_when_missing():
    """旧格式输出(无追问判定字段)必须兼容: 默认不追。"""
    g = Grader(_FakeModel(_GRADER_JSON), tool_registry=None)
    res = g.run(SubTask(goal="评分", inputs={"question": "q", "answer": "a"}))
    assert res.structured["need_follow_up"] is False
    assert res.structured["follow_up_hint"] == ""


def test_grader_prompt_asks_follow_up_judgement():
    """评分 prompt 必须顺带索要 need_follow_up 判定, 不新增独立 LLM 调用。"""
    model = _FakeModel(_GRADER_JSON)
    Grader(model, tool_registry=None).run(
        SubTask(goal="评分", inputs={"question": "q", "answer": "a"}))
    prompt_text = "\n".join(m.content for m in model.seen)
    assert "need_follow_up" in prompt_text
    assert "follow_up_hint" in prompt_text


def test_grader_injects_answer_into_prompt():
    model = _FakeModel(_GRADER_JSON)
    g = Grader(model, tool_registry=None)
    g.run(SubTask(goal="评分", inputs={"question": "q", "answer": "我用了 Redlock"}))
    prompt_text = "\n".join(m.content for m in model.seen)
    assert "我用了 Redlock" in prompt_text


def test_grader_records_answer_when_question_id_present(tmp_path):
    mem = _memory(tmp_path)
    reg = build_default_registry(mem)
    g = Grader(_FakeModel(_GRADER_JSON), reg)
    g.run(SubTask(goal="评分", inputs={
        "question": "q", "answer": "a", "question_id": "qid-1"}))
    items = mem.episodic.all()
    assert len(items) == 1
    assert items[0].content["question_id"] == "qid-1"
    assert items[0].content["score"] == 4


def test_grader_no_record_without_question_id(tmp_path):
    mem = _memory(tmp_path)
    reg = build_default_registry(mem)
    g = Grader(_FakeModel(_GRADER_JSON), reg)
    g.run(SubTask(goal="评分", inputs={"question": "q", "answer": "a"}))
    assert mem.episodic.all() == []  # 无 question_id 不写


def test_grader_includes_reference_answer_in_prompt():
    """D: reference_answer 若提供, 应注入提示词供模型对照评分。"""
    model = _FakeModel(_GRADER_JSON)
    g = Grader(model, tool_registry=None)
    g.run(SubTask(goal="评分", inputs={
        "question": "如何实现分布式锁?", "answer": "我会用 SETNX",
        "reference_answer": "SETNX + 过期时间 + 唯一 value"}))
    prompt_text = "\n".join(m.content for m in model.seen)
    assert "SETNX + 过期时间 + 唯一 value" in prompt_text
    assert "参考答案" in prompt_text


def test_grader_skips_reference_answer_when_empty():
    """没有参考答案时不应在 prompt 里硬塞空行。"""
    model = _FakeModel(_GRADER_JSON)
    g = Grader(model, tool_registry=None)
    g.run(SubTask(goal="评分", inputs={"question": "q", "answer": "a"}))
    prompt_text = "\n".join(m.content for m in model.seen)
    assert "参考答案" not in prompt_text


def test_grader_passes_weakness_tags_to_record_answer(tmp_path):
    """weakness_tags 应从 structured 透传给 record_answer, 并持久化到 episodic 记忆。"""
    mem = _memory(tmp_path)
    reg = build_default_registry(mem)
    g = Grader(_FakeModel(_GRADER_JSON), reg)
    g.run(SubTask(goal="评分", inputs={
        "question": "q", "answer": "a", "question_id": "qid-2"}))
    items = mem.episodic.all()
    assert len(items) == 1
    assert items[0].content["weakness_tags"] == ["边界条件"]


def test_grader_cannot_call_search_questions(tmp_path):
    mem = _memory(tmp_path)
    g = Grader(_FakeModel(_GRADER_JSON), build_default_registry(mem))
    with pytest.raises(ToolPermissionError):
        g._call_tool("search_questions", role="后端", topic="redis")


import json
from interviewforge.tools.registry import ToolRegistry, Tool, ToolSpec


class FakeModel:
    def chat(self, messages, **kwargs):
        return json.dumps({"score": 4, "weakness_tags": ["t"], "feedback": "f"})


def test_grader_passes_dimension_to_record_answer():
    captured = {}
    reg = ToolRegistry()
    spec = ToolSpec(name="record_answer", description="",
                    parameters={"question_id": {"type": "str", "required": True},
                                "score": {"type": "int", "required": True}})

    def _rec(question_id, score, notes="", weakness_tags=None, dimension=None,
             is_follow_up=False, parent_question_id=None):
        captured.update(dimension=dimension, is_follow_up=is_follow_up,
                        parent_question_id=parent_question_id)
        return {"recorded": question_id}

    reg.register(Tool(spec, _rec))
    Grader(FakeModel(), reg).run(SubTask(goal="评分", inputs={
        "question": "Q", "answer": "A", "question_id": "be-1", "dimension": "存储层"}))
    assert captured["dimension"] == "存储层"
    # 未标追问时默认 False/None (主问路径)
    assert captured["is_follow_up"] is False
    assert captured["parent_question_id"] is None
