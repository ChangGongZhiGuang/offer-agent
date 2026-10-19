"""HTTP 边界数据契约 (Pydantic v2)。

所有 API 请求体与响应体的类型定义集中在此,
确保前后端契约一目了然、修改可追踪。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── 简历 / 候选人 ──────────────────────────────────────────────

class ProjectModel(BaseModel):
    """简历中的单个项目经历。"""
    name: str = ""           # 项目名称
    tech: list[str] = []     # 使用到的技术栈列表
    summary: str = ""        # 项目简要描述


class CandidateProfileModel(BaseModel):
    """从简历解析出的候选人画像结构化数据。"""
    skills: list[str] = []        # 技能列表 (如 ["Python", "Kubernetes"])
    projects: list[ProjectModel] = []  # 项目经历列表
    years: str = ""               # 工作年限 (保留字符串形式便于展示)
    highlights: list[str] = []    # 突出亮点, 供面试官参考
    weak_spots: list[str] = []    # 薄弱环节, 供针对性提问
    topic_plan: list[str] = []    # 建议考察的主题, 驱动 session_plan 选题


class ResumeResponse(BaseModel):
    """POST /resume 上传简历后的响应。"""
    resume_text: str                # 提取出的纯文本全文
    profile: CandidateProfileModel  # 结构化画像


# ── 面试会话: 启动 ─────────────────────────────────────────────

class StartRequest(BaseModel):
    """POST /start 创建新面试会话的请求。"""
    role: str                                          # 目标岗位, 如 "后端工程师"
    topic: str                                         # 这场面试的主题方向
    profile: str = ""                                  # 候选人背景描述 (自由文本)
    jd_keywords: list[str] = []                        # 职位描述关键词
    profile_struct: CandidateProfileModel | None = None  # 结构化画像 (可选, 替代自由文本)
    num_questions: int = Field(default=3, ge=1, le=20)  # 计划提问数量 (1~20)


class StartResponse(BaseModel):
    """POST /start 创建成功后的响应。"""
    session_id: str  # 新创建会话的唯一标识, 后续请求携带此 ID
    role: str
    topic: str


# ── 面试会话: 提问与回答 ───────────────────────────────────────

class QuestionResponse(BaseModel):
    """GET /question 获取下一道题的响应。

    当 done=True 时表示面试已无更多题目 (题数耗尽或已被强制 HALT),
    此时 question_id 和 question 为 None。
    """
    done: bool                         # True = 无更多题 (题数耗尽或面试已终止)
    phase: str                         # 当前面试相位 (如 "开场" / "深入" / "结束")
    question_id: str | None = None     # 本题 ID, 后续作答时回传
    question: str | None = None        # 问题正文


class AnswerRequest(BaseModel):
    """POST /answer 提交回答的请求。"""
    answer: str  # 候选人对当前题目的回答文本


class AnswerResponse(BaseModel):
    """POST /answer 评分后的响应。"""
    score: int                    # 本题得分 (0~100)
    weakness_tags: list[str]      # 本题暴露的能力短板标签集合
    feedback: str                 # 面试官评语 / 参考答案


# ── 面试会话: 报告与状态 ───────────────────────────────────────

class ReportResponse(BaseModel):
    """GET /report 面试结束后的完整评估报告。"""
    answered: int                                # 已作答题目数
    avg_score: float                             # 各题平均分
    overall_score: float = 0.0                   # 综合评分 (加权或额外维度调整)
    dimensions: list[dict] = Field(default_factory=list)    # 各维度得分列表
    per_question: list[dict] = Field(default_factory=list)  # 逐题明细
    weakness_tags: list[str] = Field(default_factory=list)  # 全场汇总的薄弱标签
    summary: str = ""                                        # 总结评语
    suggestions: list[str] = Field(default_factory=list)     # 改进建议列表
    qa: list[dict] = Field(default_factory=list)             # 逐题问答流水 (题文/答案/得分/评语/维度)


class StatusResponse(BaseModel):
    """GET /status 查询会话当前进度。"""
    session_id: str        # 会话 ID
    phase: str             # 当前相位
    turn: int              # 当前轮次 (已出的题数)
    asked: int             # 已作答的题数
    halted: str | None = None  # 若会话被强制终止, 此处说明原因


# ── 题库管理: 题目 ─────────────────────────────────────────────

class QuestionIn(BaseModel):
    """POST /admin/questions 新增 / PUT 更新题目的请求体。"""
    id: str                          # 题目唯一标识
    stem: str                        # 题干 (问题正文)
    role: str                        # 适用岗位标记
    topic: str = ""                  # 所属主题
    answer: str = ""                 # 参考答案
    difficulty: str = "medium"       # 难度: "easy" | "medium" | "hard"
    fu: str = ""                     # 追问 / follow-up 引导


class QuestionOut(BaseModel):
    """GET /admin/questions 列出的题目条目。字段与 QuestionIn 一致。"""
    id: str
    stem: str
    role: str
    topic: str
    answer: str
    difficulty: str
    fu: str


# ── 题库管理: 岗位 ─────────────────────────────────────────────

class PositionIn(BaseModel):
    """POST /admin/positions 新增岗位的请求体。"""
    name: str                    # 岗位名称, 如 "后端工程师"
    color: str = "#4F46E5"       # 前端展示用的色值, 便于区分不同岗位


class PositionOut(BaseModel):
    """GET /admin/positions 列出的岗位条目。"""
    id: str    # 岗位唯一标识
    name: str
    color: str


# ── 岗位广场: 招聘卡片 (与上方题库岗位标签无关) ────────────────

class JobIn(BaseModel):
    """POST/PUT /jobs 新增或更新岗位卡片的请求体 (仅基础字段)。"""
    category: str = ""           # 后端 / 前端 / 算法 / 系统设计
    title: str                   # 岗位标题
    company: str = ""
    salary: str = ""             # 展示用薪资文本
    salary_min: int = 0          # 薪资下限 (K), 供筛选
    city: str = ""
    exp: str = ""
    skills: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)


class JobOut(JobIn):
    """GET /jobs 列出的岗位条目。"""
    id: str


# ── 用户 / 角色管理 (仅超级管理员 root) ────────────────────────

class UserRoleOut(BaseModel):
    """GET /admin/users 列出的用户条目 (不含口令哈希)。"""
    user_id: str
    username: str
    role: str


class SetRoleRequest(BaseModel):
    """PUT /admin/users/{user_id}/role 设置角色的请求体。"""
    role: str                    # 仅允许 "user" | "admin"


# ── 认证: 注册 / 登录 ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    """POST /auth/register 注册请求。"""
    username: str            # 3-16 位, 仅字母/数字/-/_, 不可与已有重复
    password: str            # 明文口令 (后端哈希后落库, 不记录原文)


class LoginRequest(BaseModel):
    """POST /auth/login 登录请求。"""
    username: str
    password: str


class AuthUser(BaseModel):
    """对外暴露的用户身份 (不含口令哈希)。"""
    user_id: str
    username: str
    role: str = "user"       # "user" | "admin" | "root"


class LoginResponse(BaseModel):
    """注册/登录成功后的响应: 携带 Bearer token 与用户身份。"""
    token: str               # 后续请求以 Authorization: Bearer <token> 回传
    user: AuthUser


# ── 历史记录 ───────────────────────────────────────────────────

class HistoryItem(BaseModel):
    """GET /history 列表条目 (摘要, 不含完整报告)。"""
    session_id: str
    role: str
    topic: str
    overall_score: float
    avg_score: float
    answered: int
    created_at: str


class HistoryDetailResponse(BaseModel):
    """GET /history/{session_id} 单场完整报告 + 会话元信息。"""
    session_id: str
    role: str
    topic: str
    created_at: str
    report: ReportResponse


# ── 我的简历 (登录用户维护的简历正文) ──────────────────────

class ResumeSaveRequest(BaseModel):
    """PUT /profile/me 保存/覆盖简历正文。"""
    text: str                # 简历正文 (已提取的纯文本)
    filename: str = ""       # 来源文件名 (仅展示用, 可空)


class ResumeSavedResponse(BaseModel):
    """保存成功后的摘要 (不回传全文, 避免无谓传输)。"""
    exists: bool = True
    filename: str = ""
    size: int = 0
    updated_at: str = ""


class ResumeDetailResponse(BaseModel):
    """GET /profile/me 已存简历正文; text 为空表示尚未保存。"""
    exists: bool = False
    filename: str = ""
    size: int = 0
    updated_at: str = ""
    text: str = ""


class ResumeAnalyzeRequest(BaseModel):
    """POST /resume/analyze 从文本按岗位/JD 现生成结构化画像。"""
    text: str                    # 简历正文
    role: str = ""               # 目标岗位
    jd: str = ""                 # 职位描述关键词


class ResumeAnalyzeResponse(BaseModel):
    """从文本分析出的结构化画像。"""
    profile: CandidateProfileModel


# ── Trace 重放 ───────────────────────────────────────────────────

class TraceEventOut(BaseModel):
    """trace 事件条目 (来自 transcript.jsonl 的一行)。"""
    type: str              # "transition" | "compact"
    ts: float              # Unix timestamp
    payload: dict          # 详情 (from/to/gate 或 layers/before/after)
