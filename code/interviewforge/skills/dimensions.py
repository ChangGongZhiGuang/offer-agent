"""从 SKILL.md 方法论正文抽取考察维度名 (用于题序规划与报告雷达轴)。"""
from __future__ import annotations

import re

# 匹配 "## 考察维度" 段落, 到下一个 "## " 或文末
_SECTION = re.compile(r"##\s*考察维度\s*(.*?)(?=\n##\s|\Z)", re.S)
# 段内三级标题: "### 1. 存储层（权重 30%）" -> 取 "存储层"
_HEADING = re.compile(r"^###\s*\d*\.?\s*([^（(\n]+)", re.M)


def extract_dimensions(body: str) -> list[str]:
    m = _SECTION.search(body or "")
    if not m:
        return []
    return [h.strip() for h in _HEADING.findall(m.group(1)) if h.strip()]
