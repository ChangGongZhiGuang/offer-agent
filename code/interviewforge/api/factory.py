"""生产装配: 真实 ModelClient + 真实 embedding 灌库 + CORS。供 uvicorn --factory。

环境变量 INTERVIEWFORGE_USE_MCP=1 时启用 MCP 路径:
  search_questions / lookup_jd 通过 stdio MCP server 走外部进程, 主进程不直接读题库。
"""
from __future__ import annotations

# ── 标准库 ──────────────────────────────────────────────────────────────────
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

logger = logging.getLogger("interviewforge")

# ── 三方库 ──────────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── 内部模块（顶层导入，后续参数化构建 retriever 时再懒导入 MySQL 分支） ─────
from interviewforge.api.app import build_app                              # 挂载所有 HTTP 路由
from interviewforge.api.session import SessionFactory, SessionStore       # 会话层 (有界性/持久化)
from interviewforge.config.settings import load_settings                  # .env + roles.yaml -> Settings
from interviewforge.model_client import ModelClient                       # OpenAI 兼容 LLM / Embedding 客户端
from interviewforge.rag.question_bank import InMemoryQuestionBank         # 题库: 内存版 (MySQL 版在函数内懒导)
from interviewforge.rag.retriever import Retriever                        # RAG 检索器: 向量召回 + 题库查询
from interviewforge.rag.seed import SEED_QUESTIONS, seed_questions        # 默认种子题 / 灌库函数
from interviewforge.rag.vector_store import InMemoryVectorStore


# ═══════════════════════════════════════════════════════════════════════════
#  向量库选型 (内存 / Chroma 持久)
# ═══════════════════════════════════════════════════════════════════════════

def is_chroma_mode() -> bool:
    """是否启用持久化 Chroma 向量库 (INTERVIEWFORGE_VECTOR_STORE=chroma)。"""
    return os.getenv("INTERVIEWFORGE_VECTOR_STORE", "memory").strip().lower() == "chroma"


def build_vector_store():
    """按 INTERVIEWFORGE_VECTOR_STORE 返回向量库实例。

    chroma: 持久化到 INTERVIEWFORGE_CHROMA_PATH (默认 .interviewforge_chroma),
            collection=questions; 两条建索引路径 (MCP / 非 MCP) 共享同一目录。
    memory: 每次进程重建的 InMemoryVectorStore (默认, 不依赖 chromadb)。
    """
    if is_chroma_mode():
        from interviewforge.rag.vector_store import ChromaVectorStore
        path = os.getenv("INTERVIEWFORGE_CHROMA_PATH", ".interviewforge_chroma")
        return ChromaVectorStore(path=path, collection_name="questions")
    return InMemoryVectorStore()


class QuestionIndexSyncer:
    """admin 题目增删改时对向量库做单题增量同步 (仅 chroma 模式需要)。"""

    def __init__(self, vector_store, embedder):
        self._store = vector_store
        self._embed = embedder

    def upsert(self, question) -> None:
        # 元数据复用 index_builder.metadata_for 单源构造, 与 ensure_index 的
        # 整体比对保持一致, 避免字段清单不同步导致重启时重复 embedding。
        from interviewforge.rag.chunking import embeddable_text
        from interviewforge.rag.index_builder import metadata_for
        self._store.upsert(
            ids=[question.id],
            embeddings=self._embed([embeddable_text(question)]),
            metadatas=[metadata_for(question)],
        )

    def delete(self, question_id: str) -> None:
        self._store.delete([question_id])           # 向量库 (始终内存, 启动重建)


# ═══════════════════════════════════════════════════════════════════════════
#  RAG 构建
# ═══════════════════════════════════════════════════════════════════════════

def build_inmemory_retriever(
    embedder: Callable[[list[str]], list[list[float]]],
) -> Retriever:
    """用给定 embedder 把 SEED_QUESTIONS 灌进 InMemory RAG, 返回 Retriever。

    用于单元测试或非 MCP 纯内存模式; 生产环境走 build_retriever() 按环境变量选后端。
    """
    vector_store, question_bank = InMemoryVectorStore(), InMemoryQuestionBank()
    seed_questions(question_bank, vector_store, embedder, SEED_QUESTIONS)
    return Retriever(vector_store, question_bank, embedder)


def _safe_seed(question_bank, vector_store, embedder, questions) -> None:
    """灌向量索引; embedding 端点不可用时降级为空索引而非整服务崩溃。

    题库 CRUD (admin/题库管理) 不依赖 embedding, 因此 seeding 失败只影响
    面试 RAG 召回质量, 不应阻断服务启动。
    """
    try:
        seed_questions(question_bank, vector_store, embedder, questions)
    except Exception as exc:  # noqa: BLE001 - 启动期容错: 网络/鉴权失败均降级
        logger.warning(
            "向量索引 seeding 失败, 面试 RAG 召回将退化为空索引 (题库管理不受影响): %s",
            exc,
        )


def _seed_bank_only(question_bank) -> None:
    """只把 SEED 题写进题库 (保证题存在), 不做向量 embedding。用于 chroma 模式。"""
    for q in SEED_QUESTIONS:
        question_bank.add(q)


def _safe_ensure_index(question_bank, embedder, vector_store) -> None:
    """增量补齐持久向量库; embedding 端点不可用时降级为已有索引而非崩溃。"""
    from interviewforge.rag.index_builder import ensure_index
    try:
        n = ensure_index(question_bank, embedder, vector_store)
        if n:
            logger.info("Chroma 增量向量化: 本次新 embed %d 题", n)
        else:
            logger.info("Chroma 增量向量化: 无缺失/变更题, 跳过 embedding")
    except Exception as exc:  # noqa: BLE001 - 启动期容错: 网络/鉴权失败降级
        logger.warning("Chroma 增量向量化失败, 检索退化为已有索引: %s", exc)


def build_retriever(embedder, settings=None):
    """按环境变量选题库/向量库后端, 组装 Retriever 返回。

    INTERVIEWFORGE_QUESTION_BANK (inmemory|mysql) 选题库原文后端。
    INTERVIEWFORGE_VECTOR_STORE  (memory|chroma)  选向量库:
      - memory: 旧行为, 每次重建内存库, 仅灌 SEED 题向量。
      - chroma: 持久库, 对整个题库按 id+题干hash 增量 embedding (首启全量, 之后增量)。
    """
    source = os.getenv("INTERVIEWFORGE_QUESTION_BANK", "inmemory").strip().lower()
    chroma = is_chroma_mode()
    vector_store = build_vector_store()
    if source == "inmemory":
        question_bank = InMemoryQuestionBank()
    elif source == "mysql":
        # 懒导入 MySQLQuestionBank, 避免没用 MySQL 时也加载 pymysql
        from interviewforge.rag.question_bank import MySQLQuestionBank
        question_bank = MySQLQuestionBank(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "interviewforge"),
        )
        question_bank.ensure_schema()
    else:
        raise ValueError(f"未知题库源 INTERVIEWFORGE_QUESTION_BANK={source!r}")

    if chroma:
        # 保证 SEED 题在库中; 向量走持久库增量 (覆盖全题库, 不只 SEED)
        _seed_bank_only(question_bank)
        _safe_ensure_index(question_bank, embedder, vector_store)
    else:
        # 内存模式: 保持旧行为 (灌 SEED 向量, 每次重建)
        _safe_seed(question_bank, vector_store, embedder, SEED_QUESTIONS)
    return Retriever(vector_store, question_bank, embedder)


# ═══════════════════════════════════════════════════════════════════════════
#  MCP (Model Context Protocol) 路径 — 子进程隔离模式
# ═══════════════════════════════════════════════════════════════════════════

def _build_mcp_pool():
    """启动题库/JD 两台 MCP server; 仅在 INTERVIEWFORGE_USE_MCP=1 时调用。

    每台 server 跑在独立子进程中, 通过 stdio JSON-RPC 通信,
    主进程的 MCPClientPool 持有长连接, 同步方式调用。
    """
    from interviewforge.mcp.client import MCPClientPool, ServerSpec
    logger.info("启动 MCP 连接池 …")
    pool = MCPClientPool([
        ServerSpec(name="questions",
                   module="interviewforge.mcp_servers.questions_server"),
        ServerSpec(name="jd",
                   module="interviewforge.mcp_servers.jd_server"),
    ])
    pool.start()
    logger.info("MCP 连接池就绪 (questions, jd)")
    return pool


# ═══════════════════════════════════════════════════════════════════════════
#  日志初始化
# ═══════════════════════════════════════════════════════════════════════════

def _configure_logging():
    """统一日志格式: interviewforge 系列的 logger 输出到 stderr (跟 uvicorn 同流)。"""
    root = logging.getLogger("interviewforge")
    if not root.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(handler)
        root.setLevel(logging.INFO)


# ═══════════════════════════════════════════════════════════════════════════
#  FastAPI 应用工厂 — uvicorn --factory 入口
# ═══════════════════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    """生产入口: uvicorn 调用的 --factory 函数。

    流程:
      1. 配置日志 → 2. 加载配置 + 模型客户端 → 3. 构建 RAG 检索器
      → 4. 按需启动 MCP 池 → 5. 组装会话工厂 → 6. 初始化岗位/题库 bank
      → 7. 挂载路由 + CORS → 返回 app
    """
    _configure_logging()
    logger.info("启动服务 …")
    settings = load_settings()                              # 读 .env + roles.yaml
    model_client = ModelClient.from_settings(settings)      # 包装 OpenAI 兼容 API

    # 构建 RAG 检索器: 根据 INTERVIEWFORGE_QUESTION_BANK 选 InMemory 或 MySQL 后端
    retriever = build_retriever(model_client.embed, settings)
    base_dir = Path(os.getenv("INTERVIEWFORGE_WORKDIR", ".interviewforge_sessions"))

    # ── MCP 模式: 从主进程拆出题库/JD 查询到独立子进程 ────────────
    use_mcp = os.getenv("INTERVIEWFORGE_USE_MCP", "").strip() in {"1", "true", "yes"}
    pool = None
    search_adapter_factory = None
    jd_lookup = None
    if use_mcp:
        from interviewforge.mcp.tools import MCPSearchAdapter, make_mcp_jd_lookup
        pool = _build_mcp_pool()
        # 打包成闭包: 每个 session 拿到独立的 MCPSearchAdapter 实例
        search_adapter_factory = lambda memory: MCPSearchAdapter(pool, memory)
        jd_lookup = make_mcp_jd_lookup(pool)

    # ── 简历解析 / 分析器 ──────────────────────────────────────────
    from interviewforge.resume.parser import extract_text
    from interviewforge.resume.analyzer import ResumeAnalyzer
    from interviewforge.skills.registry import SkillRegistry
    skill_registry = SkillRegistry()           # 加载 roles.yaml 定义的技能维度
    analyzer = ResumeAnalyzer(model_client)

    def analyze_resume_text(text: str, role: str, jd: str):
        """已有正文 → 技能评估 → 结构化画像 (供“我的投递”按当前 JD 现生成)。"""
        methodology, _dims = skill_registry.methodology_for(f"{role} {jd}")
        return analyzer.analyze(resume_text=text, role=role, jd=jd,
                                methodology=methodology)

    def analyze_resume(data: bytes, filename: str, role: str, jd: str):
        """解压二进制简历 → 全文 → 技能评估 → (原文, 画像)"""
        text = extract_text(data, filename)
        return text, analyze_resume_text(text, role, jd)

    # 会话工厂: 一个 factory 创建多个 InterviewLoop (每 session 一个)
    factory = SessionFactory(
        retriever=retriever, model_client=model_client, base_dir=base_dir,
        rules=settings.global_rules, token_budget=settings.token_budget,
        search_adapter_factory=search_adapter_factory, jd_lookup=jd_lookup,
        skill_registry=skill_registry)

    # FastAPI 生命周期: 应用退出时关闭 MCP 池子进程
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        try:
            yield
        finally:
            if pool is not None:
                pool.stop()

    # ── Admin 后端: 岗位管理 (与题库同源) ──────────────────────────
    from interviewforge.rag.position_bank import (
        InMemoryPositionBank, MySQLPositionBank, Position)
    admin_question_bank = retriever.question_bank

    # ── 认证/历史后端: 与题库同一开关 (mysql / inmemory) ───────────
    from interviewforge.auth.history import (
        InMemoryHistoryBank, MySQLHistoryBank)
    from interviewforge.auth.resume_store import (
        InMemoryResumeStore, MySQLResumeStore)
    from interviewforge.auth.tokens import TokenStore
    from interviewforge.auth.users import InMemoryUserBank, MySQLUserBank
    _auth_mysql = (os.getenv("INTERVIEWFORGE_QUESTION_BANK",
                             "inmemory").strip().lower() == "mysql")
    _mysql_kwargs = dict(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "interviewforge"),
    )
    if _auth_mysql:
        user_bank = MySQLUserBank(**_mysql_kwargs)
        user_bank.ensure_schema()
        history_bank = MySQLHistoryBank(**_mysql_kwargs)
        history_bank.ensure_schema()
        resume_store = MySQLResumeStore(**_mysql_kwargs)
        resume_store.ensure_schema()
    else:
        # 无 MySQL 的开发环境: 注册/登录/历史均可跑通, 但不落盘
        user_bank = InMemoryUserBank()
        history_bank = InMemoryHistoryBank()
        resume_store = InMemoryResumeStore()
    token_store = TokenStore()

    # ── 超级管理员 root 幂等引导 (username=root / 密码 123456, role=root) ──
    from interviewforge.auth.password import hash_password
    root = user_bank.get_by_username("root")
    if root is None:
        user_bank.create("root", hash_password("123456"), role="root")
        logger.info("已创建超级管理员 root")
    elif root.role != "root":
        user_bank.set_role(root.id, "root")   # 确保 root 始终为超级管理员
        logger.info("已将 root 账号角色归正为超级管理员")

    # ── 岗位广场后端: 与题库同一开关 (mysql / inmemory) ───────────
    from interviewforge.jobs.seed import SEED_JOBS
    from interviewforge.jobs.store import InMemoryJobStore, Job, MySQLJobStore
    if _auth_mysql:
        job_store = MySQLJobStore(**_mysql_kwargs)
        job_store.ensure_schema()
        # 仅首次启动 (表为空) 灌种子; 管理员删除的岗位不会在重启后复活
        if not job_store.list_all():
            for d in SEED_JOBS:
                job_store.add(Job(**d))
    else:
        job_store = InMemoryJobStore()
        for d in SEED_JOBS:
            job_store.add(Job(**d))

    _DEFAULT_POSITIONS = [
        ("p1", "后端工程师", "#4F46E5"),
        ("p2", "前端工程师", "#0284C7"),
        ("p3", "算法工程师", "#7C3AED"),
        ("p4", "系统设计",   "#0F172A"),
    ]
    # 岗位 bank 的持久化策略与题库保持一致: 同样走 MySQL 或 InMemory
    if os.getenv("INTERVIEWFORGE_QUESTION_BANK", "inmemory").strip().lower() == "mysql":
        pos_bank = MySQLPositionBank(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "interviewforge"),
        )
        pos_bank.ensure_schema()
        # 仅当岗位表为空 (首次启动) 时种入默认岗位; 用户删除的岗位不会在重启后复活
        if not pos_bank.list_all():
            for pid, name, color in _DEFAULT_POSITIONS:
                pos_bank.add(Position(id=pid, name=name, color=color))
    else:
        pos_bank = InMemoryPositionBank()
        # 种几个默认岗位，方便首次体验
        for pid, name, color in _DEFAULT_POSITIONS:
            pos_bank.add(Position(id=pid, name=name, color=color))

    # ── 向量索引同步器: 仅 chroma 模式下 admin 增删改题目时即时同步 Chroma ──
    vector_index_syncer = None
    if is_chroma_mode():
        vector_index_syncer = QuestionIndexSyncer(retriever.vector_store,
                                                   model_client.embed)

    # 组装 FastAPI app: 挂载所有路由 (会话 + admin + 认证/历史 + 岗位广场)
    # 接口文档开关: INTERVIEWFORGE_EXPOSE_DOCS=0 关闭 /docs /redoc /openapi.json
    # (默认 1 开启, 方便本地; 生产 .env 设 0, 避免公网暴露全部接口清单)
    _expose_docs = os.getenv("INTERVIEWFORGE_EXPOSE_DOCS",
                             "1").strip().lower() in {"1", "true", "yes"}
    _docs_kwargs = (
        {"docs_url": "/docs", "redoc_url": "/redoc",
         "openapi_url": "/openapi.json"}
        if _expose_docs else
        {"docs_url": None, "redoc_url": None, "openapi_url": None}
    )
    app = build_app(SessionStore(factory), question_bank=admin_question_bank,
                    position_bank=pos_bank, analyze_resume=analyze_resume,
                    user_bank=user_bank, history_bank=history_bank,
                    token_store=token_store, resume_store=resume_store,
                    analyze_resume_text=analyze_resume_text,
                    job_store=job_store,
                    vector_index_syncer=vector_index_syncer,
                    **_docs_kwargs)
    app.router.lifespan_context = lifespan
    # CORS: 仅允许本地 Vite 开发服务器 (5173) 直连
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )
    return app
