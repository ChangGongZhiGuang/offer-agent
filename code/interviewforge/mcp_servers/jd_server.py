"""MCP server: JD 查询。stdio 传输; 用 `python -m interviewforge.mcp_servers.jd_server` 启动。

内置示例 JD; 后续可换 yaml/DB 后端而不动 client。
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("interviewforge.mcp.jd")

mcp = FastMCP("interviewforge-jd")

_JD_TABLE: dict[tuple[str, str], dict] = {
    ("acme", "backend"): {
        "requirements": ["MySQL", "Redis", "高并发", "微服务", "API 设计"],
        "nice_to_have": ["Kafka", "K8s"],
    },
    ("acme", "algorithm"): {
        "requirements": ["数据结构", "动态规划", "图论", "复杂度分析"],
        "nice_to_have": ["竞赛经验"],
    },
    ("generic", "backend"): {
        "requirements": ["数据库", "并发", "API 设计"],
        "nice_to_have": [],
    },
}


@mcp.tool()
def lookup_jd(company: str, role: str) -> dict:
    """查岗位要求, 返回 {company, role, requirements, nice_to_have}。未命中走 generic。"""
    key = (company.strip().lower(), role.strip().lower())
    body = _JD_TABLE.get(key) or _JD_TABLE.get(("generic", key[1])) or {
        "requirements": ["数据库", "并发", "API 设计"], "nice_to_have": []}
    logger.info("lookup_jd company=%s role=%s -> %s", company, role, "命中" if key in _JD_TABLE else "走 generic")
    return {"company": company, "role": role, **body}


if __name__ == "__main__":
    logger.info("jd_server 就绪 (内置 JD 表)")
    mcp.run()
