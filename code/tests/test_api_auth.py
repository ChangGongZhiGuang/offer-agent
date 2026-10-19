"""认证 + 历史记录的端到端 HTTP 测试 (InMemory banks)。"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api.app import build_app
from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.auth.history import InMemoryHistoryBank
from interviewforge.auth.resume_store import InMemoryResumeStore
from interviewforge.auth.tokens import TokenStore
from interviewforge.auth.users import InMemoryUserBank
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore
from interviewforge.resume.types import CandidateProfile, Project

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
    qs = [Question(id="be-1", role="后端", topic="redis",
                    stem="如何用 Redis 实现分布式锁", answer="SETNX", difficulty="hard")]
    seed_questions(qb, vs, embed, qs)
    return Retriever(vs, qb, embed)


@pytest.fixture()
def deps(tmp_path):
    factory = SessionFactory(retriever=_retriever(), model_client=_RoutingFakeModel(),
                             base_dir=tmp_path)

    def _analyze_resume_text(text, role, jd):
        # 固定画像: 验证端点能拿到 profile 且不需上传文件
        return CandidateProfile(skills=["Redis", "Kafka"],
                                projects=[Project(name="秒杀", tech=["Redis"])],
                                years="3", topic_plan=["redis"])

    return {
        "store": SessionStore(factory),
        "user_bank": InMemoryUserBank(),
        "history_bank": InMemoryHistoryBank(),
        "token_store": TokenStore(),
        "resume_store": InMemoryResumeStore(),
        "analyze_resume_text": _analyze_resume_text,
    }


@pytest.fixture()
def client(deps):
    app = build_app(deps["store"], user_bank=deps["user_bank"],
                    history_bank=deps["history_bank"], token_store=deps["token_store"],
                    resume_store=deps["resume_store"],
                    analyze_resume_text=deps["analyze_resume_text"])
    return TestClient(app)


def _register(client, username="alice", password="secret123"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _run_interview(client, token, num_questions=1):
    """登录态下完成一场面试, 返回 session_id。"""
    create = client.post("/sessions", headers=_auth(token), json={
        "role": "后端", "topic": "redis", "num_questions": num_questions})
    sid = create.json()["session_id"]
    client.post(f"/sessions/{sid}/ask", headers=_auth(token))
    client.post(f"/sessions/{sid}/answer", headers=_auth(token), json={"answer": "SETNX"})
    client.post(f"/sessions/{sid}/finish", headers=_auth(token))
    return sid


def test_register_returns_token_and_me(client):
    token = _register(client)
    me = client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_register_invalid_username_400(client):
    resp = client.post("/auth/register", json={"username": "ab", "password": "secret123"})
    assert resp.status_code == 400


def test_register_short_password_400(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "12345"})
    assert resp.status_code == 400


def test_register_duplicate_409(client):
    _register(client)
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 409


def test_login_success_and_wrong_password(client):
    _register(client)
    ok = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert ok.status_code == 200 and ok.json()["token"]
    bad = client.post("/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert bad.status_code == 401
    # 不存在的用户也统一 401 (避免枚举)
    ghost = client.post("/auth/login", json={"username": "ghost", "password": "whatever"})
    assert ghost.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_history_requires_auth(client):
    assert client.get("/history").status_code == 401


def test_logged_in_interview_recorded(client, deps):
    token = _register(client)
    sid = _run_interview(client, token)
    listing = client.get("/history", headers=_auth(token)).json()
    assert len(listing) == 1
    assert listing[0]["session_id"] == sid
    # 详情可取回完整报告
    detail = client.get(f"/history/{sid}", headers=_auth(token))
    assert detail.status_code == 200
    assert detail.json()["report"]["answered"] >= 1


def test_anonymous_interview_not_recorded(client, deps):
    """未登录发起的面试即使事后登录也不写历史。"""
    create = client.post("/sessions", json={"role": "后端", "topic": "redis",
                                            "num_questions": 1})
    sid = create.json()["session_id"]
    client.post(f"/sessions/{sid}/ask")
    client.post(f"/sessions/{sid}/answer", json={"answer": "SETNX"})
    client.post(f"/sessions/{sid}/finish")   # 无 token
    # 之后再登录: 历史里不应出现这场匿名面试
    token = _register(client)
    listing = client.get("/history", headers=_auth(token)).json()
    assert all(it["session_id"] != sid for it in listing)


def test_history_isolated_between_users(client):
    t1 = _register(client, username="alice")
    t2 = _register(client, username="bob")
    sid1 = _run_interview(client, t1)
    # bob 看不到 alice 的记录
    assert client.get("/history", headers=_auth(t2)).json() == []
    # bob 直接访问 alice 的 session 详情 → 404
    assert client.get(f"/history/{sid1}", headers=_auth(t2)).status_code == 404


def test_logout_revokes_token(client):
    token = _register(client)
    assert client.get("/auth/me", headers=_auth(token)).status_code == 200
    client.post("/auth/logout", headers=_auth(token))
    assert client.get("/auth/me", headers=_auth(token)).status_code == 401


def test_detail_contains_qa_log(client):
    """登录面试结束后, 历史详情回传逐题问答 (题文 + 候选人答案)。"""
    token = _register(client)
    sid = _run_interview(client, token)
    detail = client.get(f"/history/{sid}", headers=_auth(token)).json()
    qa = detail["report"]["qa"]
    assert len(qa) >= 1
    first = qa[0]
    assert first["answer"] == "SETNX"
    assert first["question"]           # 题干原文已写入
    assert first["score"] == 4


def test_history_delete_endpoint(client):
    token = _register(client)
    sid = _run_interview(client, token)
    # 删除前存在
    assert client.get(f"/history/{sid}", headers=_auth(token)).status_code == 200
    del_resp = client.delete(f"/history/{sid}", headers=_auth(token))
    assert del_resp.status_code == 200
    # 删除后列表为空, 详情 404
    assert client.get("/history", headers=_auth(token)).json() == []
    assert client.get(f"/history/{sid}", headers=_auth(token)).status_code == 404


def test_history_delete_isolated_between_users(client):
    t1 = _register(client, username="alice")
    t2 = _register(client, username="bob")
    sid1 = _run_interview(client, t1)
    # bob 删除 alice 的记录 → 404, 且 alice 的记录仍在
    assert client.delete(f"/history/{sid1}", headers=_auth(t2)).status_code == 404
    assert client.get(f"/history/{sid1}", headers=_auth(t1)).status_code == 200


def test_history_delete_requires_auth(client):
    assert client.delete("/history/anything").status_code == 401


# ── 我的简历 ──────────────────────────────────────
def test_my_resume_requires_auth(client):
    assert client.get("/profile/me").status_code == 401
    assert client.put("/profile/me", json={"text": "x"}).status_code == 401
    assert client.delete("/profile/me").status_code == 401


def test_resume_save_get_roundtrip(client):
    token = _register(client)
    # 初始为空
    empty = client.get("/profile/me", headers=_auth(token)).json()
    assert empty["exists"] is False and empty["text"] == ""
    # 保存
    sv = client.put("/profile/me", headers=_auth(token),
                    json={"text": "3 年 Java 后端", "filename": "r.pdf"})
    assert sv.status_code == 200
    assert sv.json()["filename"] == "r.pdf"
    # 取回含正文
    got = client.get("/profile/me", headers=_auth(token)).json()
    assert got["exists"] is True
    assert got["text"] == "3 年 Java 后端"


def test_resume_save_overwrites(client):
    token = _register(client)
    client.put("/profile/me", headers=_auth(token),
               json={"text": "旧版", "filename": "old.pdf"})
    client.put("/profile/me", headers=_auth(token),
               json={"text": "新版", "filename": "new.docx"})
    got = client.get("/profile/me", headers=_auth(token)).json()
    assert got["text"] == "新版" and got["filename"] == "new.docx"


def test_resume_empty_text_400(client):
    token = _register(client)
    assert client.put("/profile/me", headers=_auth(token),
                      json={"text": "   "}).status_code == 400


def test_resume_delete(client):
    token = _register(client)
    client.put("/profile/me", headers=_auth(token), json={"text": "内容"})
    assert client.delete("/profile/me", headers=_auth(token)).status_code == 200
    assert client.get("/profile/me", headers=_auth(token)).json()["exists"] is False
    # 再删 → 404
    assert client.delete("/profile/me", headers=_auth(token)).status_code == 404


def test_resume_isolated_between_users(client):
    t1 = _register(client, username="alice")
    t2 = _register(client, username="bob")
    client.put("/profile/me", headers=_auth(t1), json={"text": "alice 简历"})
    # bob 看不到 alice 的简历
    assert client.get("/profile/me", headers=_auth(t2)).json()["exists"] is False


def test_resume_analyze_from_text_no_file(client):
    """POST /resume/analyze 无需上传文件, 直接返回结构化画像。"""
    resp = client.post("/resume/analyze",
                       json={"text": "3 年 Java, Redis 秒杀", "role": "后端", "jd": "redis"})
    assert resp.status_code == 200
    prof = resp.json()["profile"]
    assert prof["skills"] == ["Redis", "Kafka"]
    assert prof["projects"][0]["name"] == "秒杀"


def test_resume_analyze_empty_text_400(client):
    assert client.post("/resume/analyze", json={"text": "  "}).status_code == 400
