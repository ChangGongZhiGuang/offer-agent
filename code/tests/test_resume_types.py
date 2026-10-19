from interviewforge.resume.types import CandidateProfile, Project


def _profile() -> CandidateProfile:
    return CandidateProfile(
        skills=["Redis", "MySQL", "Kafka"],
        projects=[
            Project(name="秒杀系统", tech=["Redis", "Kafka"], summary="10w QPS 秒杀，Redis 预扣库存"),
            Project(name="后台管理", tech=["Vue"], summary="中后台 CRUD"),
        ],
        years="3",
        highlights=["主导秒杀重构"],
        weak_spots=["分布式事务讲不清"],
        topic_plan=["redis", "mysql", "分布式"],
    )


def test_to_prompt_includes_skills_and_projects():
    text = _profile().to_prompt()
    assert "Redis" in text
    assert "秒杀系统" in text
    assert "分布式事务讲不清" in text  # 薄弱点也注入, 供出题深挖


def test_to_prompt_caps_projects():
    text = _profile().to_prompt(max_projects=1)
    assert "秒杀系统" in text
    assert "后台管理" not in text


def test_relevant_projects_matches_topic_in_tech_or_summary():
    hits = _profile().relevant_projects("redis")
    assert [p.name for p in hits] == ["秒杀系统"]


def test_relevant_projects_empty_when_no_match():
    assert _profile().relevant_projects("图算法") == []


def test_from_dict_tolerates_missing_fields():
    p = CandidateProfile.from_dict({"skills": ["Go"]})
    assert p.skills == ["Go"]
    assert p.projects == []
    assert p.topic_plan == []
