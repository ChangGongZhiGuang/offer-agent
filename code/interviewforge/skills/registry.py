"""SkillRegistry: 扫描 SKILL.md frontmatter, 按 JD 匹配岗位方法论, 懒加载 body。"""
from __future__ import annotations

import re
from pathlib import Path

from interviewforge.skills.loader import SkillMeta, load_skill_body, load_skill_meta

_DEFAULT_SKILLS_DIR = Path(__file__).parent
_SPLIT = re.compile(r"[,、，。\s;:：]+")


def _terms(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text) if len(t) >= 2]


class SkillRegistry:
    def __init__(self, skills_dir: str | Path | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else _DEFAULT_SKILLS_DIR
        self._metas: list[SkillMeta] = self._scan()

    def _scan(self) -> list[SkillMeta]:
        return [load_skill_meta(p) for p in sorted(self.skills_dir.glob("*/SKILL.md"))]

    def list(self) -> list[SkillMeta]:
        return list(self._metas)

    def _score(self, meta: SkillMeta, query: str) -> int:
        return sum(1 for term in _terms(meta.description) if term in query)

    def match(self, query: str) -> SkillMeta | None:
        best, best_score = None, 0
        for meta in self._metas:
            score = self._score(meta, query)
            if score > best_score:
                best, best_score = meta, score
        return best

    def load(self, meta: SkillMeta) -> str:
        return load_skill_body(meta.path)

    def match_and_load(self, query: str) -> tuple[SkillMeta, str] | None:
        meta = self.match(query)
        if meta is None:
            return None
        return meta, self.load(meta)

    def methodology_for(self, query: str) -> tuple[str, list[str]]:
        """按 query 匹配岗位 SKILL.md, 返回 (方法论正文, 考察维度名列表)。无命中返回 ("", [])。"""
        from interviewforge.skills.dimensions import extract_dimensions
        loaded = self.match_and_load(query)
        if loaded is None:
            return "", []
        _meta, body = loaded
        return body, extract_dimensions(body)
