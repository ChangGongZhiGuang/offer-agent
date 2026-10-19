from interviewforge.loop.driver import make_keyword_embedder, run_demo_interview
from interviewforge.loop.types import HaltReason
from interviewforge.persistence.transcript import Transcript
from interviewforge.rag.types import Question


def _questions():
    return [
        Question(id="be-1", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX+过期", difficulty="hard"),
        Question(id="be-2", role="后端", topic="mysql",
                 stem="MySQL 聚簇索引与非聚簇索引区别", answer="回表", difficulty="medium"),
        Question(id="be-3", role="后端", topic="并发",
                 stem="什么是缓存击穿如何缓解", answer="互斥锁", difficulty="medium"),
    ]


def test_full_interview_runs_end_to_end(tmp_path):
    report, loop = run_demo_interview(
        tmp_path,
        role="后端",
        topics=["redis", "mysql", "并发"],
        answers=["我用 SETNX 加过期", "聚簇存整行", "用互斥锁"],
        questions=_questions(),
        profile="擅长SQL, 弱分布式",
    )
    assert len(loop.state.asked_ids) == 3
    assert len(set(loop.state.asked_ids)) == 3
    items = loop.memory.episodic.all()
    assert len(items) == 3
    assert report["answered"] == 3
    assert report["avg_score"] == 4
    assert loop.state.halted == HaltReason.COMPLETED


def test_full_interview_writes_transcript(tmp_path):
    report, loop = run_demo_interview(
        tmp_path, role="后端", topics=["redis"],
        answers=["我用 SETNX"], questions=_questions(), profile="x")
    events = Transcript(tmp_path / "transcript.jsonl").replay()
    assert any(e.type == "transition" for e in events)
    tos = [e.payload.get("to") for e in events if e.type == "transition"]
    for ph in ("plan", "execute", "verify", "respond", "halt"):
        assert ph in tos


def test_keyword_embedder_ranks_matching_question_first(tmp_path):
    embed = make_keyword_embedder(["redis", "mysql"])
    vecs = embed(["后端 redis", "MySQL 索引"])
    assert vecs[0][0] == 1.0 and vecs[0][1] == 0.0
    assert vecs[1][1] == 1.0
