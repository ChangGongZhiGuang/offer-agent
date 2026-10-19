import pytest

from interviewforge.tools.registry import Tool, ToolRegistry, ToolSpec


def _echo_tool():
    spec = ToolSpec(
        name="echo",
        description="回显输入",
        parameters={"text": {"type": "str", "required": True}},
    )
    return Tool(spec, lambda text: {"echo": text})


def test_register_and_get():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    assert reg.names() == ["echo"]
    assert reg.get("echo").name == "echo"


def test_call_dispatches_and_returns():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    assert reg.call("echo", text="hi") == {"echo": "hi"}


def test_call_missing_required_param_raises():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    with pytest.raises(ValueError, match="missing required"):
        reg.call("echo")


def test_get_unknown_tool_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("nope")


def test_optional_param_not_required():
    spec = ToolSpec(name="t", description="d",
                    parameters={"a": {"required": True}, "b": {"required": False}})
    tool = Tool(spec, lambda a, b="default": f"{a}-{b}")
    reg = ToolRegistry()
    reg.register(tool)
    assert reg.call("t", a="x") == "x-default"


def test_render_definitions_lists_tools():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    text = reg.render_definitions()
    assert "echo" in text and "text" in text and "回显输入" in text
