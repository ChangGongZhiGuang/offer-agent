"""岗位广场 / 角色管理 (RBAC) 的 HTTP 端到端测试 (InMemory banks)。"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from interviewforge.api.app import build_app
from interviewforge.api.session import SessionFactory, SessionStore
from interviewforge.auth.tokens import TokenStore
from interviewforge.auth.users import InMemoryUserBank
from interviewforge.jobs.seed import SEED_JOBS
from interviewforge.jobs.store import InMemoryJobStore, Job
from interviewforge.loop.driver import make_keyword_embedder
from interviewforge.rag.position_bank import InMemoryPositionBank
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.vector_store import InMemoryVectorStore


class _FakeModel:
    def chat(self, messages): return '{"score":3,"weakness_tags":[],"feedback":"ok"}'


def _make_store(tmp_path):
    from interviewforge.rag.retriever import Retriever
    embed = make_keyword_embedder(["redis", "mysql"])
    vs, qb = InMemoryVectorStore(), InMemoryQuestionBank()
    retriever = Retriever(vs, qb, embed)
    factory = SessionFactory(retriever=retriever, model_client=_FakeModel(),
                             base_dir=tmp_path)
    return SessionStore(factory)


@pytest.fixture()
def deps(tmp_path):
    ub = InMemoryUserBank()
    ts = TokenStore()
    jb = InMemoryJobStore()
    for d in SEED_JOBS:
        jb.add(Job(**d))
    app = build_app(_make_store(tmp_path), question_bank=InMemoryQuestionBank(),
                    position_bank=InMemoryPositionBank(), user_bank=ub,
                    token_store=ts, job_store=jb)
    return {"app": app, "user_bank": ub, "token_store": ts, "job_store": jb}


def _client(deps, role=None, username=None):
    """role=None → 匿名; 否则创建该角色用户并注入 Bearer。"""
    c = TestClient(deps["app"])
    if role is None:
        return c
    u = deps["user_bank"].create(username or f"{role}u", "h", role=role)
    token = deps["token_store"].issue(u.id)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


_JOB_PAYLOAD = {"category": "后端", "title": "新岗位", "company": "某司",
                "salary": "20-40K", "salary_min": 20, "city": "上海",
                "exp": "3-5 年", "skills": ["Go"], "requirements": ["熟练 Go"]}


# ── 岗位广场: 浏览公开 ────────────────────────────────
def test_get_jobs_public_returns_seed(deps):
    r = _client(deps).get("/jobs")
    assert r.status_code == 200
    assert len(r.json()) == len(SEED_JOBS)


def test_create_job_anonymous_401(deps):
    assert _client(deps).post("/jobs", json=_JOB_PAYLOAD).status_code == 401


def test_create_job_normal_user_403(deps):
    assert _client(deps, role="user").post("/jobs", json=_JOB_PAYLOAD).status_code == 403


def test_create_job_admin_200(deps):
    r = _client(deps, role="admin").post("/jobs", json=_JOB_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "新岗位" and body["id"]
    assert len(_client(deps).get("/jobs").json()) == len(SEED_JOBS) + 1


def test_create_job_empty_title_400(deps):
    payload = {**_JOB_PAYLOAD, "title": "   "}
    assert _client(deps, role="admin").post("/jobs", json=payload).status_code == 400


def test_update_and_delete_job_admin(deps):
    admin = _client(deps, role="admin")
    jid = admin.post("/jobs", json=_JOB_PAYLOAD).json()["id"]
    upd = {**_JOB_PAYLOAD, "title": "改名后"}
    assert admin.put(f"/jobs/{jid}", json=upd).json()["title"] == "改名后"
    assert admin.delete(f"/jobs/{jid}").status_code == 200
    assert admin.delete(f"/jobs/{jid}").status_code == 404


def test_update_nonexistent_job_404(deps):
    assert _client(deps, role="admin").put(
        "/jobs/nope", json=_JOB_PAYLOAD).status_code == 404


def test_root_also_can_manage_jobs(deps):
    # root 天然具备 admin 能力
    assert _client(deps, role="root").post("/jobs", json=_JOB_PAYLOAD).status_code == 200


# ── 用户 / 角色管理 (仅 root) ─────────────────────────
def test_list_users_requires_root(deps):
    assert _client(deps).get("/admin/users").status_code == 401
    assert _client(deps, role="user").get("/admin/users").status_code == 403
    assert _client(deps, role="admin").get("/admin/users").status_code == 403
    assert _client(deps, role="root").get("/admin/users").status_code == 200


def test_root_promote_and_demote(deps):
    root = _client(deps, role="root", username="root")
    target = deps["user_bank"].create("alice", "h", role="user")
    r = root.put(f"/admin/users/{target.id}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert deps["user_bank"].get_by_id(target.id).role == "admin"
    root.put(f"/admin/users/{target.id}/role", json={"role": "user"})
    assert deps["user_bank"].get_by_id(target.id).role == "user"


def test_cannot_change_self_or_root(deps):
    root_client = _client(deps, role="root", username="bossroot")
    boss = deps["user_bank"].get_by_username("bossroot")
    # 改自己
    assert root_client.put(f"/admin/users/{boss.id}/role",
                           json={"role": "user"}).status_code == 400
    # 改另一个 root
    other_root = deps["user_bank"].create("root2", "h", role="root")
    assert root_client.put(f"/admin/users/{other_root.id}/role",
                           json={"role": "user"}).status_code == 400


def test_set_role_invalid_value_400(deps):
    root = _client(deps, role="root")
    target = deps["user_bank"].create("dave", "h", role="user")
    assert root.put(f"/admin/users/{target.id}/role",
                    json={"role": "superuser"}).status_code == 400


def test_set_role_missing_user_404(deps):
    root = _client(deps, role="root")
    assert root.put("/admin/users/ghost/role", json={"role": "admin"}).status_code == 404


# ── 登录 / me 返回 role ───────────────────────────────
def test_register_defaults_role_user(deps):
    c = _client(deps)
    # 需要一个已挂载 /auth 的 app: user_bank + token_store 已在 deps
    r = c.post("/auth/register", json={"username": "newbie", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "user"
    token = r.json()["token"]
    me = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "user"
