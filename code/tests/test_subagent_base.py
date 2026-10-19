import pytest

from interviewforge.subagents.base import (
    SubAgent,
    SubResult,
    SubTask,
    ToolPermissionError,
    parse_structured,
)
from interviewforge.tools.registry import Tool, ToolRegistry, ToolSpec


def _registry():
    reg = ToolRegistry()
    reg.register(Tool(ToolSpec("echo", "", {"x": {"required": True}}), lambda x: x))
    reg.register(Tool(ToolSpec("secret", "", {}), lambda: "secret"))
    return reg


class _Dummy(SubAgent):
    name = "dummy"
    allowed_tools = ["echo"]

    def run(self, task):
        return SubResult("ok", {})


def test_subtask_subresult_defaults():
    t = SubTask(goal="g")
    assert t.inputs == {}
    r = SubResult("s", {"a": 1})
    assert r.tokens_used == 0


def test_parse_structured_extracts_json():
    assert parse_structured('前缀 {"a": 1, "b": [2]} 后缀') == {"a": 1, "b": [2]}


def test_parse_structured_raises_without_json():
    with pytest.raises(ValueError):
        parse_structured("没有 json")


def test_call_tool_allowed():
    agent = _Dummy(model_client=None, tool_registry=_registry())
    assert agent._call_tool("echo", x="hi") == "hi"


def test_call_tool_denied_raises():
    agent = _Dummy(model_client=None, tool_registry=_registry())
    with pytest.raises(ToolPermissionError):
        agent._call_tool("secret")


def test_subagent_is_abstract():
    with pytest.raises(TypeError):
        SubAgent(model_client=None)
