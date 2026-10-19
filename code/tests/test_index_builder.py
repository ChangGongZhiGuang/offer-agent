from interviewforge.rag.index_builder import build_index_from_bank
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.types import Question
from interviewforge.loop.driver import make_keyword_embedder


def test_build_index_covers_all_bank_questions():
    qb = InMemoryQuestionBank()
    qb.add(Question(id="q1", role="后端", topic="redis", stem="redis 锁", answer="a", difficulty="hard"))
    qb.add(Question(id="q2", role="后端", topic="mysql", stem="mysql 索引", answer="b", difficulty="medium"))
    r = build_index_from_bank(qb, make_keyword_embedder(["redis", "mysql"]))
    # 题库里两道题都进了向量索引 (admin 新增的题也能被检索到, 不再只覆盖 SEED)
    hit = r.retrieve_one("mysql", where={"role": "后端"})
    assert hit is not None and hit.id == "q2"
