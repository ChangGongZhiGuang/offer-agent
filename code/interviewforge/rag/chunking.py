"""Chunking 策略 = 题干 / 参考答案分开切。

设计要点 (面试讲点):
- 题干用于检索 (Examiner 出题时做相似度匹配, 只能看到候选题面)。
- 参考答案用于评分 (Grader 评分时对照, 不能进入检索 query, 否则答案词会污染相似度)。
- 因此 RAG 的 "chunking" 在本项目里不是把长文切碎, 而是字段级的分离——只对 stem 做 embedding,
  不切碎 stem; 参考答案在评分阶段通过另一条通路 (SearchAdapter.last_reference_answer) 注入。
- 当前所有种子题题干都很短, 不需要把单个 stem 切碎。如果未来引入长篇题目 (如系统设计场景题),
  再回来考虑 stem 的二次切块。
"""
from __future__ import annotations

import hashlib

from interviewforge.rag.types import Question


def embeddable_text(question: Question) -> str:
    """只取题干做 embedding, 不含参考答案。"""
    return question.stem


def stem_hash(text: str) -> str:
    """题干内容的 sha1 十六进制摘要, 用于增量向量化时判断题干是否变更。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()
