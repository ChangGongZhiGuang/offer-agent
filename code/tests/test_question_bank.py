import os

import pytest

from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.types import Question


def _q(qid, difficulty="medium"):
    return Question(id=qid, role="后端", topic="redis",
                    stem=f"题干{qid}", answer=f"答案{qid}", difficulty=difficulty)


def test_inmemory_get_by_ids_preserves_order_and_skips_missing():
    bank = InMemoryQuestionBank()
    bank.add(_q("q1"))
    bank.add(_q("q2"))
    out = bank.get_by_ids(["q2", "q1", "missing"])
    assert [q.id for q in out] == ["q2", "q1"]


def test_inmemory_add_overwrites_same_id():
    bank = InMemoryQuestionBank()
    bank.add(_q("q1", difficulty="easy"))
    bank.add(_q("q1", difficulty="hard"))
    assert bank.get_by_ids(["q1"])[0].difficulty == "hard"


def _mysql_available():
    if not os.getenv("MYSQL_DATABASE"):
        return False
    try:
        import pymysql
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE"),
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _mysql_available(), reason="no reachable MySQL configured")
def test_mysql_bank_roundtrip():
    from interviewforge.rag.question_bank import MySQLQuestionBank
    bank = MySQLQuestionBank(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE"),
    )
    bank.ensure_schema()
    bank.clear()
    bank.add(_q("mysql-q1", difficulty="hard"))
    out = bank.get_by_ids(["mysql-q1"])
    assert out[0].id == "mysql-q1" and out[0].difficulty == "hard"
    assert out[0].answer == "答案mysql-q1"


def test_question_fu_field_defaults_empty():
    q = Question(id="q1", role="后端", topic="redis", stem="题干", answer="答案")
    assert q.fu == ""


def test_question_to_dict_includes_fu():
    q = Question(id="q1", role="后端", topic="redis", stem="题干", answer="答案", fu="深挖")
    assert q.to_dict()["fu"] == "深挖"


def test_question_from_dict_reads_fu():
    d = {"id": "q1", "role": "后端", "topic": "redis",
         "stem": "题干", "answer": "答案", "fu": "引导"}
    assert Question.from_dict(d).fu == "引导"


def test_question_from_dict_fu_defaults_empty_when_missing():
    d = {"id": "q1", "role": "后端", "topic": "redis", "stem": "题干", "answer": "答案"}
    assert Question.from_dict(d).fu == ""


def test_inmemory_list_all_returns_all_questions():
    bank = InMemoryQuestionBank()
    bank.add(_q("q1"))
    bank.add(_q("q2"))
    result = bank.list_all()
    assert {q.id for q in result} == {"q1", "q2"}


def test_inmemory_list_all_filters_by_role():
    bank = InMemoryQuestionBank()
    bank.add(Question(id="q1", role="后端", topic="redis", stem="s", answer="a"))
    bank.add(Question(id="q2", role="前端", topic="vue",  stem="s", answer="a"))
    result = bank.list_all(role="后端")
    assert len(result) == 1 and result[0].id == "q1"


def test_inmemory_list_all_empty_role_filter_returns_all():
    bank = InMemoryQuestionBank()
    bank.add(_q("q1"))
    bank.add(_q("q2"))
    assert len(bank.list_all(role=None)) == 2


def test_inmemory_delete_removes_question():
    bank = InMemoryQuestionBank()
    bank.add(_q("q1"))
    bank.add(_q("q2"))
    bank.delete("q1")
    assert bank.get_by_ids(["q1"]) == []
    assert len(bank.list_all()) == 1


def test_inmemory_delete_nonexistent_is_noop():
    bank = InMemoryQuestionBank()
    bank.delete("nonexistent")  # 不应抛异常
