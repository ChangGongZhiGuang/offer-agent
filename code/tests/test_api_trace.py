"""Trace 重放端点 GET /sessions/{session_id}/trace 的集成测试。"""
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
    ]
    seed_questions(qb, vs, embed, qs)
    return Retriever(vs, qb, embed)


def _build_store(tmp_path):
    factory = SessionFactory(retriever=_retriever(), model_client=_RoutingFakeModel(),
                             base_dir=tmp_path)
    return SessionStore(factory)


@pytest.fixture()
def store(tmp_path):
    return _build_store(tmp_path)


@pytest.fixture()
def client(store):
    return TestClient(build_app(store))


def _start_and_finish(client, store):
    """创建会话 → 问一题 → 作答 → finish,返回 session_id。"""
    resp = client.post("/sessions", json={
        "role": "后端", "topic": "redis", "profile": "擅长SQL", "num_questions": 1})
    sid = resp.json()["session_id"]
    # 问一题
    client.post(f"/sessions/{sid}/ask")
    # 作答
    client.post(f"/sessions/{sid}/answer", json={"answer": "用 SETNX 加过期时间"})
    # 收尾
    client.post(f"/sessions/{sid}/finish")
    return sid


def test_trace_returns_events_for_live_session(client, store):
    """会话存活时调 trace 应返回 transition 事件列表。"""
    sid = _start_and_finish(client, store)
    resp = client.get(f"/sessions/{sid}/trace")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) > 0
    # 应包含 transition 类型
    types = {e["type"] for e in events}
    assert "transition" in types
    # 每条事件必有 type / ts / payload
    for e in events:
        assert "type" in e and "ts" in e and "payload" in e


def test_trace_contains_expected_phases(client, store):
    """trace 事件应包含 plan/execute/verify/respond/halt 等关键相位。"""
    sid = _start_and_finish(client, store)
    resp = client.get(f"/sessions/{sid}/trace")
    events = resp.json()
    tos = [e["payload"].get("to") for e in events if e["type"] == "transition"]
    for phase in ("plan", "execute", "verify", "respond", "halt"):
        assert phase in tos, f"missing phase '{phase}' in trace: {tos}"


def test_trace_persists_after_session_removed(client, store):
    """会话从内存移除后(模拟重启), trace 仍可从磁盘文件读取。"""
    sid = _start_and_finish(client, store)
    # 从内存移除会话
    store.remove(sid)
    resp = client.get(f"/sessions/{sid}/trace")
    assert resp.status_code == 200
    events = resp.json()
    # 文件仍在磁盘, 应返回同样非空的事件列表
    assert len(events) > 0
    assert any(e["type"] == "transition" for e in events)


def test_trace_nonexistent_session_returns_empty(client):
    """不存在的 session_id 应返回空列表(200)。"""
    resp = client.get("/sessions/nonexistent-id/trace")
    assert resp.status_code == 200
    assert resp.json() == []
