"""会话装配与生命周期: 每会话一台隔离 InterviewLoop。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from interviewforge.context.assembler import ContextAssembler
from interviewforge.context.compaction import build_pipeline
from interviewforge.loop.adapter import SearchAdapter
from interviewforge.loop.machine import InterviewLoop
from interviewforge.loop.planner import RulePlanner
from interviewforge.loop.types import Bounds
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.memory.working import WorkingMemory
from interviewforge.persistence.transcript import Transcript
from interviewforge.rag.retriever import Retriever
from interviewforge.subagents.examiner import Examiner
from interviewforge.subagents.grader import Grader
from interviewforge.tools.interview_tools import build_default_registry


class SessionFactory:
    """按会话装配隔离的 InterviewLoop。retriever / model_client 跨会话共享。

    每调用一次 build() 就组装一套完整的面试循环 (出题 → 作答 → 评分),
    各会话之间的 RAG 检索器与 LLM 客户端共享以节省资源, 但内存/工具/子 Agent
    完全独立, 避免状态串扰。
    """

    def __init__(self, *, retriever: Retriever, model_client, base_dir,
                 rules: list[dict] | None = None, token_budget: int = 24000,
                 search_adapter_factory: Callable | None = None,
                 jd_lookup: Callable | None = None, skill_registry=None):
        self.retriever = retriever
        self.model_client = model_client
        self.base_dir = Path(base_dir)
        self.rules = rules or []
        self.token_budget = token_budget
        # 默认每会话 new SearchAdapter(retriever, memory); MCP 模式注入自己的工厂。
        self.search_adapter_factory = search_adapter_factory or (
            lambda memory: SearchAdapter(self.retriever, memory))
        self.jd_lookup = jd_lookup
        from interviewforge.skills.registry import SkillRegistry
        self.skill_registry = skill_registry or SkillRegistry()

    def build(self, *, session_id: str, role: str, topic: str,
              profile: str = "", num_questions: int = 3,
              jd_keywords: list[str] | None = None,
              dimension: str | None = None,
              profile_struct=None) -> InterviewLoop:
        """创建一个完整面试会话。

        步骤:
          1) 技能维度匹配 → 2) 面试计划生成 → 3) 四层记忆系统初始化
          → 4) 工具注册 → 5) 出题/评分子 Agent 装载 → 6) 状态机启动
        """
        from interviewforge.loop.session_plan import build_session_plan
        from interviewforge.resume.types import CandidateProfile

        # ── 1) 角色 × 技能维度匹配 ─────────────────────────────────
        jd_keywords = list(jd_keywords or [])
        query = " ".join([role, topic, *jd_keywords])
        methodology, dims = self.skill_registry.methodology_for(query)

        # ── 2) 面试计划: 按画像与维度分配小题数, 确保覆盖所有考察面 ──
        profile_struct = profile_struct or CandidateProfile()
        plan = build_session_plan(profile_struct, dims, num_questions,
                                  fallback_topic=topic)

        # ── 3) 记忆系统(每会话隔离) ──────────────────────────────────
        #    工作记忆: 当前轮次; 情节记忆: 已回答题目文件; 语义记忆: 画像/知识; 程序记忆: 规则
        sdir = self.base_dir / session_id
        memory = MemoryService(
            working=WorkingMemory(),
            episodic=EpisodicMemory(sdir / "episodic.jsonl"),
            semantic=SemanticMemory(InMemorySemanticBackend()),
            procedural=ProceduralMemory(self.rules),
        )
        # 画像入 semantic memory (跨阶段可召回; ContextAssembler 读它注入子 Agent 系统提示)
        # 结构化画像优先; 未解析简历时回退到用户填的自由文本画像 (否则出题忽略简历)
        profile_text = profile_struct.to_prompt().strip() or (profile or "").strip()
        if profile_text.strip():
            memory.remember(MemoryItem(kind=MemoryKind.SEMANTIC,
                                       content={"role": role, "fact": profile_text}))

        # ── 4) 工具注册 ─────────────────────────────────────────────
        #    搜索适配器包装 RAG 检索 (直连或 MCP); registry 装载面试专用工具集
        adapter = self.search_adapter_factory(memory)
        registry = build_default_registry(memory, retriever=adapter,
                                          jd_lookup=self.jd_lookup,
                                          model_client=self.model_client,
                                          profile_text=profile_text)
        # ContextAssembler: 子 Agent 系统提示经它组入 procedural 规则 + semantic 画像
        assembler = ContextAssembler(self.token_budget)

        # ── 5) 子 Agent ─────────────────────────────────────────────
        #    Examiner: 出题 + 追问; Grader: 评分 + 反馈 (分别调用 LLM)
        examiner = Examiner(self.model_client, registry, methodology=methodology,
                            memory=memory, assembler=assembler, role=role)
        grader = Grader(self.model_client, registry,
                        memory=memory, assembler=assembler, role=role)
        # 五层压缩管道: 长会话超 budget 时由状态机 _maybe_compact 触发
        pipeline = build_pipeline(model_client=self.model_client,
                                  token_budget=self.token_budget)

        # ── 6) InterviewLoop 状态机 ─────────────────────────────────
        #    串联出题→回答→评分→循环, 由 loop.ask_question / submit_answer 驱动
        loop = InterviewLoop(
            memory=memory, examiner=examiner, grader=grader, planner=RulePlanner(),
            registry=registry, search_adapter=adapter,
            transcript=Transcript(sdir / "transcript.jsonl"),
            bounds=Bounds(max_questions=num_questions),
            pipeline=pipeline,
            token_budget=self.token_budget,
        )
        loop.start(role=role, topic=topic, profile=profile_text,
                   jd_keywords=jd_keywords, dimension=dimension)
        loop.state.session_plan = plan
        loop.state.profile_struct = profile_struct
        return loop


class SessionStore:
    """进程内会话表: session_id → InterviewLoop。

    HTTP 接口无状态, 每次请求通过 session_id 从该表取出对应的 InterviewLoop
    继续执行, 等价于内存版 session store (重启即失)。
    """

    def __init__(self, factory: SessionFactory):
        self._factory = factory
        self._sessions: dict[str, InterviewLoop] = {}
        # session_id -> user_id (创建会话时若已登录则绑定; 未登录为 None)
        self._owners: dict[str, str | None] = {}

    @property
    def base_dir(self) -> Path:
        """会话工作目录的根路径, 供 trace 端点拼文件路径。"""
        return self._factory.base_dir

    def create(self, *, role: str, topic: str, profile: str = "",
               num_questions: int = 3, jd_keywords: list[str] | None = None,
               profile_struct=None, user_id: str | None = None) -> str:
        """创建新会话: 委托 factory.build(), 返回随机 session_id。

        user_id 非空表示登录状态下发起的面试, 记录归属供 finish 时写历史。
        """
        sid = uuid4().hex
        self._sessions[sid] = self._factory.build(
            session_id=sid, role=role, topic=topic, profile=profile,
            num_questions=num_questions, jd_keywords=jd_keywords,
            profile_struct=profile_struct)
        self._owners[sid] = user_id
        return sid

    def get(self, session_id: str) -> InterviewLoop | None:
        """按 ID 取会话; 不存在则返回 None (由调用方抛 404)。"""
        return self._sessions.get(session_id)

    def get_owner(self, session_id: str) -> str | None:
        """取会话归属的 user_id; 未登录发起或不存在则为 None。"""
        return self._owners.get(session_id)

    def remove(self, session_id: str) -> None:
        """销毁会话 (释放内存, 但情节记忆文件保留在磁盘)。"""
        self._sessions.pop(session_id, None)
        self._owners.pop(session_id, None)
