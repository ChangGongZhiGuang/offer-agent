import json

import pytest

from interviewforge.resume.types import CandidateProfile, Project
from interviewforge.subagents.base import SubTask, ToolPermissionError
from interviewforge.subagents.examiner import Examiner
from interviewforge.tools.registry import Tool, ToolRegistry, ToolSpec


class _FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.seen = []

    def chat(self, messages):
        self.seen = messages
        return self.reply


_EXAMINER_JSON = ('{"question": "如何实现分布式锁?", "rubric": "看是否提到过期时间", '
                  '"expected_points": ["SETNX", "过期时间"]}')


def _exam_registry(captured=None):
    reg = ToolRegistry()

    def _search(role, topic, difficulty=None):
        if captured is not None:
            captured["called"] = (role, topic, difficulty)
        return [{"question_id": "be-1", "stem": "如何实现分布式锁",
                 "difficulty": difficulty or "hard"}]

    reg.register(Tool(ToolSpec("search_questions", "",
                               {"role": {"required": True},
                                "topic": {"required": True},
                                "difficulty": {"required": False}}), _search))
    return reg


def test_examiner_returns_structured_question():
    ex = Examiner(_FakeModel(_EXAMINER_JSON), _exam_registry())
    res = ex.run(SubTask(goal="出题", inputs={
        "role": "后端", "topic": "redis", "difficulty": "hard", "profile": "擅长SQL"}))
    assert res.structured["question"] == "如何实现分布式锁?"
    assert "expected_points" in res.structured
    assert "后端" in res.summary and "redis" in res.summary


def test_examiner_calls_search_questions():
    captured = {}
    ex = Examiner(_FakeModel(_EXAMINER_JSON), _exam_registry(captured))
    ex.run(SubTask(goal="出题", inputs={"role": "后端", "topic": "redis"}))
    assert captured["called"] == ("后端", "redis", "medium")  # 默认难度


def test_examiner_followup_branch_skips_search_and_uses_chain():
    """出追问分支: 不调 search_questions, prompt 含上一题/回答/评语/追问方向/题库 fu。"""
    captured = {}
    model = _FakeModel('{"question": "追问: 锁续约怎么做?", "rubric": "r2", '
                       '"expected_points": []}')
    ex = Examiner(model, _exam_registry(captured), methodology="追问树: 答得好加深一层")
    res = ex.run(SubTask(goal="出追问", inputs={
        "role": "后端", "topic": "redis", "dimension": "缓存层",
        "prev_question": "如何实现分布式锁?", "prev_answer": "用 SETNX",
        "feedback": "不错但缺边界", "weakness_tags": ["边界"],
        "follow_up_hint": "深挖续期机制", "fu_hint": "答得好→追问红锁"}))
    assert res.structured["question"] == "追问: 锁续约怎么做?"
    assert "called" not in captured                     # 未查题库
    blob = " ".join(m.content for m in model.seen)
    for needle in ("如何实现分布式锁?", "用 SETNX", "不错但缺边界",
                   "深挖续期机制", "答得好→追问红锁", "追问树"):
        assert needle in blob


def test_examiner_forwards_difficulty_to_search_tool():
    captured = {}
    ex = Examiner(_FakeModel(_EXAMINER_JSON), _exam_registry(captured))
    ex.run(SubTask(goal="出题", inputs={
        "role": "后端", "topic": "redis", "difficulty": "hard"}))
    assert captured["called"] == ("后端", "redis", "hard")


def test_examiner_injects_profile_into_prompt():
    model = _FakeModel(_EXAMINER_JSON)
    ex = Examiner(model, _exam_registry())
    ex.run(SubTask(goal="出题", inputs={
        "role": "后端", "topic": "redis", "profile": "擅长SQL弱系统设计"}))
    prompt_text = "\n".join(m.content for m in model.seen)
    assert "擅长SQL弱系统设计" in prompt_text  # 画像显式注入隔离上下文


def test_examiner_cannot_call_record_answer():
    ex = Examiner(_FakeModel(_EXAMINER_JSON), _exam_registry())
    with pytest.raises(ToolPermissionError):
        ex._call_tool("record_answer", question_id="x", score=1)


def test_examiner_history_isolated_not_in_result():
    ex = Examiner(_FakeModel(_EXAMINER_JSON), _exam_registry())
    res = ex.run(SubTask(goal="出题", inputs={"role": "后端", "topic": "redis"}))
    assert len(ex._history) > 0          # 内部隔离历史存在
    assert not hasattr(res, "history")    # 完整历史不回主上下文


# ---------------------------------------------------------------------------
# Task 8: methodology / profile_struct / dimension injection
# ---------------------------------------------------------------------------

class FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.last_messages = None

    def chat(self, messages, **kwargs):
        self.last_messages = messages
        return self.reply


def _registry():
    reg = ToolRegistry()
    spec = ToolSpec(name="search_questions", description="",
                    parameters={"role": {"type": "str", "required": True},
                                "topic": {"type": "str", "required": True},
                                "difficulty": {"type": "str", "required": False}})
    reg.register(Tool(spec, lambda role, topic, difficulty=None: [
        {"question_id": "be-1", "question": "锚点题: 分布式锁?", "difficulty": "hard"}]))
    return reg


def _profile():
    return CandidateProfile(skills=["Redis"],
                            projects=[Project(name="秒杀", tech=["Redis"], summary="预扣库存")])


def test_examiner_injects_methodology_profile_project():
    model = FakeModel(json.dumps({"question": "你秒杀里 Redis 锁怎么防超卖?",
                                  "rubric": "看是否提到 Lua 原子", "expected_points": ["Lua"]},
                                 ensure_ascii=False))
    ex = Examiner(model, _registry(), methodology="追问树: 答得好加深一层")
    res = ex.run(SubTask(goal="出题", inputs={
        "role": "后端", "topic": "redis", "difficulty": "hard",
        "dimension": "缓存层", "profile_struct": _profile()}))
    blob = " ".join(m.content for m in model.last_messages)
    assert "追问树" in blob          # 方法论注入
    assert "秒杀" in blob            # 命中项目注入
    assert "锚点题" in blob          # 题库候选作锚点注入
    assert res.structured["dimension"] == "缓存层"  # 维度回填


def test_examiner_without_profile_struct_still_works():
    model = FakeModel(json.dumps({"question": "Q", "rubric": "r", "expected_points": []},
                                 ensure_ascii=False))
    ex = Examiner(model, _registry())
    res = ex.run(SubTask(goal="出题", inputs={"role": "后端", "topic": "redis"}))
    assert res.structured["question"] == "Q"
    assert res.structured["dimension"] is None


def test_examiner_uses_free_text_profile_when_struct_empty():
    """生产真实形态: 未上传简历时 build 给的是非 None 的空 CandidateProfile,
    自由文本画像在 inputs['profile']。应回退用自由文本, 否则出题完全忽略简历。"""
    model = FakeModel(json.dumps({"question": "Q", "rubric": "r", "expected_points": []},
                                 ensure_ascii=False))
    ex = Examiner(model, _registry())
    ex.run(SubTask(goal="出题", inputs={
        "role": "后端", "topic": "redis",
        "profile": "秒杀系统用Redis集群预扣库存,自述精通Redis,分布式CAP较弱",
        "profile_struct": CandidateProfile()}))  # 非 None 的空画像
    blob = " ".join(m.content for m in model.last_messages)
    assert "秒杀系统用Redis集群预扣库存" in blob
