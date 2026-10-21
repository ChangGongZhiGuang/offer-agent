"""追问闭环: 评分后 LLM 判定 + 规则边界双重把关, 生成追问 → 追问作答 → 链闭合归档。"""
import json

from interviewforge.loop.adapter import SearchAdapter
from interviewforge.loop.machine import InterviewLoop
from interviewforge.loop.planner import RulePlanner
from interviewforge.loop.types import Bounds
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.working import WorkingMemory
from interviewforge.persistence.transcript import Transcript
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore
from interviewforge.subagents.examiner import Examiner
from interviewforge.subagents.grader import Grader
from interviewforge.tools.interview_tools import build_default_registry

_VOCAB = ["redis", "mysql", "分布式", "锁", "索引"]


def _embed(texts):
    return [[float(t.lower().count(w)) for w in _VOCAB] for t in texts]


class _SeqModel:
    """按调用次序回放回复; 用尽后固定回最后一条。保留最近一次 prompt 供断言。"""

    def __init__(self, replies):
        self._replies = list(replies)
        self._i = 0
        self.last_messages = []

    def chat(self, messages):
        self.last_messages = messages
        r = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return r


_EXAM_MAIN = '{"question": "如何实现分布式锁?", "rubric": "看过期时间", "expected_points": ["SETNX"]}'
_EXAM_FU = '{"question": "追问: 锁到期但任务没跑完怎么办?", "rubric": "看续约", "expected_points": ["watchdog"]}'


def _grade(score, need, hint=""):
    return json.dumps({"score": score, "weakness_tags": ["边界"], "feedback": "f",
                       "need_follow_up": need, "follow_up_hint": hint},
                      ensure_ascii=False)


_GRADE_HIT = _grade(5, True, "深挖持久化")      # 答得好 + LLM 判要追
_GRADE_MID = _grade(3, True)                    # LLM 判要追但分数在中段 → 规则拦截
_GRADE_HIT_NOFLAG = _grade(5, False)             # 分数到两端但 LLM 判不追
_GRADE_STUCK = _grade(1, True, "给提示换角度")   # 答得卡


def _memory(tmp_path):
    return MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )


def _retriever():
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    qs = [
        Question(id="be-1", role="后端", topic="redis",
                 stem="Redis 锁误删如何避免", answer="唯一 value",
                 difficulty="hard", fu="答得好 → 追问锁续期与红锁"),
        Question(id="be-2", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard"),
    ]
    seed_questions(qb, vs, _embed, qs)
    return Retriever(vs, qb, _embed)


def _build(tmp_path, grade_reply=_GRADE_HIT, *, bounds=None):
    """examiner 用序列模型: 第 1 次出主题, 之后都出追问; 每题追问上限默认 1。"""
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    registry = build_default_registry(mem, retriever=adapter)
    examiner = Examiner(_SeqModel([_EXAM_MAIN, _EXAM_FU]), registry)
    grader = Grader(_SeqModel([grade_reply] if isinstance(grade_reply, str) else grade_reply),
                    registry)
    loop = InterviewLoop(
        memory=mem, examiner=examiner, grader=grader, planner=RulePlanner(),
        registry=registry, search_adapter=adapter,
        transcript=Transcript(tmp_path / "t.jsonl"),
        bounds=bounds or Bounds(max_questions=3),
    )
    loop.start(role="后端", topic="redis", profile="擅长SQL")
    return loop, mem


def test_follow_up_triggered_after_high_score(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    res = loop.submit_answer("答得非常全面")
    assert res["score"] == 5
    assert res["is_follow_up"] is False
    assert res["follow_up_question"] == "追问: 锁到期但任务没跑完怎么办?"
    assert res["follow_up_of"] == "be-1"
    # pending 挂上, 主问链未闭合; 追问计数与 qid 正确
    assert loop.state.pending_follow_up is not None
    assert loop.state.pending_follow_up["question_id"] == "be-1-fu1"
    assert loop.state.total_follow_ups == 1
    assert loop.state.follow_up_counts == {"be-1": 1}
    # 追问不占主题额度: asked_ids 只有主题
    assert loop.state.asked_ids == ["be-1"]


def test_follow_up_answer_graded_and_chain_closes(tmp_path):
    # 主题与追问都判 5 分要追, 但每题上限=1 → 追问答完闭合
    loop, mem = _build(tmp_path, grade_reply=[_GRADE_HIT, _GRADE_HIT])
    loop.ask_question()
    loop.submit_answer("a1")
    res2 = loop.submit_answer("追问也答得好")
    assert res2["is_follow_up"] is True
    assert res2["follow_up_done"] is True
    assert "follow_up_question" not in res2
    assert loop.state.pending_follow_up is None
    assert loop.state.current_question is None
    # qa_log 全链归档
    log = loop.state.qa_log
    assert len(log) == 2
    assert log[0]["is_follow_up"] is False
    assert log[1]["is_follow_up"] is True
    assert log[1]["parent_question_id"] == "be-1"
    assert log[1]["question_id"] == "be-1-fu1"
    # episodic 追问条目带链标记, 供报告嵌套
    fu_items = [it for it in mem.episodic.all()
                if it.content.get("is_follow_up")]
    assert len(fu_items) == 1
    assert fu_items[0].content["parent_question_id"] == "be-1"


def test_mid_score_not_followed_even_if_llm_flags(tmp_path):
    """规则边界拦截: score=3 即使 LLM 判 need_follow_up 也不追。"""
    loop, mem = _build(tmp_path, grade_reply=_GRADE_MID)
    loop.ask_question()
    res = loop.submit_answer("一般般")
    assert "follow_up_question" not in res
    assert loop.state.pending_follow_up is None
    assert loop.state.current_question is None


def test_llm_veto_blocks_follow_up(tmp_path):
    """LLM 判定拦截: score=5 但 need_follow_up=False 不追。"""
    loop, mem = _build(tmp_path, grade_reply=_GRADE_HIT_NOFLAG)
    loop.ask_question()
    res = loop.submit_answer("答得好但没必要追")
    assert "follow_up_question" not in res
    assert loop.state.total_follow_ups == 0


def test_low_score_triggers_hint_follow_up(tmp_path):
    """答得卡 (score<=2): 走"给提示换角度"追问。"""
    loop, mem = _build(tmp_path, grade_reply=_GRADE_STUCK)
    loop.ask_question()
    res = loop.submit_answer("完全不会")
    assert res["follow_up_question"] == "追问: 锁到期但任务没跑完怎么办?"
    assert loop.state.pending_follow_up["parent_question_id"] == "be-1"


def test_follow_up_disabled_with_zero_bound(tmp_path):
    loop, mem = _build(tmp_path, bounds=Bounds(max_questions=3,
                                               max_follow_ups_per_question=0))
    loop.ask_question()
    res = loop.submit_answer("a")
    assert "follow_up_question" not in res
    assert loop.state.total_follow_ups == 0


def test_total_cap_truncates_second_question(tmp_path):
    """全场追问总量 ≤ 主题数: max_questions=1 时只允许 1 次追问。"""
    loop, mem = _build(tmp_path, grade_reply=[_GRADE_HIT, _GRADE_HIT, _GRADE_HIT],
                       bounds=Bounds(max_questions=1, max_follow_ups_per_question=2))
    loop.ask_question()
    res = loop.submit_answer("a1")
    assert res.get("follow_up_question")           # 第 1 次追问 (总量 0<1)
    res2 = loop.submit_answer("a2")
    # 每问上限 2 未到, 但全场总量 1>=1 → 闭合
    assert res2["follow_up_done"] is True
    assert loop.state.total_follow_ups == 1


def test_follow_up_prompt_consumes_fu_and_grader_context(tmp_path):
    """追问生成注入上一题/评语/题库 fu; 主题 structured 携带 fu_hint。"""
    mem = _memory(tmp_path)
    adapter = SearchAdapter(_retriever(), mem)
    registry = build_default_registry(mem, retriever=adapter)
    exam_model = _SeqModel([_EXAM_MAIN, _EXAM_FU])
    examiner = Examiner(exam_model, registry)
    grader = Grader(_SeqModel([_GRADE_HIT]), registry)
    loop = InterviewLoop(
        memory=mem, examiner=examiner, grader=grader, planner=RulePlanner(),
        registry=registry, search_adapter=adapter,
        transcript=Transcript(tmp_path / "t.jsonl"),
        bounds=Bounds(max_questions=3),
    )
    loop.start(role="后端", topic="redis", profile="")
    loop.ask_question()
    # 题库 fu 随主题带入 structured (命中 be-1, 其 fu 非空)
    assert loop.state.current_question["fu_hint"] == "答得好 → 追问锁续期与红锁"
    loop.submit_answer("a1")
    # examiner 第二次调用 (出追问) 的 prompt 应含问答链与题库引导
    blob = " ".join(m.content for m in exam_model.last_messages)
    assert "如何实现分布式锁?" in blob        # 上一题
    assert "a1" in blob                       # 候选人回答
    assert "深挖持久化" in blob               # Grader 的追问方向
    assert "答得好 → 追问锁续期与红锁" in blob  # 题库 fu 引导
    assert loop.state.pending_follow_up["reference_answer"] == "唯一 value"


def test_transcript_records_follow_up_event(tmp_path):
    loop, mem = _build(tmp_path)
    loop.ask_question()
    loop.submit_answer("a1")
    events = Transcript(tmp_path / "t.jsonl").replay()
    fu_events = [e for e in events if e.type == "follow_up"]
    assert len(fu_events) == 1
    assert fu_events[0].payload["parent"] == "be-1"
    assert fu_events[0].payload["depth"] == 1


def test_next_main_question_after_chain(tmp_path):
    """链闭合后正常进下一主题, 主题去重语义不受追问 qid 污染。"""
    loop, mem = _build(tmp_path, grade_reply=[_GRADE_HIT, _GRADE_HIT])
    loop.ask_question()
    loop.submit_answer("a1")          # 主题 be-1 → 追问 be-1-fu1
    loop.submit_answer("a2")          # 闭合
    q2 = loop.ask_question()
    assert q2 is not None
    assert loop.state.asked_ids == ["be-1", "be-2"]
    assert loop.state.total_follow_ups == 1
