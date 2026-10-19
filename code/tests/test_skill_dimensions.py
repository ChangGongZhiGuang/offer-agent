from interviewforge.skills.dimensions import extract_dimensions
from interviewforge.skills.registry import SkillRegistry

_BODY = """## 岗位画像
- foo

## 考察维度

### 1. 存储层（权重 30%）
- 索引

### 2. 缓存层（权重 20%）
- 模式

## 出题节奏
1. 开胃
"""


def test_extract_dimensions_strips_index_and_weight():
    assert extract_dimensions(_BODY) == ["存储层", "缓存层"]


def test_extract_dimensions_empty_when_no_section():
    assert extract_dimensions("## 其它\n正文") == []


def test_registry_methodology_for_returns_body_and_dims():
    reg = SkillRegistry()  # 扫描内置 skills/*/SKILL.md
    body, dims = reg.methodology_for("后端 Redis MySQL 并发")
    assert "考察维度" in body          # backend-interview 命中
    assert "存储层" in dims


def test_registry_methodology_for_no_match_returns_empty():
    body, dims = reg_no_match()
    assert body == ""
    assert dims == []


def reg_no_match():
    return SkillRegistry().methodology_for("完全不相关的词 zzzzz")
