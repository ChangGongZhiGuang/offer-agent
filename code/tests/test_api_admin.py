# tests/test_api_admin.py
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api.app import build_app
from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.auth.tokens import TokenStore
from interviewforge.auth.users import InMemoryUserBank
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.rag.position_bank import InMemoryPositionBank, Position
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore

_VOCAB = ["redis", "mysql"]


class _FakeModel:
    def chat(self, messages): return '{"score":3,"weakness_tags":[],"feedback":"ok"}'


def _make_store(tmp_path):
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    embed = make_keyword_embedder(_VOCAB)
    seed_questions(qb, vs, embed,
                   [Question(id="be-1", role="后端", topic="redis",
                              stem="如何实现分布式锁", answer="SETNX", difficulty="hard")])
    retriever = Retriever(vs, qb, embed)
    factory = SessionFactory(retriever=retriever, model_client=_FakeModel(),
                             base_dir=tmp_path)
    return SessionStore(factory)


def _seed_positions():
    pb = InMemoryPositionBank()
    pb.add(Position(id="p1", name="后端", color="#4F46E5"))
    pb.add(Position(id="p2", name="前端", color="#0284C7"))
    return pb


@pytest.fixture()
def deps(tmp_path):
    qb = InMemoryQuestionBank()
    pb = _seed_positions()
    ub = InMemoryUserBank()
    ts = TokenStore()
    app = build_app(_make_store(tmp_path), question_bank=qb, position_bank=pb,
                    user_bank=ub, token_store=ts)
    return {"app": app, "user_bank": ub, "token_store": ts}


def _client_as(deps, role="admin"):
    u = deps["user_bank"].create(f"{role}user", "h", role=role)
    token = deps["token_store"].issue(u.id)
    c = TestClient(deps["app"])
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


@pytest.fixture()
def client(deps):
    # 默认以管理员身份访问 (admin 端点需鉴权)
    return _client_as(deps, role="admin")


def test_list_questions_empty(client):
    r = client.get("/admin/questions")
    assert r.status_code == 200
    assert r.json() == []


def test_create_question(client):
    payload = {"id": "q1", "stem": "如何实现分布式锁", "role": "后端",
               "topic": "redis", "answer": "SETNX", "difficulty": "medium", "fu": "深挖"}
    r = client.post("/admin/questions", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q1"
    assert body["stem"] == "如何实现分布式锁"
    assert body["fu"] == "深挖"


def test_list_questions_after_create(client):
    client.post("/admin/questions",
                json={"id": "q1", "stem": "题干", "role": "后端",
                      "topic": "redis", "answer": "a", "difficulty": "medium", "fu": ""})
    r = client.get("/admin/questions")
    assert len(r.json()) == 1


def test_list_questions_filter_by_role(client):
    client.post("/admin/questions",
                json={"id": "q1", "stem": "后端题", "role": "后端",
                      "topic": "redis", "answer": "a", "difficulty": "medium", "fu": ""})
    client.post("/admin/questions",
                json={"id": "q2", "stem": "前端题", "role": "前端",
                      "topic": "vue", "answer": "b", "difficulty": "easy", "fu": ""})
    r = client.get("/admin/questions?role=后端")
    data = r.json()
    assert len(data) == 1 and data[0]["id"] == "q1"


def test_update_question(client):
    client.post("/admin/questions",
                json={"id": "q1", "stem": "旧题干", "role": "后端",
                      "topic": "redis", "answer": "旧答案", "difficulty": "easy", "fu": ""})
    r = client.put("/admin/questions/q1",
                   json={"id": "q1", "stem": "新题干", "role": "前端",
                         "topic": "vue", "answer": "新答案", "difficulty": "hard", "fu": "追问"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q1"
    assert body["stem"] == "新题干"
    assert body["role"] == "前端"
    assert body["difficulty"] == "hard"
    assert body["fu"] == "追问"
    # 列表里仍是一条且内容已更新 (没有新增)
    lst = client.get("/admin/questions").json()
    assert len(lst) == 1 and lst[0]["stem"] == "新题干"


def test_update_nonexistent_question_returns_404(client):
    r = client.put("/admin/questions/nope",
                   json={"id": "nope", "stem": "x", "role": "后端",
                         "topic": "t", "answer": "a", "difficulty": "medium", "fu": ""})
    assert r.status_code == 404


def test_delete_question(client):
    client.post("/admin/questions",
                json={"id": "q1", "stem": "题干", "role": "后端",
                      "topic": "t", "answer": "a", "difficulty": "medium", "fu": ""})
    r = client.delete("/admin/questions/q1")
    assert r.status_code == 200
    assert client.get("/admin/questions").json() == []


def test_delete_nonexistent_question_returns_404(client):
    r = client.delete("/admin/questions/nonexistent")
    assert r.status_code == 404


def test_list_positions(client):
    r = client.get("/admin/positions")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "后端" in names and "前端" in names


def test_create_position(client):
    r = client.post("/admin/positions", json={"name": "算法", "color": "#7C3AED"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "算法"
    assert body["color"] == "#7C3AED"
    assert body["id"]  # 有生成的 id


def test_delete_position(client):
    # 先建一个无题目的岗位再删
    pid = client.post("/admin/positions", json={"name": "算法", "color": "#7C3AED"}).json()["id"]
    r = client.delete(f"/admin/positions/{pid}")
    assert r.status_code == 200
    names = [p["name"] for p in client.get("/admin/positions").json()]
    assert "算法" not in names


def test_delete_nonexistent_position_returns_404(client):
    r = client.delete("/admin/positions/ghost")
    assert r.status_code == 404


def test_delete_position_cascades_questions(client):
    # 岗位 "后端" 下挂两道题, 删除岗位时题目一并删除
    client.post("/admin/questions",
                json={"id": "q1", "stem": "题1", "role": "后端",
                      "topic": "t", "answer": "a", "difficulty": "medium", "fu": ""})
    client.post("/admin/questions",
                json={"id": "q2", "stem": "题2", "role": "后端",
                      "topic": "t", "answer": "a", "difficulty": "easy", "fu": ""})
    # 另一岗位的题目不受影响
    client.post("/admin/questions",
                json={"id": "q3", "stem": "前端题", "role": "前端",
                      "topic": "t", "answer": "a", "difficulty": "easy", "fu": ""})
    p_be = next(p for p in client.get("/admin/positions").json() if p["name"] == "后端")
    r = client.delete(f"/admin/positions/{p_be['id']}")
    assert r.status_code == 200
    assert r.json()["removed_questions"] == 2
    assert "后端" not in [p["name"] for p in client.get("/admin/positions").json()]
    remaining = [q["id"] for q in client.get("/admin/questions").json()]
    assert remaining == ["q3"]  # 后端题被级联删除, 前端题保留


def test_admin_endpoints_absent_when_no_banks(tmp_path):
    """未注入 banks 时不挂载 admin 路由。"""
    app = build_app(_make_store(tmp_path))
    c = TestClient(app)
    assert c.get("/admin/questions").status_code == 404


def test_admin_questions_anonymous_401(deps):
    c = TestClient(deps["app"])
    assert c.get("/admin/questions").status_code == 401


def test_admin_questions_normal_user_403(deps):
    u = deps["user_bank"].create("norm", "h", role="user")
    token = deps["token_store"].issue(u.id)
    c = TestClient(deps["app"])
    c.headers.update({"Authorization": f"Bearer {token}"})
    assert c.get("/admin/questions").status_code == 403
    assert c.post("/admin/positions", json={"name": "算法"}).status_code == 403


class _RecordingSyncer:
    """记录 admin 题目增删改对应的向量索引同步调用。"""
    def __init__(self):
        self.upserted = []
        self.deleted = []

    def upsert(self, question):
        self.upserted.append(question.id)

    def delete(self, question_id):
        self.deleted.append(question_id)


@pytest.fixture()
def deps_with_syncer(tmp_path):
    qb = InMemoryQuestionBank()
    pb = _seed_positions()
    ub = InMemoryUserBank()
    ts = TokenStore()
    syncer = _RecordingSyncer()
    app = build_app(_make_store(tmp_path), question_bank=qb, position_bank=pb,
                    user_bank=ub, token_store=ts, vector_index_syncer=syncer)
    return {"app": app, "user_bank": ub, "token_store": ts, "syncer": syncer}


def test_question_crud_syncs_vector_index(deps_with_syncer):
    c = _client_as(deps_with_syncer, role="admin")
    syncer = deps_with_syncer["syncer"]
    # 新增 -> upsert
    c.post("/admin/questions", json={"id": "q1", "stem": "题干", "role": "后端",
                                     "topic": "t", "answer": "a",
                                     "difficulty": "medium", "fu": ""})
    assert syncer.upserted == ["q1"]
    # 更新 -> 再次 upsert 同 id
    c.put("/admin/questions/q1", json={"id": "q1", "stem": "新题干", "role": "后端",
                                       "topic": "t", "answer": "a",
                                       "difficulty": "medium", "fu": ""})
    assert syncer.upserted == ["q1", "q1"]
    # 删除 -> delete
    c.delete("/admin/questions/q1")
    assert syncer.deleted == ["q1"]


def test_position_delete_cascades_sync_delete(deps_with_syncer):
    c = _client_as(deps_with_syncer, role="admin")
    syncer = deps_with_syncer["syncer"]
    c.post("/admin/questions", json={"id": "q1", "stem": "题1", "role": "后端",
                                     "topic": "t", "answer": "a",
                                     "difficulty": "medium", "fu": ""})
    p_be = next(p for p in c.get("/admin/positions").json() if p["name"] == "后端")
    c.delete(f"/admin/positions/{p_be['id']}")
    # 级联删后端题目时也同步删了向量
    assert "q1" in syncer.deleted
