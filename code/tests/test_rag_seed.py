from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import SEED_QUESTIONS, seed_questions
from interviewforge.rag.vector_store import InMemoryVectorStore


def _embedder(texts):
    return [[float(len(t)), 1.0] for t in texts]


def test_seed_questions_nonempty():
    assert len(SEED_QUESTIONS) >= 3


def test_seed_populates_both_stores():
    bank = InMemoryQuestionBank()
    vs = InMemoryVectorStore()
    n = seed_questions(bank, vs, _embedder)
    assert n == len(SEED_QUESTIONS)
    ids = [q.id for q in SEED_QUESTIONS]
    assert len(bank.get_by_ids(ids)) == n


def test_seeded_questions_are_retrievable():
    bank = InMemoryQuestionBank()
    vs = InMemoryVectorStore()
    seed_questions(bank, vs, _embedder)
    got = Retriever(vs, bank, _embedder).retrieve_one(SEED_QUESTIONS[0].stem, top_k=10)
    assert got is not None


def test_seed_embeds_stem_not_answer():
    bank = InMemoryQuestionBank()
    vs = InMemoryVectorStore()
    captured = {}
    def spy_embedder(texts):
        captured["texts"] = texts
        return [[1.0, 0.0] for _ in texts]
    seed_questions(bank, vs, spy_embedder)
    stems = {q.stem for q in SEED_QUESTIONS}
    answers = {q.answer for q in SEED_QUESTIONS}
    assert set(captured["texts"]) == stems
    assert not (set(captured["texts"]) & answers)
