"""最小 Python 驱动 (无 CLI): 把所有模块装好跑一场可复现的面试。供集成测试 + demo。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from interviewforge.loop.adapter import SearchAdapter
from interviewforge.loop.machine import InterviewLoop
from interviewforge.loop.planner import RulePlanner
from interviewforge.loop.types import Bounds
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.working import WorkingMemory
from interviewforge.persistence.transcript import Transcript
from interviewforge.rag.question_bank import InMemoryQuestionBank
from interviewforge.rag.retriever import Retriever
from interviewforge.rag.seed import seed_questions
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import InMemoryVectorStore
from interviewforge.subagents.examiner import Examiner
from interviewforge.subagents.grader import Grader
from interviewforge.tools.interview_tools import build_default_registry


def make_keyword_embedder(vocab: list[str]) -> Callable[[list[str]], list[list[float]]]:
    """确定性词频 embedder: 维度=vocab, 每维=该词(小写)出现次数。无需真实 LLM。"""
    def _embed(texts: list[str]) -> list[list[float]]:
        return [[float(t.lower().count(w.lower())) for w in vocab] for t in texts]
    return _embed


class _FakeModel:
    """离线桩模型: chat 恒返回固定 reply。"""
    def __init__(self, reply: str):
        self.reply = reply

    def chat(self, messages) -> str:
        return self.reply


_EXAM_REPLY = ('{"question": "PLACEHOLDER", "rubric": "看关键点是否覆盖", '
               '"expected_points": ["要点1", "要点2"]}')
_GRADE_REPLY = '{"score": 4, "weakness_tags": ["边界条件"], "feedback": "整体不错, 注意边界"}'

_DEFAULT_VOCAB = ["redis", "mysql", "并发", "分布式", "锁", "索引", "缓存", "击穿"]


def run_demo_interview(
    work_dir: str | Path,
    *,
    role: str,
    topics: list[str],
    answers: list[str],
    questions: list[Question],
    profile: str = "",
    vocab: list[str] | None = None,
) -> tuple[dict, InterviewLoop]:
    """跑一场面试: 按 topics 逐题 出题->收答->评分, 最后出报告。"""
    work_dir = Path(work_dir)
    embed = make_keyword_embedder(vocab or _DEFAULT_VOCAB)

    memory = MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(work_dir / "episodic.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([]),
    )
    vector_store, question_bank = InMemoryVectorStore(), InMemoryQuestionBank()
    seed_questions(question_bank, vector_store, embed, questions)
    retriever = Retriever(vector_store, question_bank, embed)

    adapter = SearchAdapter(retriever, memory)
    registry = build_default_registry(memory, retriever=adapter)
    examiner = Examiner(_FakeModel(_EXAM_REPLY), registry)
    grader = Grader(_FakeModel(_GRADE_REPLY), registry)

    loop = InterviewLoop(
        memory=memory, examiner=examiner, grader=grader, planner=RulePlanner(),
        registry=registry, search_adapter=adapter,
        transcript=Transcript(work_dir / "transcript.jsonl"),
        bounds=Bounds(max_questions=len(topics), max_turns=max(len(topics) + 1, 2)),
    )
    loop.start(role=role, topic=topics[0], profile=profile)

    for topic, answer in zip(topics, answers):
        loop.state.topic = topic
        if loop.ask_question() is None:
            break
        loop.submit_answer(answer)

    report = loop.finish()
    return report, loop
