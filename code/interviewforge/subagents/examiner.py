"""Examiner 出题官: 题库候选作锚点 + 方法论 + 画像/项目 → LLM 产个性化题。"""
from __future__ import annotations

from interviewforge.subagents.base import SubAgent, SubResult, SubTask, parse_structured
from interviewforge.types import Message, Role

_SYSTEM = "你是严谨的面试出题官, 结合方法论与候选人画像出一道贴其经历的题, 只输出一道题的 JSON。"


def _build_prompt(role: str, topic: str, difficulty: str, dimension: str | None,
                  methodology: str, profile_text: str, projects_text: str,
                  candidates) -> str:
    method_block = f"出题方法论(标尺):\n{methodology}\n" if methodology else ""
    profile_block = f"候选人画像:\n{profile_text}\n" if profile_text else ""
    project_block = f"可深挖的相关项目:\n{projects_text}\n" if projects_text else ""
    dim_line = f" 考察维度:{dimension}" if dimension else ""
    return (
        f"岗位:{role} 主题:{topic} 难度:{difficulty}{dim_line}\n"
        f"{method_block}{profile_block}{project_block}"
        f"题库候选题(仅作方向锚点, 可改写或据此另出更贴候选人经历的题):\n{candidates}\n"
        '请输出一道题, 以 JSON 返回 {"question", "rubric", "expected_points", "anchored_question_id"(命中的候选题id或null)}。'
    )


class Examiner(SubAgent):
    name = "examiner"
    allowed_tools = ["search_questions", "lookup_jd"]

    def __init__(self, model_client, tool_registry=None, *, methodology: str = "",
                 token_budget: int = 4000, memory=None, assembler=None,
                 role: str | None = None):
        super().__init__(model_client, tool_registry, token_budget=token_budget,
                         memory=memory, assembler=assembler, role=role)
        self.methodology = methodology

    def run(self, task: SubTask) -> SubResult:
        role = task.inputs["role"]
        topic = task.inputs["topic"]
        difficulty = task.inputs.get("difficulty", "medium")
        dimension = task.inputs.get("dimension")
        profile_struct = task.inputs.get("profile_struct")

        # 结构化画像优先; 为空 (含非 None 的空画像) 时回退到自由文本画像
        profile_text = (profile_struct.to_prompt().strip() if profile_struct is not None
                        else "") or task.inputs.get("profile", "")
        projects_text = ""
        if profile_struct is not None:
            hits = profile_struct.relevant_projects(topic)
            projects_text = "\n".join(
                f"- {p.name}({'/'.join(p.tech)}): {p.summary}" for p in hits)

        candidates = self._call_tool("search_questions", role=role, topic=topic,
                                     difficulty=difficulty)
        prompt = _build_prompt(role, topic, difficulty, dimension, self.methodology,
                               profile_text, projects_text, candidates)
        reply = self._ask_model([
            Message(role=Role.SYSTEM, content=self._system_context(_SYSTEM)),
            Message(role=Role.USER, content=prompt),
        ])
        structured = parse_structured(reply)
        structured["dimension"] = dimension       # 回填供评分/报告聚合
        summary = f"为[{role}/{topic}]出了一道{difficulty}难度的题"
        return SubResult(summary=summary, structured=structured)
