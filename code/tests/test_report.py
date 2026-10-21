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


_EPISODIC_WITH_FU = [
    {"question_id": "be-1", "score": 4, "notes": "好", "weakness_tags": [], "dimension": "缓存层"},
    {"question_id": "be-1-fu1", "score": 2, "notes": "追问弱", "weakness_tags": ["续约"],
     "dimension": "缓存层", "is_follow_up": True, "parent_question_id": "be-1"},
    {"question_id": "be-2", "score": 2, "notes": "弱", "weakness_tags": ["事务"], "dimension": "存储层"},
]


def test_follow_ups_nested_and_excluded_from_avg():
    """追问不进 answered/avg/维度分母, 嵌套到主问明细; 全场追问计数正确。"""
    rep = ReportGenerator(None).build(_EPISODIC_WITH_FU, profile_text="")
    assert rep["answered"] == 2                      # 只算主题
    assert rep["avg_score"] == 3.0                   # (4+2)/2, 追问 2 分不入
    assert rep["follow_up_total"] == 1
    by_id = {r["question_id"]: r for r in rep["per_question"]}
    assert set(by_id) == {"be-1", "be-2"}
    assert by_id["be-1"]["follow_ups"][0]["question_id"] == "be-1-fu1"
    assert "follow_ups" not in by_id["be-2"]
    # 维度聚合只按主题: 缓存层 = 4 (追问题 2 不入), 存储层 = 2
    dims = {d["name"]: d["score"] for d in rep["dimensions"]}
    assert dims["缓存层"] == 4.0


def test_orphan_follow_up_kept_as_standalone_row():
    """找不到主问的追问条目 (旧数据/异常) 回退为独立行, 不丢数据。"""
    episodic = [{"question_id": "x-fu1", "score": 3, "notes": "", "weakness_tags": [],
                 "dimension": None, "is_follow_up": True, "parent_question_id": "ghost"}]
    rep = ReportGenerator(None).build(episodic, profile_text="")
    assert rep["answered"] == 0
    assert rep["per_question"][0]["question_id"] == "x-fu1"
    assert rep["per_question"][0]["is_follow_up"] is True
