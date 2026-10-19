"""ResumeAnalyzer: 一次 LLM 调用把简历解析成 CandidateProfile。"""
from __future__ import annotations

from interviewforge.resume.types import CandidateProfile
from interviewforge.subagents.base import parse_structured
from interviewforge.types import Message, Role

_SYSTEM = "你是资深技术招聘官, 把简历解析成结构化 JSON 画像, 只输出 JSON。"

_INSTRUCT = (
    '请仅以 JSON 返回, 字段: '
    '{"skills":[字符串], "projects":[{"name","tech":[字符串],"summary"}], '
    '"years":字符串, "highlights":[字符串], "weak_spots":[需深挖或存疑的点], '
    '"topic_plan":[按重要性排序的建议考察主题, 取自岗位与简历交集]}。'
)


class ResumeAnalyzer:
    def __init__(self, model_client):
        self._model = model_client

    def analyze(self, *, resume_text: str, role: str, jd: str = "",
                methodology: str = "") -> CandidateProfile:
        prompt = (
            f"目标岗位: {role}\n"
            f"岗位 JD: {jd}\n"
            f"岗位面试方法论(用于判断该考察哪些维度):\n{methodology}\n"
            f"---简历正文---\n{resume_text}\n---简历结束---\n"
            f"{_INSTRUCT}"
        )
        reply = self._model.chat([
            Message(role=Role.SYSTEM, content=_SYSTEM),
            Message(role=Role.USER, content=prompt),
        ])
        return CandidateProfile.from_dict(parse_structured(reply))
