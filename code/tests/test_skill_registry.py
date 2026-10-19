from pathlib import Path

from interviewforge.skills.registry import SkillRegistry

_SKILLS = Path(__file__).resolve().parents[1] / "interviewforge" / "skills"


EXPECTED_SKILLS = {
    "backend-interview",
    "algorithm-interview",
    "system-design",
    "frontend-interview",
    "data-engineering-interview",
    "ml-interview",
    "devops-sre-interview",
}


def test_list_scans_all_skills():
    reg = SkillRegistry(_SKILLS)
    names = {m.name for m in reg.list()}
    # 至少要包含全部预期 skill (允许后续再加新的)
    assert EXPECTED_SKILLS <= names


def test_match_backend_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("这个岗位需要熟悉数据库、并发和分布式系统设计")
    assert meta is not None and meta.name == "backend-interview"


def test_match_algorithm_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("需要刷过很多 LeetCode 算法题, 熟悉动态规划和数据结构")
    assert meta is not None and meta.name == "algorithm-interview"


def test_match_unrelated_returns_none():
    reg = SkillRegistry(_SKILLS)
    assert reg.match("完全无关的内容 xyzqwerty") is None


def test_load_returns_body_only():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("数据库 并发 分布式")
    body = reg.load(meta)
    assert "考察维度" in body
    assert "description:" not in body


def test_match_and_load_one_shot():
    reg = SkillRegistry(_SKILLS)
    result = reg.match_and_load("数据库 并发 缓存")
    assert result is not None
    meta, body = result
    assert meta.name == "backend-interview"
    assert "追问树" in body


def test_match_system_design_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("岗位要求做系统设计 高并发 秒杀 海量数据 架构设计")
    assert meta is not None and meta.name == "system-design"


def test_match_frontend_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("前端工程师 熟悉 Vue React TypeScript 浏览器 CSS 性能优化")
    assert meta is not None and meta.name == "frontend-interview"


def test_match_data_engineering_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("大数据 数仓 Spark Flink Hive Kafka ETL 维度建模")
    assert meta is not None and meta.name == "data-engineering-interview"


def test_match_ml_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("机器学习 深度学习 大模型 LLM PyTorch CV NLP 推荐")
    assert meta is not None and meta.name == "ml-interview"


def test_match_devops_sre_jd():
    reg = SkillRegistry(_SKILLS)
    meta = reg.match("SRE 运维 Kubernetes K8s Docker CI/CD Prometheus 监控 稳定性 SLO")
    assert meta is not None and meta.name == "devops-sre-interview"


def test_loaded_body_is_rich():
    """新版 SKILL.md 必须含统一的方法论小节, 避免回退到精简版本。"""
    reg = SkillRegistry(_SKILLS)
    for meta in reg.list():
        body = reg.load(meta)
        for section in ("岗位画像", "考察维度", "追问树", "评分 rubric", "红旗"):
            assert section in body, f"{meta.name} missing section {section!r}"
