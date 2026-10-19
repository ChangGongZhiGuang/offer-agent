"""Retriever: 题库语义检索链。embed→向量检索→取原文→去重→难度重排→选一题。"""
from __future__ import annotations

from typing import Callable

from interviewforge.rag.question_bank import QuestionBank
from interviewforge.rag.types import Question, difficulty_rank
from interviewforge.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, vector_store: VectorStore, question_bank: QuestionBank,
                 embedder: Callable[[list[str]], list[list[float]]]):
        self.vector_store = vector_store
        self.question_bank = question_bank
        self.embedder = embedder

    def retrieve_one(self, query_text: str, *, top_k: int = 5,
                     asked_ids: list[str] | None = None,
                     target_difficulty: str | None = None,
                     where: dict | None = None) -> Question | None:
        vec = self.embedder([query_text])[0]                      # ② embedding
        candidate_ids = self.vector_store.query(
            vec, top_k, where=where)                              # ③ 向量检索 (含元数据硬过滤)
        questions = self.question_bank.get_by_ids(candidate_ids)  # ④ 取原文 (保序)

        asked = set(asked_ids or [])                              # ⑤ episodic 去重
        questions = [q for q in questions if q.id not in asked]

        if target_difficulty is not None:                         # ⑤ 难度重排 (稳定)
            target = difficulty_rank(target_difficulty)
            questions.sort(key=lambda q: abs(difficulty_rank(q.difficulty) - target))

        return questions[0] if questions else None                # ⑥ 选一题

    def retrieve_many(self, query_text: str, *, top_k: int = 5,
                      asked_ids: list[str] | None = None,
                      target_difficulty: str | None = None,
                      where: dict | None = None) -> list[Question]:
        """返回去重 + 难度重排后的候选列表 (供 server 端返回多条, 客户端再选)。"""
        vec = self.embedder([query_text])[0]
        candidate_ids = self.vector_store.query(vec, top_k, where=where)
        questions = self.question_bank.get_by_ids(candidate_ids)
        asked = set(asked_ids or [])
        questions = [q for q in questions if q.id not in asked]
        if target_difficulty is not None:
            target = difficulty_rank(target_difficulty)
            questions.sort(key=lambda q: abs(difficulty_rank(q.difficulty) - target))
        return questions
