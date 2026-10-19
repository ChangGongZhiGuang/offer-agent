import json

from interviewforge.resume.analyzer import ResumeAnalyzer
from interviewforge.resume.types import CandidateProfile


class FakeModel:
    def __init__(self, reply: str):
        self.reply = reply
        self.last_messages = None

    def chat(self, messages, **kwargs):
        self.last_messages = messages
        return self.reply


_JSON = json.dumps({
    "skills": ["Redis", "MySQL"],
    "projects": [{"name": "秒杀", "tech": ["Redis"], "summary": "预扣库存"}],
    "years": "3",
    "highlights": ["主导重构"],
    "weak_spots": ["分布式事务模糊"],
    "topic_plan": ["redis", "mysql"],
}, ensure_ascii=False)


def test_analyze_returns_structured_profile():
    model = FakeModel("解析结果如下:\n" + _JSON)
    profile = ResumeAnalyzer(model).analyze(
        resume_text="我做过 Redis 秒杀", role="后端",
        jd="Redis MySQL 高并发", methodology="考察维度: 存储/缓存")
    assert isinstance(profile, CandidateProfile)
    assert profile.skills == ["Redis", "MySQL"]
    assert profile.topic_plan == ["redis", "mysql"]
    assert profile.projects[0].name == "秒杀"


def test_prompt_includes_resume_role_and_methodology():
    model = FakeModel(_JSON)
    ResumeAnalyzer(model).analyze(resume_text="ABC简历正文", role="后端",
                                  jd="JD内容", methodology="方法论维度XYZ")
    blob = " ".join(m.content for m in model.last_messages)
    assert "ABC简历正文" in blob
    assert "后端" in blob
    assert "方法论维度XYZ" in blob
