"""岗位广场数据域: 岗位卡片存储 (与题库岗位标签 PositionBank 相互独立)。"""
from __future__ import annotations

from interviewforge.jobs.store import (
    InMemoryJobStore, Job, JobStore, MySQLJobStore)

__all__ = ["Job", "JobStore", "InMemoryJobStore", "MySQLJobStore"]
