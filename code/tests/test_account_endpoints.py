# tests/test_account_endpoints.py
"""修改密码 / 注销账号 (软删除) 端点与数据层单元测试。"""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api.app import build_app
from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.auth.password import hash_password, verify_password
from interviewforge.auth.tokens import TokenStore
from interviewforge.auth.users import InMemoryUserBank
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore

_VOCAB = ["redis"]


class _FakeModel:
    def chat(self, messages):
        return '{"score":3,"weakness_tags":[],"feedback":"ok"}'


def _make_store(tmp_path):
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    embed = make_keyword_embedder(_VOCAB)
    seed_questions(qb, vs, embed,
                   [Question(id="be-1", role="后端", topic="redis",
                             stem="如何实现分布式锁", answer="SETNX",
                             difficulty="hard")])
    retriever = Retriever(vs, qb, embed)
    factory = SessionFactory(retriever=retriever, model_client=_FakeModel(),
                             base_dir=tmp_path)
    return SessionStore(factory)


@pytest.fixture()
def deps(tmp_path):
    ub = InMemoryUserBank()
    ts = TokenStore()
    app = build_app(_make_store(tmp_path), question_bank=InMemoryQuestionBank(),
                    user_bank=ub, token_store=ts)
    return {"app": app, "user_bank": ub, "token_store": ts}


def _client(deps, token=None):
    c = TestClient(deps["app"])
    if token:
        c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def _register(deps, username="alice", password="secret123"):
    r = _client(deps).post("/auth/register",
                           json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _make_root(deps, username="root0", password="rootpass123"):
    u = deps["user_bank"].create(username, hash_password(password), role="root")
    return u, deps["token_store"].issue(u.id)


# ── 数据层单元: InMemoryUserBank 新方法 + TokenStore.revoke_all ──

def test_inmemory_bank_set_password_and_status():
    ub = InMemoryUserBank()
    u = ub.create("alice", hash_password("secret123"))
    assert ub.set_password_hash(u.id, hash_password("newsecret")) is True
    assert verify_password("newsecret", ub.get_by_id(u.id).password_hash)
    assert ub.set_status(u.id, "deleted") is True
    assert ub.get_by_username("alice").status == "deleted"  # 查询不过滤 deleted
    assert ub.set_password_hash("no-such-id", "x") is False
    assert ub.set_status("no-such-id", "active") is False
    # to_dict 带出 status
    assert ub.get_by_id(u.id).to_dict()["status"] == "deleted"


def test_token_store_revoke_all_multi_device():
    ts = TokenStore()
    t1, t2 = ts.issue("u1"), ts.issue("u1")
    other = ts.issue("u2")
    assert ts.revoke_all("u1") == 2
    assert ts.resolve(t1) is None and ts.resolve(t2) is None
    assert ts.resolve(other) == "u2"
    assert ts.revoke_all("nobody") == 0


# ── 修改密码 ──────────────────────────────────────────────────

def test_change_password_requires_auth(deps):
    r = _client(deps).post("/auth/change-password",
                           json={"old_password": "x", "new_password": "yyyyyy"})
    assert r.status_code == 401


def test_change_password_validation_and_revocation(deps):
    token = _register(deps)
    c = _client(deps, token)
    # 旧密码错 → 401
    r = c.post("/auth/change-password",
               json={"old_password": "wrong-pass", "new_password": "brandnew1"})
    assert r.status_code == 401
    # 新密码太短 → 400
    r = c.post("/auth/change-password",
               json={"old_password": "secret123", "new_password": "short"})
    assert r.status_code == 400
    # 新旧相同 → 400
    r = c.post("/auth/change-password",
               json={"old_password": "secret123", "new_password": "secret123"})
    assert r.status_code == 400
    # 成功 → 全部 token 吊销
    r = c.post("/auth/change-password",
               json={"old_password": "secret123", "new_password": "brandnew1"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert _client(deps, token).get("/auth/me").status_code == 401
    # 旧密码登录失败, 新密码可登录
    anon = _client(deps)
    assert anon.post("/auth/login",
                     json={"username": "alice", "password": "secret123"}).status_code == 401
    r = anon.post("/auth/login",
                  json={"username": "alice", "password": "brandnew1"})
    assert r.status_code == 200


# ── 自助注销 ──────────────────────────────────────────────────

def test_deactivate_requires_correct_password(deps):
    token = _register(deps)
    r = _client(deps, token).post("/auth/deactivate", json={"password": "wrong"})
    assert r.status_code == 401
    # 未注销, 仍可登录态访问
    assert _client(deps, token).get("/auth/me").status_code == 200


def test_deactivate_self_soft_deletes_and_blocks_login(deps):
    token = _register(deps)
    r = _client(deps, token).post("/auth/deactivate", json={"password": "secret123"})
    assert r.status_code == 200
    # token 全部吊销: 旧 token 的登录态接口 401
    assert _client(deps, token).get("/auth/me").status_code == 401
    # 密码正确也登录被拒 403 (明确提示已注销)
    r = _client(deps).post("/auth/login",
                           json={"username": "alice", "password": "secret123"})
    assert r.status_code == 403
    assert "已注销" in r.json()["detail"]
    # 同名可再注册? username UNIQUE → 409, 软删除保留占位 (预期行为)
    r = _client(deps).post("/auth/register",
                           json={"username": "alice", "password": "secret123"})
    assert r.status_code == 409


# ── root 注销/恢复他人 ────────────────────────────────────────

def test_root_cannot_delete_self_or_other_root(deps):
    root, root_token = _make_root(deps)
    c = _client(deps, root_token)
    r = c.delete(f"/admin/users/{root.id}")
    assert r.status_code == 400 and "自助" in r.json()["detail"]
    # 另一个 root 账号不可注销
    other_root = deps["user_bank"].create("root2", hash_password("rootpass123"),
                                          role="root")
    r = c.delete(f"/admin/users/{other_root.id}")
    assert r.status_code == 400 and "超级管理员" in r.json()["detail"]


def test_root_deletes_user_then_restore(deps):
    root, root_token = _make_root(deps)
    user_token = _register(deps)
    u = deps["user_bank"].get_by_username("alice")
    admin = _client(deps, root_token)

    r = admin.delete(f"/admin/users/{u.id}")
    assert r.status_code == 200
    # 被注销者 token 吊销 + 登录被拒
    assert _client(deps, user_token).get("/auth/me").status_code == 401
    assert _client(deps).post("/auth/login", json={
        "username": "alice", "password": "secret123"}).status_code == 403
    # 列表可见 status=deleted (供恢复)
    rows = admin.get("/admin/users").json()
    alice = next(x for x in rows if x["username"] == "alice")
    assert alice["status"] == "deleted"
    # 恢复后重新可登录
    r = admin.post(f"/admin/users/{u.id}/restore")
    assert r.status_code == 200 and r.json()["status"] == "active"
    r = _client(deps).post("/auth/login",
                           json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200


def test_admin_users_list_carries_status_default(deps):
    root, root_token = _make_root(deps)
    _register(deps)
    rows = _client(deps, root_token).get("/admin/users").json()
    assert all(x["status"] == "active" for x in rows)


def test_non_root_cannot_delete_or_restore(deps):
    # 普通用户: 401/403
    user_token = _register(deps)
    u = deps["user_bank"].get_by_username("alice")
    c = _client(deps, user_token)
    assert c.delete(f"/admin/users/{u.id}").status_code == 403
    assert c.post(f"/admin/users/{u.id}/restore").status_code == 403
    # admin 角色也不行 (仅 root)
    adm = deps["user_bank"].create("adm0", hash_password("admpass123"), role="admin")
    ca = _client(deps, deps["token_store"].issue(adm.id))
    assert ca.delete(f"/admin/users/{u.id}").status_code == 403
    # 未登录: 401
    anon = _client(deps)
    assert anon.delete(f"/admin/users/{u.id}").status_code == 401
    # 注销不存在的人 → 404
    root, root_token = _make_root(deps)
    assert _client(deps, root_token).delete("/admin/users/nope").status_code == 404
