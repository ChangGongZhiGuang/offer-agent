import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api import factory


def test_create_app_is_callable():
    assert callable(factory.create_app)


def test_build_inmemory_retriever_seeds(monkeypatch):
    # 用 fake embedder 验证灌库装配逻辑, 不触发真实网络
    from interviewforge.loop.driver import make_keyword_embedder
    retriever = factory.build_inmemory_retriever(
        make_keyword_embedder(["redis", "mysql", "并发", "动态规划"]))
    # SEED_QUESTIONS 含 be-1(redis); 检索应能取到
    q = retriever.retrieve_one("后端 redis", top_k=5)
    assert q is not None


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"),
                    reason="needs real OPENAI_API_KEY for end-to-end smoke")
def test_real_smoke_create_and_ask(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIEWFORGE_WORKDIR", str(tmp_path))
    app = factory.create_app()
    client = TestClient(app)
    sid = client.post("/sessions", json={"role": "后端", "topic": "redis",
                                         "num_questions": 1}).json()["session_id"]
    body = client.post(f"/sessions/{sid}/ask").json()
    assert body["done"] is False and body["question"]
