"""FastAPI 路由: 把 InterviewLoop 暴露成会话化 HTTP 接口，含 admin 题库端点。"""
from __future__ import annotations

import logging
import time
import random
import string

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form

from interviewforge.api.schemas import (
    AnswerRequest, AnswerResponse, AuthUser, CandidateProfileModel,
    HistoryDetailResponse, HistoryItem,
    ChangePasswordRequest, DeactivateRequest,
    JobIn, JobOut, LoginRequest, LoginResponse,
    PositionIn, PositionOut, QuestionIn, QuestionOut,
    QuestionResponse, RegisterRequest, ReportResponse,
    ResumeAnalyzeRequest, ResumeAnalyzeResponse, ResumeDetailResponse,
    ResumeResponse, ResumeSaveRequest, ResumeSavedResponse,
    SetRoleRequest, StartRequest, StartResponse, StatusResponse,
    TraceEventOut, UserRoleOut,
)
from interviewforge.api.session import SessionStore
from interviewforge.auth.history import HistoryEntry
from interviewforge.auth.password import (
    hash_password, validate_password, validate_username, verify_password)
from interviewforge.auth.users import DuplicateUserError, User
from interviewforge.jobs.store import Job
from interviewforge.loop.machine import InterviewLoop
from interviewforge.resume.parser import ResumeParseError

logger = logging.getLogger("interviewforge")

# 可管理岗位/题库的角色 (root 天然包含在内)
ADMIN_ROLES = {"admin", "root"}


def _gen_id(prefix: str) -> str:
    ts = int(time.time() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{prefix}-{ts}-{rand}"


def build_app(store: SessionStore, question_bank=None, position_bank=None,
              analyze_resume=None, user_bank=None, history_bank=None,
              token_store=None, resume_store=None,
              analyze_resume_text=None, job_store=None,
              vector_index_syncer=None,
              docs_url="/docs", redoc_url="/redoc",
              openapi_url="/openapi.json") -> FastAPI:
    # docs_url/redoc_url/openapi_url 传 None 即关闭对应路由 (生产环境用,
    # 由 factory 依 INTERVIEWFORGE_EXPOSE_DOCS 决定; 默认保持开启便于本地调试)
    app = FastAPI(title="OfferAgent API", version="0.0.0",
                  docs_url=docs_url, redoc_url=redoc_url,
                  openapi_url=openapi_url)

    def _sync_upsert(question) -> None:
        """写库后同步向量索引 (仅 chroma 模式有 syncer); 失败仅告警不回滚 MySQL。"""
        if vector_index_syncer is None:
            return
        try:
            vector_index_syncer.upsert(question)
        except Exception as exc:  # noqa: BLE001 - 索引同步失败不阻断写库
            logger.warning("向量索引同步 upsert 失败 [%s]: %s", question.id, exc)

    def _sync_delete(question_id: str) -> None:
        if vector_index_syncer is None:
            return
        try:
            vector_index_syncer.delete(question_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("向量索引同步 delete 失败 [%s]: %s", question_id, exc)

    def _loop(session_id: str) -> InterviewLoop:
        loop = store.get(session_id)
        if loop is None:
            raise HTTPException(status_code=404, detail="session not found")
        return loop

    def _bearer(request: Request) -> str | None:
        """从 Authorization: Bearer <token> 提取 token。"""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):].strip() or None
        return None

    def _current_user_id(request: Request) -> str | None:
        """解析当前请求的登录用户 id; 未配置 token_store 或无有效 token 则 None。"""
        if token_store is None:
            return None
        return token_store.resolve(_bearer(request))

    def _current_user(request: Request) -> "User | None":
        """解析当前登录用户对象 (含 role); 未登录/无 user_bank/已注销则 None。

        已注销 (status=deleted) 在此集中拦截 → 所有登录态接口自然 401。
        """
        if user_bank is None:
            return None
        uid = _current_user_id(request)
        if uid is None:
            return None
        user = user_bank.get_by_id(uid)
        if user is not None and user.status == "deleted":
            return None
        return user

    def _require_role(request: Request, allowed: set[str]) -> "User":
        """要求当前登录用户角色属于 allowed; 否则 401/403。"""
        if user_bank is None:
            raise HTTPException(status_code=503, detail="auth not configured")
        user = _current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="permission denied")
        return user

    # ── 认证: 注册 / 登录 / 当前用户 ─────────────────────────
    @app.post("/auth/register", response_model=LoginResponse)
    def register(req: RegisterRequest) -> LoginResponse:
        if user_bank is None or token_store is None:
            raise HTTPException(status_code=503, detail="auth not configured")
        if not validate_username(req.username):
            raise HTTPException(
                status_code=400,
                detail="用户名需为 3-16 位字母/数字/-/_")
        if not validate_password(req.password):
            raise HTTPException(status_code=400, detail="密码至少 6 位")
        try:
            user = user_bank.create(req.username, hash_password(req.password))
        except DuplicateUserError:
            raise HTTPException(status_code=409, detail="用户名已存在")
        token = token_store.issue(user.id)
        return LoginResponse(token=token, user=AuthUser(user_id=user.id,
                                                        username=user.username,
                                                        role=user.role))

    @app.post("/auth/login", response_model=LoginResponse)
    def login(req: LoginRequest) -> LoginResponse:
        if user_bank is None or token_store is None:
            raise HTTPException(status_code=503, detail="auth not configured")
        user = user_bank.get_by_username(req.username)
        # 统一 401: 不区分“用户不存在/密码错”, 避免枚举
        if user is None or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.status == "deleted":
            # 密码正确但账号已注销: 给出明确提示 (可联系管理员恢复)
            raise HTTPException(status_code=403, detail="该账号已注销")
        token = token_store.issue(user.id)
        return LoginResponse(token=token, user=AuthUser(user_id=user.id,
                                                        username=user.username,
                                                        role=user.role))

    @app.post("/auth/logout", response_model=dict)
    def logout(request: Request) -> dict:
        if token_store is not None:
            token = _bearer(request)
            if token:
                token_store.revoke(token)
        return {"ok": True}

    @app.get("/auth/me", response_model=AuthUser)
    def me(request: Request) -> AuthUser:
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        user = user_bank.get_by_id(uid) if user_bank is not None else None
        return AuthUser(user_id=uid, username=user.username if user else "",
                        role=user.role if user else "user")

    @app.post("/auth/change-password", response_model=dict)
    def change_password(req: ChangePasswordRequest, request: Request) -> dict:
        """修改密码: 需登录 + 旧密码二次确认; 成功后吊销全部 token 强制重登。"""
        user = _current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        if not verify_password(req.old_password, user.password_hash):
            raise HTTPException(status_code=401, detail="旧密码不正确")
        if not validate_password(req.new_password):
            raise HTTPException(status_code=400, detail="新密码至少 6 位")
        if req.new_password == req.old_password:
            raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
        if not user_bank.set_password_hash(user.id, hash_password(req.new_password)):
            raise HTTPException(status_code=404, detail="user not found")
        revoked = token_store.revoke_all(user.id) if token_store is not None else 0
        logger.info("用户 [%s] 修改密码, 吊销 %d 个 token", user.username, revoked)
        return {"ok": True}

    @app.post("/auth/deactivate", response_model=dict)
    def deactivate(request: Request, req: DeactivateRequest) -> dict:
        """自助注销账号 (软删除): 需登录 + 当前密码二次确认; 历史/简历数据保留。"""
        user = _current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="密码不正确")
        user_bank.set_status(user.id, "deleted")
        revoked = token_store.revoke_all(user.id) if token_store is not None else 0
        logger.info("用户 [%s] 自助注销, 吊销 %d 个 token", user.username, revoked)
        return {"ok": True}

    # ── 历史记录 (需登录) ────────────────────────────────
    @app.get("/history", response_model=list[HistoryItem])
    def list_history(request: Request) -> list[HistoryItem]:
        if history_bank is None:
            raise HTTPException(status_code=503, detail="history not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        return [HistoryItem(**e.summary())
                for e in history_bank.list_by_user(uid)]

    @app.get("/history/{session_id}", response_model=HistoryDetailResponse)
    def history_detail(session_id: str, request: Request) -> HistoryDetailResponse:
        if history_bank is None:
            raise HTTPException(status_code=503, detail="history not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        entry = history_bank.get_by_session(uid, session_id)
        # 不存在于他人名下时一律 404, 不泄露是否属于别人
        if entry is None:
            raise HTTPException(status_code=404, detail="history not found")
        rpt = entry.report
        report = ReportResponse(
            answered=rpt.get("answered", entry.answered),
            avg_score=rpt.get("avg_score", entry.avg_score),
            overall_score=rpt.get("overall_score", entry.overall_score),
            dimensions=rpt.get("dimensions", []),
            per_question=rpt.get("per_question", []),
            weakness_tags=rpt.get("weakness_tags", []),
            summary=rpt.get("summary", ""),
            suggestions=rpt.get("suggestions", []),
            qa=rpt.get("qa", []),
            follow_up_total=rpt.get("follow_up_total", 0),
        )
        return HistoryDetailResponse(session_id=entry.session_id, role=entry.role,
                                     topic=entry.topic, created_at=entry.created_at,
                                     report=report)

    @app.delete("/history/{session_id}", response_model=dict)
    def delete_history(session_id: str, request: Request) -> dict:
        if history_bank is None:
            raise HTTPException(status_code=503, detail="history not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        if not history_bank.delete(uid, session_id):
            raise HTTPException(status_code=404, detail="history not found")
        return {"deleted": session_id}

    # ── 我的简历 (需登录) ────────────────────────────────
    @app.get("/profile/me", response_model=ResumeDetailResponse)
    def get_my_resume(request: Request) -> ResumeDetailResponse:
        if resume_store is None:
            raise HTTPException(status_code=503, detail="resume store not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        sr = resume_store.get(uid)
        if sr is None:
            return ResumeDetailResponse(exists=False)
        return ResumeDetailResponse(exists=True, **sr.to_dict())

    @app.put("/profile/me", response_model=ResumeSavedResponse)
    def save_my_resume(req: ResumeSaveRequest, request: Request) -> ResumeSavedResponse:
        if resume_store is None:
            raise HTTPException(status_code=503, detail="resume store not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        try:
            sr = resume_store.put(uid, req.text, req.filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ResumeSavedResponse(exists=True, **sr.summary())

    @app.delete("/profile/me", response_model=dict)
    def delete_my_resume(request: Request) -> dict:
        if resume_store is None:
            raise HTTPException(status_code=503, detail="resume store not configured")
        uid = _current_user_id(request)
        if uid is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        if not resume_store.delete(uid):
            raise HTTPException(status_code=404, detail="resume not found")
        return {"deleted": True}

    @app.post("/resume/analyze", response_model=ResumeAnalyzeResponse)
    def analyze_resume_from_text(req: ResumeAnalyzeRequest) -> ResumeAnalyzeResponse:
        if analyze_resume_text is None:
            raise HTTPException(status_code=503, detail="resume analysis not configured")
        if not req.text.strip():
            raise HTTPException(status_code=400, detail="简历正文不能为空")
        profile = analyze_resume_text(req.text, req.role, req.jd)
        return ResumeAnalyzeResponse(
            profile=CandidateProfileModel(**profile.to_dict()))

    @app.post("/sessions", response_model=StartResponse)
    def create_session(req: StartRequest, request: Request) -> StartResponse:
        from interviewforge.resume.types import CandidateProfile
        ps = CandidateProfile.from_dict(req.profile_struct.model_dump()) \
            if req.profile_struct is not None else None
        # 登录状态下发起的面试才绑定 user_id (供 finish 写历史)
        uid = _current_user_id(request)
        sid = store.create(role=req.role, topic=req.topic, profile=req.profile,
                           num_questions=req.num_questions,
                           max_follow_ups=req.max_follow_ups,
                           jd_keywords=req.jd_keywords, profile_struct=ps,
                           user_id=uid)
        return StartResponse(session_id=sid, role=req.role, topic=req.topic)

    @app.post("/resume", response_model=ResumeResponse)
    async def resume(file: UploadFile = File(...), role: str = Form(""),
                     jd: str = Form("")):
        if analyze_resume is None:
            raise HTTPException(status_code=503, detail="resume analysis not configured")
        data = await file.read()
        try:
            text, profile = analyze_resume(data, file.filename, role, jd)
        except ResumeParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ResumeResponse(resume_text=text, profile=profile.to_dict())

    @app.post("/sessions/{session_id}/ask", response_model=QuestionResponse)
    def ask(session_id: str) -> QuestionResponse:
        loop = _loop(session_id)
        question = loop.ask_question()
        if question is None:
            return QuestionResponse(done=True, phase=loop.state.phase.value)
        cq = loop.state.current_question or {}
        return QuestionResponse(done=False, phase=loop.state.phase.value,
                                question_id=cq.get("question_id"), question=question)

    @app.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
    def answer(session_id: str, req: AnswerRequest) -> AnswerResponse:
        loop = _loop(session_id)
        try:
            result = loop.submit_answer(req.answer)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        if result is None:
            raise HTTPException(status_code=409,
                                detail=f"session halted: {loop.state.halted}")
        return AnswerResponse(score=result["score"],
                              weakness_tags=result.get("weakness_tags", []),
                              feedback=result.get("feedback", ""),
                              is_follow_up=result.get("is_follow_up", False),
                              follow_up_question=result.get("follow_up_question"),
                              follow_up_of=result.get("follow_up_of"),
                              follow_up_done=result.get("follow_up_done", False))

    @app.post("/sessions/{session_id}/finish", response_model=ReportResponse)
    def finish(session_id: str) -> ReportResponse:
        loop = _loop(session_id)
        report = loop.finish()
        # 逐题问答随报告一同沉淀 (report_json 已能容纳, 无需改表)
        report["qa"] = list(loop.state.qa_log)
        # 仅当会话是“登录状态下发起”时写历史 (创建时绑定的 owner)
        owner = store.get_owner(session_id)
        if history_bank is not None and owner is not None:
            history_bank.add(HistoryEntry(
                session_id=session_id,
                user_id=owner,
                role=loop.state.role,
                topic=loop.state.topic,
                overall_score=report.get("overall_score", report["avg_score"]),
                avg_score=report["avg_score"],
                answered=report["answered"],
                report=dict(report),
            ))
        return ReportResponse(
            answered=report["answered"],
            avg_score=report["avg_score"],
            overall_score=report.get("overall_score", report["avg_score"]),
            dimensions=report.get("dimensions", []),
            per_question=report.get("per_question", []),
            weakness_tags=report.get("weakness_tags", []),
            summary=report.get("summary", ""),
            suggestions=report.get("suggestions", []),
            qa=report.get("qa", []),
            follow_up_total=report.get("follow_up_total", 0),
        )

    @app.get("/sessions/{session_id}", response_model=StatusResponse)
    def status(session_id: str) -> StatusResponse:
        loop = _loop(session_id)
        halted = loop.state.halted.value if loop.state.halted is not None else None
        return StatusResponse(session_id=session_id, phase=loop.state.phase.value,
                              turn=loop.state.turn, asked=len(loop.state.asked_ids),
                              halted=halted)

    @app.get("/sessions/{session_id}/trace", response_model=list[TraceEventOut])
    def session_trace(session_id: str) -> list[TraceEventOut]:
        """重放 trace: 会话存活时直接从内存取, 已丢失则从磁盘文件读。"""
        from interviewforge.persistence.transcript import Transcript
        loop = store.get(session_id)
        if loop is not None and loop.transcript is not None:
            events = loop.transcript.replay()
        else:
            # 会话已丢失(进程重启等): 从磁盘拼路径读文件
            path = store.base_dir / session_id / "transcript.jsonl"
            if not path.exists():
                return []
            events = Transcript(path).replay()
        return [TraceEventOut(type=e.type, ts=e.ts, payload=e.payload)
                for e in events]

    # ── admin endpoints (仅在注入 banks 后挂载; 需 admin/root 角色) ────────
    if question_bank is not None and position_bank is not None:

        @app.get("/admin/questions", response_model=list[QuestionOut])
        def list_questions(request: Request, role: str = "") -> list[QuestionOut]:
            _require_role(request, ADMIN_ROLES)
            qs = question_bank.list_all(role=role if role else None)
            return [QuestionOut(id=q.id, stem=q.stem, role=q.role, topic=q.topic,
                                answer=q.answer, difficulty=q.difficulty, fu=q.fu)
                    for q in qs]

        @app.post("/admin/questions", response_model=QuestionOut)
        def create_question(req: QuestionIn, request: Request) -> QuestionOut:
            _require_role(request, ADMIN_ROLES)
            from interviewforge.rag.types import Question
            q = Question(id=req.id, stem=req.stem, role=req.role, topic=req.topic,
                         answer=req.answer, difficulty=req.difficulty, fu=req.fu)
            question_bank.add(q)
            logger.info("新增题目 [%s] role=%s topic=%s stem=%.50s",
                        q.id, q.role, q.topic, q.stem)
            _sync_upsert(q)
            return QuestionOut(id=q.id, stem=q.stem, role=q.role, topic=q.topic,
                               answer=q.answer, difficulty=q.difficulty, fu=q.fu)

        @app.put("/admin/questions/{question_id}", response_model=QuestionOut)
        def update_question(question_id: str, req: QuestionIn,
                            request: Request) -> QuestionOut:
            _require_role(request, ADMIN_ROLES)
            from interviewforge.rag.types import Question
            if not question_bank.get_by_ids([question_id]):
                raise HTTPException(status_code=404, detail="question not found")
            # 路径 id 为准, 忽略 body.id, 避免改主键
            q = Question(id=question_id, stem=req.stem, role=req.role, topic=req.topic,
                         answer=req.answer, difficulty=req.difficulty, fu=req.fu)
            question_bank.add(q)
            logger.info("更新题目 [%s] role=%s topic=%s stem=%.50s",
                        question_id, q.role, q.topic, q.stem)
            _sync_upsert(q)
            return QuestionOut(id=q.id, stem=q.stem, role=q.role, topic=q.topic,
                               answer=q.answer, difficulty=q.difficulty, fu=q.fu)

        @app.delete("/admin/questions/{question_id}", response_model=dict)
        def delete_question(question_id: str, request: Request) -> dict:
            _require_role(request, ADMIN_ROLES)
            existing = question_bank.get_by_ids([question_id])
            if not existing:
                raise HTTPException(status_code=404, detail="question not found")
            question_bank.delete(question_id)
            logger.info("删除题目 [%s] (stem=%.50s)", question_id, existing[0].stem)
            _sync_delete(question_id)
            return {"deleted": question_id}

        @app.get("/admin/positions", response_model=list[PositionOut])
        def list_positions(request: Request) -> list[PositionOut]:
            _require_role(request, ADMIN_ROLES)
            return [PositionOut(id=p.id, name=p.name, color=p.color)
                    for p in position_bank.list_all()]

        @app.post("/admin/positions", response_model=PositionOut)
        def create_position(req: PositionIn, request: Request) -> PositionOut:
            _require_role(request, ADMIN_ROLES)
            from interviewforge.rag.position_bank import Position
            pid = _gen_id("pos")
            p = Position(id=pid, name=req.name, color=req.color)
            position_bank.add(p)
            logger.info("新增岗位 [%s] name=%s", pid, req.name)
            return PositionOut(id=p.id, name=p.name, color=p.color)

        @app.delete("/admin/positions/{position_id}", response_model=dict)
        def delete_position(position_id: str, request: Request) -> dict:
            _require_role(request, ADMIN_ROLES)
            target = next((p for p in position_bank.list_all()
                           if p.id == position_id), None)
            if target is None:
                raise HTTPException(status_code=404, detail="position not found")
            # 级联删除: 题目以岗位名 (role) 关联, 连同该岗位下的题目一并删除
            removed = question_bank.list_all(role=target.name)
            for q in removed:
                question_bank.delete(q.id)
                _sync_delete(q.id)
            position_bank.delete(position_id)
            logger.info("删除岗位 [%s] name=%s (连带删除 %d 道题目)",
                        position_id, target.name, len(removed))
            return {"deleted": position_id, "removed_questions": len(removed)}

    # ── 岗位广场 (浏览公开; 增删改需 admin/root) ───────────────
    if job_store is not None:

        @app.get("/jobs", response_model=list[JobOut])
        def list_jobs() -> list[JobOut]:
            return [JobOut(**j.to_dict()) for j in job_store.list_all()]

        @app.post("/jobs", response_model=JobOut)
        def create_job(req: JobIn, request: Request) -> JobOut:
            _require_role(request, ADMIN_ROLES)
            if not req.title.strip():
                raise HTTPException(status_code=400, detail="岗位标题不能为空")
            job = Job(id=_gen_id("job"), **req.model_dump())
            job_store.add(job)
            logger.info("新增岗位 [%s] category=%s title=%.40s",
                        job.id, job.category, job.title)
            return JobOut(**job.to_dict())

        @app.put("/jobs/{job_id}", response_model=JobOut)
        def update_job(job_id: str, req: JobIn, request: Request) -> JobOut:
            _require_role(request, ADMIN_ROLES)
            if job_store.get(job_id) is None:
                raise HTTPException(status_code=404, detail="job not found")
            if not req.title.strip():
                raise HTTPException(status_code=400, detail="岗位标题不能为空")
            # 路径 id 为准, 忽略 body 中可能的 id 字段
            job = Job(id=job_id, **req.model_dump())
            job_store.add(job)
            logger.info("更新岗位 [%s] title=%.40s", job_id, job.title)
            return JobOut(**job.to_dict())

        @app.delete("/jobs/{job_id}", response_model=dict)
        def delete_job(job_id: str, request: Request) -> dict:
            _require_role(request, ADMIN_ROLES)
            if not job_store.delete(job_id):
                raise HTTPException(status_code=404, detail="job not found")
            return {"deleted": job_id}

    # ── 用户 / 角色管理 (仅超级管理员 root) ───────────────────
    if user_bank is not None:

        @app.get("/admin/users", response_model=list[UserRoleOut])
        def list_users(request: Request) -> list[UserRoleOut]:
            _require_role(request, {"root"})
            return [UserRoleOut(user_id=u.id, username=u.username, role=u.role,
                                status=u.status)
                    for u in user_bank.list_all()]

        @app.put("/admin/users/{user_id}/role", response_model=UserRoleOut)
        def set_user_role(user_id: str, req: SetRoleRequest,
                          request: Request) -> UserRoleOut:
            actor = _require_role(request, {"root"})
            if req.role not in {"user", "admin"}:
                raise HTTPException(status_code=400, detail="角色只能为 user 或 admin")
            if user_id == actor.id:
                raise HTTPException(status_code=400, detail="不能修改自己的角色")
            target = user_bank.get_by_id(user_id)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if target.role == "root":
                raise HTTPException(status_code=400, detail="超级管理员不可修改")
            user_bank.set_role(user_id, req.role)
            logger.info("设置角色 [%s] %s -> %s (by root)",
                        target.username, target.role, req.role)
            return UserRoleOut(user_id=target.id, username=target.username,
                               role=req.role)

        @app.delete("/admin/users/{user_id}", response_model=dict)
        def deactivate_user(user_id: str, request: Request) -> dict:
            """root 注销他人 (软删除); 本人/root 不可由此注销。"""
            actor = _require_role(request, {"root"})
            if user_id == actor.id:
                raise HTTPException(status_code=400, detail="不能注销自己, 请使用自助注销")
            target = user_bank.get_by_id(user_id)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if target.role == "root":
                raise HTTPException(status_code=400, detail="超级管理员不可注销")
            user_bank.set_status(user_id, "deleted")
            revoked = token_store.revoke_all(user_id) if token_store is not None else 0
            logger.info("root 注销用户 [%s], 吊销 %d 个 token (by %s)",
                        target.username, revoked, actor.username)
            return {"ok": True}

        @app.post("/admin/users/{user_id}/restore", response_model=UserRoleOut)
        def restore_user(user_id: str, request: Request) -> UserRoleOut:
            """root 恢复已注销账号。"""
            actor = _require_role(request, {"root"})
            target = user_bank.get_by_id(user_id)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            user_bank.set_status(user_id, "active")
            logger.info("root 恢复用户 [%s] (by %s)", target.username, actor.username)
            return UserRoleOut(user_id=target.id, username=target.username,
                               role=target.role, status="active")

    return app
