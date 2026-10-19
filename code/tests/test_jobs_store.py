"""岗位广场存储 (InMemory) 与 Job 数据模型单测。"""
from __future__ import annotations

from interviewforge.jobs.store import InMemoryJobStore, Job


def _job(jid="j1", **kw):
    base = dict(id=jid, category="后端", title="后端工程师", company="某司",
                salary="20-40K", salary_min=20, city="上海", exp="3-5 年",
                skills=["Redis", "MySQL"], requirements=["精通 Redis"])
    base.update(kw)
    return Job(**base)


def test_add_get_list():
    store = InMemoryJobStore()
    assert store.list_all() == []
    j = _job()
    store.add(j)
    assert store.get("j1") is j
    assert len(store.list_all()) == 1


def test_add_same_id_overwrites():
    store = InMemoryJobStore()
    store.add(_job(title="旧标题"))
    store.add(_job(title="新标题"))
    assert len(store.list_all()) == 1
    assert store.get("j1").title == "新标题"


def test_delete():
    store = InMemoryJobStore()
    store.add(_job())
    assert store.delete("j1") is True
    assert store.delete("j1") is False
    assert store.list_all() == []


def test_to_from_dict_roundtrip():
    j = _job()
    d = j.to_dict()
    assert d["skills"] == ["Redis", "MySQL"]
    j2 = Job.from_dict(d)
    assert j2 == j


def test_from_dict_defaults():
    j = Job.from_dict({"id": "x"})
    assert j.category == "" and j.skills == [] and j.salary_min == 0
