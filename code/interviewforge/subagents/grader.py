"""Grader 评分官: 调模型评分, 产出 {score, weakness_tags, feedback, need_follow_up, follow_up_hint}, 可选写 episodic。"""
from __future__ import annotations

from interviewforge.subagents.base import SubAgent, SubResult, SubTask, parse_structured
from interviewforge.types import Message, Role

_SYSTEM = "你是公正的面试评分官, 只输出评分的 JSON。"


def _build_prompt(question: str, rubric: str, answer: str,
                  reference_answer: str = "") -> str:
    ref_line = f"\n参考答案(对照,不直接告知候选人):{reference_answer}" if reference_answer else ""
    return (
        f"题目:{question}\n评分标准:{rubric}{ref_line}\n候选人回答:{answer}\n"
        '请以 JSON 返回 {"score"(1-5 整数), "weakness_tags"(字符串数组), "feedback", '
        '"need_follow_up"(答得特别好 4-5 分或特别差 1-2 分且值得追问则 true, 否则 false), '
        '"follow_up_hint"(追问方向一句话: 4-5 分往更深一层追, 1-2 分给提示换角度; 不需要时为空)}。'
    )


class Grader(SubAgent):
    name = "grader"
    allowed_tools = ["record_answer"]

    def run(self, task: SubTask) -> SubResult:
        question = task.inputs["question"]
        answer = task.inputs["answer"]
        rubric = task.inputs.get("rubric", "")
        reference_answer = task.inputs.get("reference_answer", "")
        prompt = _build_prompt(question, rubric, answer, reference_answer)
        reply = self._ask_model([
            Message(role=Role.SYSTEM, content=self._system_context(_SYSTEM)),
            Message(role=Role.USER, content=prompt),
        ])
        structured = parse_structured(reply)  # {score, weakness_tags, feedback, need_follow_up, follow_up_hint}
        # 兼容旧模型输出/测试 FakeModel: 缺追问判定字段时默认不追
        structured.setdefault("need_follow_up", False)
        structured.setdefault("follow_up_hint", "")

        question_id = task.inputs.get("question_id")
        if question_id is not None and self._tools is not None:
            self._call_tool("record_answer", question_id=question_id,
                            score=structured["score"],
                            notes=structured.get("feedback", ""),
                            weakness_tags=structured.get("weakness_tags", []),
                            dimension=task.inputs.get("dimension"),
                            is_follow_up=bool(task.inputs.get("is_follow_up")),
                            parent_question_id=task.inputs.get("parent_question_id"))

        summary = f"评分 {structured.get('score')} 分"
        return SubResult(summary=summary, structured=structured)
