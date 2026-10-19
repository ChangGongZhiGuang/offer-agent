import json

from interviewforge.reporting.report import ReportGenerator


class FakeModel:
    def chat(self, messages, **kwargs):
        return json.dumps({"summary": "整体中等", "suggestions": ["补分布式事务"]},
                          ensure_ascii=False)


_EPISODIC = [
    {"question_id": "be-1", "score": 4, "notes": "好", "weakness_tags": ["lua"], "dimension": "缓存层"},
    {"question_id": "be-2", "score": 2, "notes": "弱", "weakness_tags": ["事务"], "dimension": "存储层"},
    {"question_id": "be-3", "score": 4, "notes": "好", "weakness_tags": ["lua"], "dimension": "缓存层"},
]


def test_dimension_scores_are_grouped_averages():
    rep = ReportGenerator(FakeModel()).build(_EPISODIC, profile_text="")
    dims = {d["name"]: d["score"] for d in rep["dimensions"]}
    assert dims["缓存层"] == 4.0       # (4+4)/2
    assert dims["存储层"] == 2.0


def test_overall_and_weakness_dedup():
    rep = ReportGenerator(FakeModel()).build(_EPISODIC, profile_text="")
    assert rep["answered"] == 3
    assert round(rep["overall_score"], 2) == round((4 + 2 + 4) / 3, 2)
    assert sorted(rep["weakness_tags"]) == ["lua", "事务"]   # 去重


def test_llm_summary_and_suggestions_included():
    rep = ReportGenerator(FakeModel()).build(_EPISODIC, profile_text="")
    assert rep["summary"] == "整体中等"
    assert rep["suggestions"] == ["补分布式事务"]


def test_no_model_falls_back_without_crash():
    rep = ReportGenerator(None).build(_EPISODIC, profile_text="")
    assert rep["summary"]            # 非空兜底文案
    assert isinstance(rep["suggestions"], list)


def test_empty_episodic_safe():
    rep = ReportGenerator(None).build([], profile_text="")
    assert rep["answered"] == 0
    assert rep["overall_score"] == 0
    assert rep["dimensions"] == []
