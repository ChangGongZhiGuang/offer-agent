"""岗位广场 (job square) 岗位卡片数据源。管理员可增删改, 全体用户可浏览。

注意: 这与 rag/position_bank.PositionBank 是两套东西 —— 后者是"题库管理里给题目
打的岗位标签" (name+color), 本模块是岗位广场上那些内容丰富 (标题/公司/薪资/技能/
要求) 的招聘卡片。二者互不影响。

InMemory 单测/无 MySQL + MySQL 生产。基础字段入库; logo / 匹配度等装饰元素由前端
按规则现生成, 不落库。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Job:
    id: str
    category: str = ""          # 后端 / 前端 / 算法 / 系统设计
    title: str = ""
    company: str = ""
    salary: str = ""            # 展示用文本, 如 "30-55K · 16薪"
    salary_min: int = 0         # 薪资下限 (K), 供筛选
    city: str = ""
    exp: str = ""
    skills: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "category": self.category, "title": self.title,
            "company": self.company, "salary": self.salary,
            "salary_min": self.salary_min, "city": self.city, "exp": self.exp,
            "skills": list(self.skills), "requirements": list(self.requirements),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(
            id=d["id"], category=d.get("category", ""), title=d.get("title", ""),
            company=d.get("company", ""), salary=d.get("salary", ""),
            salary_min=int(d.get("salary_min", 0) or 0), city=d.get("city", ""),
            exp=d.get("exp", ""), skills=list(d.get("skills", []) or []),
            requirements=list(d.get("requirements", []) or []),
        )


class JobStore(Protocol):
    def list_all(self) -> list[Job]: ...
    def get(self, job_id: str) -> Job | None: ...
    def add(self, job: Job) -> Job: ...       # 按 id upsert
    def delete(self, job_id: str) -> bool: ...


class InMemoryJobStore:
    """进程内岗位表, 供单测与无 MySQL 环境。"""

    def __init__(self):
        self._items: dict[str, Job] = {}

    def list_all(self) -> list[Job]:
        return list(self._items.values())

    def get(self, job_id: str) -> Job | None:
        return self._items.get(job_id)

    def add(self, job: Job) -> Job:
        self._items[job.id] = job       # 同 id 直接覆盖
        return job

    def delete(self, job_id: str) -> bool:
        return self._items.pop(job_id, None) is not None


class MySQLJobStore:
    """生产: 表 job_postings。skills/requirements 以 JSON 文本存于 TEXT。懒导入 PyMySQL。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str):
        import pymysql
        self._pymysql = pymysql
        self._conn_kwargs = dict(host=host, port=port, user=user, password=password,
                                 database=database, charset="utf8mb4", autocommit=True)

    def _connect(self):
        return self._pymysql.connect(**self._conn_kwargs)

    def _ensure_database(self) -> None:
        kwargs = {k: v for k, v in self._conn_kwargs.items() if k != "database"}
        db = self._conn_kwargs["database"]
        with self._pymysql.connect(**kwargs) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

    def ensure_schema(self) -> None:
        self._ensure_database()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS job_postings (
                    id VARCHAR(32) PRIMARY KEY,
                    category VARCHAR(32),
                    title VARCHAR(128),
                    company VARCHAR(128),
                    salary VARCHAR(64),
                    salary_min INT DEFAULT 0,
                    city VARCHAR(64),
                    exp VARCHAR(64),
                    skills TEXT,
                    requirements TEXT
                ) CHARACTER SET utf8mb4
                """
            )

    def list_all(self) -> list[Job]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, category, title, company, salary, salary_min,
                       city, exp, skills, requirements
                FROM job_postings
                """)
            rows = cur.fetchall()
        return [self._row_to_job(r) for r in rows]

    def get(self, job_id: str) -> Job | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, category, title, company, salary, salary_min,
                       city, exp, skills, requirements
                FROM job_postings WHERE id = %s
                """,
                (job_id,),
            )
            r = cur.fetchone()
        return self._row_to_job(r) if r is not None else None

    def add(self, job: Job) -> Job:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_postings
                    (id, category, title, company, salary, salary_min,
                     city, exp, skills, requirements)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    category=VALUES(category), title=VALUES(title),
                    company=VALUES(company), salary=VALUES(salary),
                    salary_min=VALUES(salary_min), city=VALUES(city),
                    exp=VALUES(exp), skills=VALUES(skills),
                    requirements=VALUES(requirements)
                """,
                (job.id, job.category, job.title, job.company, job.salary,
                 job.salary_min, job.city, job.exp,
                 json.dumps(job.skills, ensure_ascii=False),
                 json.dumps(job.requirements, ensure_ascii=False)),
            )
        return job

    def delete(self, job_id: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM job_postings WHERE id = %s", (job_id,))
            return cur.rowcount > 0

    @staticmethod
    def _row_to_job(r) -> Job:
        def _loads(v):
            if not v:
                return []
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return []
        return Job(
            id=r[0], category=r[1] or "", title=r[2] or "", company=r[3] or "",
            salary=r[4] or "", salary_min=int(r[5] or 0), city=r[6] or "",
            exp=r[7] or "", skills=_loads(r[8]), requirements=_loads(r[9]),
        )
