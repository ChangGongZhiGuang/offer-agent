"""端到端: 起 jd MCP server 子进程, 验证 lookup_jd 命中与回退。"""
from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from interviewforge.mcp.client import MCPClientPool, ServerSpec


@pytest.fixture()
def pool():
    p = MCPClientPool([ServerSpec(
        name="jd", module="interviewforge.mcp_servers.jd_server")])
    p.start()
    yield p
    p.stop()


def test_lookup_jd_hit(pool):
    res = pool.call("jd", "lookup_jd", {"company": "ACME", "role": "backend"})
    assert res["company"] == "ACME" and res["role"] == "backend"
    assert "MySQL" in res["requirements"]


def test_lookup_jd_falls_back_to_generic(pool):
    res = pool.call("jd", "lookup_jd",
                    {"company": "unknown-co", "role": "backend"})
    assert res["requirements"]
