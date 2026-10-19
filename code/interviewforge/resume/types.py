"""候选人结构化画像。一次 LLM 解析后存 semantic memory, 驱动题序与出题。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Project:
    name: str
    tech: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(name=d.get("name", ""), tech=list(d.get("tech", []) or []),
                   summary=d.get("summary", ""))


@dataclass
class CandidateProfile:
    skills: list[str] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    years: str = ""
    highlights: list[str] = field(default_factory=list)
    weak_spots: list[str] = field(default_factory=list)
    topic_plan: list[str] = field(default_factory=list)  # 建议主题序列

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateProfile":
        return cls(
            skills=list(d.get("skills", []) or []),
            projects=[Project.from_dict(p) for p in (d.get("projects", []) or [])],
            years=str(d.get("years", "") or ""),
            highlights=list(d.get("highlights", []) or []),
            weak_spots=list(d.get("weak_spots", []) or []),
            topic_plan=list(d.get("topic_plan", []) or []),
        )

    def to_dict(self) -> dict:
        return {
            "skills": self.skills,
            "projects": [{"name": p.name, "tech": p.tech, "summary": p.summary}
                         for p in self.projects],
            "years": self.years,
            "highlights": self.highlights,
            "weak_spots": self.weak_spots,
            "topic_plan": self.topic_plan,
        }

    def relevant_projects(self, topic: str) -> list[Project]:
        """挑出技术栈或描述命中该主题的项目 (供出题指着项目问)。"""
        key = (topic or "").lower()
        if not key:
            return []
        hits = []
        for p in self.projects:
            hay = (" ".join(p.tech) + " " + p.summary + " " + p.name).lower()
            if key in hay:
                hits.append(p)
        return hits

    def to_prompt(self, max_projects: int = 3) -> str:
        """精炼成注入子 Agent 的文本 (非全文, 控 token)。"""
        lines = []
        if self.years:
            lines.append(f"年限: {self.years}")
        if self.skills:
            lines.append("技能栈: " + ", ".join(self.skills))
        if self.highlights:
            lines.append("亮点: " + "; ".join(self.highlights))
        if self.weak_spots:
            lines.append("待深挖/存疑: " + "; ".join(self.weak_spots))
        for p in self.projects[:max_projects]:
            tech = "/".join(p.tech)
            lines.append(f"项目[{p.name}]({tech}): {p.summary}")
        return "\n".join(lines)
