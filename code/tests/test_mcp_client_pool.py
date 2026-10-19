"""MCPClientPool: 同时持有多台 server, 同步外观可重复调用, stop 幂等。"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("mcp")

from interviewforge.mcp.client import MCPClientPool, ServerSpec

# questions 子进程强制 fake-embed 离线模式: 否则它会 load_dotenv() 读 .env,
# 按 INTERVIEWFORGE_VECTOR_STORE/MYSQL_* 连真实 MySQL + 真实 embedding (甚至
# 重建持久 Chroma 目录), 使本测试依赖外部服务且产生真实调用成本。
_FAKE_ENV = {**os.environ, "INTERVIEWFORGE_MCP_FAKE_EMBED": "1"}


def test_pool_holds_multiple_servers_and_repeats():
    pool = MCPClientPool([
        ServerSpec(name="questions",
                   module="interviewforge.mcp_servers.questions_server",
                   env=_FAKE_ENV),
        ServerSpec(name="jd", module="interviewforge.mcp_servers.jd_server"),
    ])
    pool.start()
    try:
        for _ in range(3):
            qs = pool.call("questions", "search_questions",
                           {"role": "算法", "topic": "动态规划"})
            assert qs and qs[0]["question_id"] == "algo-1"
            jd = pool.call("jd", "lookup_jd",
                           {"company": "ACME", "role": "algorithm"})
            assert "数据结构" in jd["requirements"]
    finally:
        pool.stop()
    pool.stop()  # 幂等


def test_unknown_server_raises():
    pool = MCPClientPool([ServerSpec(
        name="jd", module="interviewforge.mcp_servers.jd_server")])
    pool.start()
    try:
        with pytest.raises(KeyError):
            pool.call("nope", "lookup_jd", {"company": "x", "role": "y"})
    finally:
        pool.stop()
