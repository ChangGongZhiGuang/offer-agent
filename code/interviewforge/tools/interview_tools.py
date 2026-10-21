"""4 个面试工具 (工厂构造, 绑定依赖)。search_questions 预留 RAG 注入点。"""
from __future__ import annotations

from typing import Callable

from interviewforge.memory.base import MemoryService
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.tools.registry import Tool, ToolRegistry, ToolSpec


def make_search_questions(retriever: Callable | None = None) -> Tool:
    spec = ToolSpec(
        name="search_questions",
        description="按岗位/主题/难度查题库 (Phase 4 接 RAG; 当前为桩)",
        parameters={"role": {"type": "str", "required": True},
                    "topic": {"type": "str", "required": True},
                    "difficulty": {"type": "str", "required": False}},
    )

    def _run(role, topic, difficulty=None):
        if retriever is not None:
            return retriever(role=role, topic=topic, difficulty=difficulty)
        return [{"question_id": "stub-1",
                 "question": f"[stub] {role}/{topic} 示例题",
                 "difficulty": difficulty or "medium", "fu": ""}]

    return Tool(spec, _run)


def make_lookup_jd(jd_lookup: Callable | None = None) -> Tool:
    spec = ToolSpec(
        name="lookup_jd",
        description="查岗位要求",
        parameters={"company": {"type": "str", "required": True},
                    "role": {"type": "str", "required": True}},
    )

    def _run(company, role):
        if jd_lookup is not None:
            return jd_lookup(company=company, role=role)
        return {"company": company, "role": role,
                "requirements": ["数据库", "并发", "API 设计"]}

    return Tool(spec, _run)


def make_record_answer(memory: MemoryService) -> Tool:
    spec = ToolSpec(
        name="record_answer",
        description="把某题表现写入 episodic 记忆",
        parameters={"question_id": {"type": "str", "required": True},
                    "score": {"type": "int", "required": True},
                    "notes": {"type": "str", "required": False},
                    "weakness_tags": {"type": "list", "required": False},
                    "dimension": {"type": "str", "required": False},
                    "is_follow_up": {"type": "bool", "required": False},
                    "parent_question_id": {"type": "str", "required": False}},
    )

    def _run(question_id, score, notes="", weakness_tags=None, dimension=None,
             is_follow_up=False, parent_question_id=None):
        memory.remember(MemoryItem(
            kind=MemoryKind.EPISODIC,
            content={"question_id": question_id, "score": score, "notes": notes,
                     "weakness_tags": weakness_tags or [], "dimension": dimension,
                     "is_follow_up": bool(is_follow_up),
                     "parent_question_id": parent_question_id},
            salience=float(score),
        ))
        return {"recorded": question_id, "score": score}

    return Tool(spec, _run)


def make_generate_report(memory: MemoryService, model_client=None,
                         profile_text: str = "") -> Tool:
    spec = ToolSpec(name="generate_report", description="汇总本场表现生成维度雷达报告", parameters={})

    def _run():
        from interviewforge.reporting.report import ReportGenerator
        episodic = [it.content for it in memory.episodic.all()]
        return ReportGenerator(model_client).build(episodic, profile_text=profile_text)

    return Tool(spec, _run)


def build_default_registry(memory: MemoryService, retriever: Callable | None = None,
                           jd_lookup: Callable | None = None, model_client=None,
                           profile_text: str = "") -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(make_search_questions(retriever))
    reg.register(make_lookup_jd(jd_lookup))
    reg.register(make_record_answer(memory))
    reg.register(make_generate_report(memory, model_client, profile_text))
    return reg
