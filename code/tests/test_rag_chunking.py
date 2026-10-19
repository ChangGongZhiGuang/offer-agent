from interviewforge.rag.chunking import embeddable_text
from interviewforge.rag.types import Question, difficulty_rank


def test_question_roundtrip():
    q = Question(id="1", role="后端", topic="redis", stem="s", answer="a", difficulty="hard")
    assert Question.from_dict(q.to_dict()) == q


def test_difficulty_rank_orders_and_defaults():
    assert difficulty_rank("easy") < difficulty_rank("medium") < difficulty_rank("hard")
    assert difficulty_rank("unknown") == difficulty_rank("medium")


def test_embeddable_text_is_stem_only():
    q = Question(id="1", role="后端", topic="redis",
                 stem="如何实现分布式锁", answer="用 SETNX 加过期时间", difficulty="medium")
    text = embeddable_text(q)
    assert text == "如何实现分布式锁"
    assert "SETNX" not in text


