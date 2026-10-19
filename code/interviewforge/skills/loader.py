"""SKILL.md 解析: 分离 frontmatter 与 body。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SkillMeta:
    """从 SKILL.md frontmatter 中提取的元信息。"""
    name: str          # 技能名称, 供 /skill 命令索引
    description: str   # 简要描述, 显示在技能列表中供用户理解用途
    path: Path         # 磁盘路径, 用于读取 body 或文件系统操作


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """将 SKILL.md 原文拆解为 frontmatter (dict) 与 body (str)。

    文件格式约定:
        ---
        name: my-skill
        description: ...
        ---
        body 正文从这里开始 ...

    若开头不是 "---" 则认为没有 frontmatter, 整个文本当作 body。
    --- 只出现一次 (缺少闭合) 时视为无 frontmatter。

    Returns:
        (frontmatter_dict, body_string)。无 frontmatter 时返回 ({}, 原文)。
    """
    # 不以 "---" 开头 → 无 frontmatter, 整篇都是 body
    if not text.startswith("---"):
        return {}, text

    # 以 "---" 切分: [0]前置空, [1]frontmatter YAML, [2]body
    parts = text.split("---", 2)
    if len(parts) < 3:
        # 只有开头 --- 没有闭合 ---, 视为无 frontmatter
        return {}, text

    # YAML 解析失败时 safe_load 返回 None, 统一转为空 dict
    fm = yaml.safe_load(parts[1]) or {}
    # 去掉 body 开头的换行, 避免空行污染正文
    body = parts[2].lstrip("\n")
    return fm, body


def load_skill_meta(path: str | Path) -> SkillMeta:
    """仅读取 SKILL.md 的 frontmatter 元信息, 忽略 body。

    用于技能注册/列表场景——只需要技能名和描述, 不需要加载完整指令。
    """
    path = Path(path)
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    # frontmatter 中必须含 name 与 description, 缺了就报 KeyError (调用方负责捕获)
    return SkillMeta(name=fm["name"], description=fm["description"], path=path)


def load_skill_body(path: str | Path) -> str:
    """读取 SKILL.md 的 body 部分 (即技能指令正文), 丢弃 frontmatter。

    用于技能执行场景——只需把指令喂给模型, 元信息已提前注册。
    """
    _, body = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
    return body
