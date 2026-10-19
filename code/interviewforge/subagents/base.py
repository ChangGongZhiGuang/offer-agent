"""子 Agent 隔离与权限的通用机制。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from interviewforge.types import Message, Role


@dataclass
class SubTask:
    goal: str                       # 单一明确目标
    inputs: dict = field(default_factory=dict)  # 主 agent 显式传入 (非共享内存!)


@dataclass
class SubResult:
    summary: str                    # 只回这个进主上下文
    structured: dict                # 结构化结果 (题目/分数)
    tokens_used: int = 0
    # 子 agent 完整对话历史不返回, 留在隔离上下文


class ToolPermissionError(PermissionError):
    """子 Agent 调用了不在 allowed_tools 内的工具。"""


def parse_structured(text: str) -> dict:
    """从模型输出里抽出第一个 JSON 对象。VERIFY 阶段会进一步校验合法性。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object found in: {text!r}")
    return json.loads(text[start : end + 1])


class SubAgent(ABC):
    name: str = "subagent"
    allowed_tools: list[str] = []

    def __init__(self, model_client, tool_registry=None, *, token_budget: int = 4000,
                 memory=None, assembler=None, role: str | None = None):
        self._model = model_client
        self._tools = tool_registry
        self.token_budget = token_budget
        # 注入后, 子 Agent 的系统提示经 ContextAssembler 组入 procedural 规则 + semantic 画像
        self._memory = memory
        self._assembler = assembler
        self._role = role
        self._history: list[Message] = []  # 隔离: 独立历史, 跑完即焚, 不回主上下文

    def _system_context(self, base_system: str) -> str:
        """有 memory+assembler 时, 用 Assembler 把全局规则与画像组进系统提示; 否则原样返回。"""
        if self._memory is None or self._assembler is None:
            return base_system
        from interviewforge.context.assembler import assemble_subagent_system
        return assemble_subagent_system(self._assembler, self._memory,
                                        base_system=base_system, role=self._role)

    def _call_tool(self, name: str, **kwargs):
        if name not in self.allowed_tools:
            raise ToolPermissionError(f"{self.name} not allowed to call tool '{name}'")
        if self._tools is None:
            raise RuntimeError("no tool registry provided")
        return self._tools.call(name, **kwargs)

    def _ask_model(self, messages: list[Message]) -> str:
        self._history.extend(messages)           # 记入隔离历史 (不回主上下文)
        reply = self._model.chat(messages)
        self._history.append(Message(role=Role.ASSISTANT, content=reply))
        return reply

    @abstractmethod
    def run(self, task: SubTask) -> SubResult: ...
