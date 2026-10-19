from pathlib import Path

from interviewforge.skills.loader import (
    SkillMeta,
    load_skill_body,
    load_skill_meta,
    parse_frontmatter,
)

_SKILLS = Path(__file__).resolve().parents[1] / "interviewforge" / "skills"


def test_parse_frontmatter_splits_meta_and_body():
    text = "---\nname: demo\ndescription: 测试技能\n---\n\n## 正文\n内容"
    fm, body = parse_frontmatter(text)
    assert fm == {"name": "demo", "description": "测试技能"}
    assert body.startswith("## 正文")


def test_parse_frontmatter_without_frontmatter():
    fm, body = parse_frontmatter("没有 frontmatter 的正文")
    assert fm == {}
    assert body == "没有 frontmatter 的正文"


def test_load_skill_meta_reads_frontmatter_only():
    meta = load_skill_meta(_SKILLS / "backend-interview" / "SKILL.md")
    assert isinstance(meta, SkillMeta)
    assert meta.name == "backend-interview"
    assert "数据库" in meta.description


def test_load_skill_body_excludes_frontmatter():
    body = load_skill_body(_SKILLS / "backend-interview" / "SKILL.md")
    assert "考察维度" in body
    assert "description:" not in body
