import io

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api.app import build_app
from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore

_VOCAB = ["redis", "mysql", "分布式", "锁", "索引"]


class _RoutingFakeModel:
    def chat(self, messages):
        text = " ".join(m.content for m in messages)
        if "评分" in text:
            return '{"score": 4, "weakness_tags": ["边界"], "feedback": "不错"}'
        return ('{"question": "如何实现分布式锁?", "rubric": "看过期时间", '
                '"expected_points": ["SETNX"]}')


def _retriever():
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    embed = make_keyword_embedder(_VOCAB)
    qs = [
        Question(id="be-1", role="后端", topic="redis",
                 stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard"),
        Question(id="be-2", role="后端", topic="redis",
                 stem="Redis 锁误删如何避免", answer="唯一 value", difficulty="hard"),
    ]
    seed_questions(qb, vs, embed, qs)
    return Retriever(vs, qb, embed)


def _fake_analyze_resume(file_bytes, filename, role, jd):
    """Test-hermetic fake: always returns a fixed CandidateProfile with Redis skills."""
    from interviewforge.resume.types import CandidateProfile
    from interviewforge.resume.parser import extract_text
    text = extract_text(file_bytes, filename)
    profile = CandidateProfile(skills=["Redis"], topic_plan=["redis"])
    return text, profile


def _build_store(tmp_path):
    factory = SessionFactory(retriever=_retriever(), model_client=_RoutingFakeModel(),
                             base_dir=tmp_path)
    return SessionStore(factory)


@pytest.fixture()
def client(tmp_path):
    return TestClient(build_app(_build_store(tmp_path)))


@pytest.fixture()
def app_with_fakes(tmp_path):
    return build_app(_build_store(tmp_path), analyze_resume=_fake_analyze_resume)


def _start(client, num_questions=3):
    resp = client.post("/sessions", json={"role": "后端", "topic": "redis",
                                          "profile": "擅长SQL", "num_questions": num_questions})
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_create_session(client):
    resp = client.post("/sessions", json={"role": "后端", "topic": "redis"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "后端" and body["session_id"]


def test_ask_returns_question(client):
    sid = _start(client)
    resp = client.post(f"/sessions/{sid}/ask")
    assert resp.status_code == 200
    body = resp.json()
    assert body["done"] is False
    # 混合方案: LLM 个性化题干保留 (题库锚点不再覆盖)
    assert body["question"] == "如何实现分布式锁?"
    assert body["question_id"] == "be-2"


def test_answer_returns_score(client):
    sid = _start(client)
    client.post(f"/sessions/{sid}/ask")
    resp = client.post(f"/sessions/{sid}/answer", json={"answer": "我用 SETNX 加过期"})
    assert resp.status_code == 200
    assert resp.json()["score"] == 4


def test_full_flow_then_report(client):
    sid = _start(client, num_questions=2)
    for answer in ("a1", "a2"):
        q = client.post(f"/sessions/{sid}/ask").json()
        assert q["done"] is False
        client.post(f"/sessions/{sid}/answer", json={"answer": answer})
    report = client.post(f"/sessions/{sid}/finish")
    assert report.status_code == 200
    body = report.json()
    assert body["answered"] == 2 and body["avg_score"] == 4


def test_status_endpoint(client):
    sid = _start(client)
    client.post(f"/sessions/{sid}/ask")
    resp = client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["asked"] == 1 and body["turn"] == 1


def test_unknown_session_404(client):
    assert client.post("/sessions/nope/ask").status_code == 404
    assert client.get("/sessions/nope").status_code == 404


def test_answer_without_question_409(client):
    sid = _start(client)
    resp = client.post(f"/sessions/{sid}/answer", json={"answer": "无题先答"})
    assert resp.status_code == 409


def test_resume_endpoint_returns_profile(app_with_fakes):
    client = TestClient(app_with_fakes)
    files = {"file": ("cv.txt", io.BytesIO("精通 Redis".encode("utf-8")), "text/plain")}
    resp = client.post("/resume", data={"role": "后端", "jd": "Redis"}, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert "profile" in body and "skills" in body["profile"]


def test_full_flow_with_dimension_report(app_with_fakes):
    client = TestClient(app_with_fakes)
    create = client.post("/sessions", json={
        "role": "后端", "topic": "redis", "jd_keywords": ["高并发"],
        "num_questions": 2,
        "profile_struct": {"skills": ["Redis"], "topic_plan": ["redis", "mysql"]},
    })
    sid = create.json()["session_id"]
    for _ in range(2):
        q = client.post(f"/sessions/{sid}/ask").json()
        if q["done"]:
            break
        client.post(f"/sessions/{sid}/answer", json={"answer": "用 Lua 原子扣减"})
    report = client.post(f"/sessions/{sid}/finish").json()
    assert "dimensions" in report
    assert "overall_score" in report
    assert "suggestions" in report
