"""工具池: Tool 校验必填参数, ToolRegistry 注册/分派/渲染定义。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # {param: {"type": str, "required": bool}}


class Tool:
    def __init__(self, spec: ToolSpec, func: Callable[..., Any]):
        self.spec = spec
        self._func = func

    @property
    def name(self) -> str:
        return self.spec.name

    def required_params(self) -> list[str]:
        return [p for p, meta in self.spec.parameters.items() if meta.get("required")]

    def __call__(self, **kwargs) -> Any:
        missing = [p for p in self.required_params() if p not in kwargs]
        if missing:
            raise ValueError(f"missing required params for {self.name}: {missing}")
        return self._func(**kwargs)

    def run(self, **kwargs) -> Any:
        return self(**kwargs)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)

    def call(self, name: str, **kwargs) -> Any:
        return self.get(name)(**kwargs)

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def render_definitions(self) -> str:
        lines = []
        for s in self.specs():
            params = ", ".join(s.parameters.keys())
            lines.append(f"- {s.name}({params}): {s.description}")
        return "\n".join(lines)
