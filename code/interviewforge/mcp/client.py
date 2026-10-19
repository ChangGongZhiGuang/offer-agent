"""MCPClientPool: 后台线程跑 asyncio event loop, 主代码以同步方式调用 MCP server。

设计要点:
- 一个 pool 管理多台 server (按名字索引)。
- 每台 server 一个长连接 ClientSession (stdio_client + ClientSession 上下文常驻)。
- pool.call(server, tool, args) 用 run_coroutine_threadsafe 投递到后台 loop, 阻塞拿结果。
- start() 在后台线程拉起 loop, 并对每台 server 跑 initialize + 进入异步上下文。
- stop() 反向退出所有上下文, 关闭 loop, join 线程。
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass(frozen=True)
class ServerSpec:
    """启动一台 MCP server 的子进程参数。"""
    name: str
    module: str            # python -m <module>
    extra_args: tuple[str, ...] = ()
    env: dict | None = None  # 透传给子进程的环境变量 (如 INTERVIEWFORGE_MCP_FAKE_EMBED)

    def to_params(self) -> StdioServerParameters:
        args = ["-m", self.module, *self.extra_args]
        return StdioServerParameters(command=sys.executable, args=list(args),
                                     env=self.env)


def _unwrap(result: Any) -> Any:
    """把 mcp CallToolResult 拆成 Python 值。优先 structuredContent, 退而 JSON 解析文本。"""
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        # FastMCP 对返回值会包一层 {"result": <value>}; 透明剥掉。
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return text
    return None


class MCPClientPool:
    """启动一组 MCP server 子进程并持有长连接, 主线程以同步 call() 调用。"""

    def __init__(self, specs: list[ServerSpec]):
        self._specs = specs
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, ClientSession] = {}
        self._stack: AsyncExitStack | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

    # ---- 生命周期 ----
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="mcp-pool", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError(f"MCPClientPool failed to start: {self._start_error}")

    def stop(self) -> None:
        if self._loop is None or self._thread is None:
            return
        fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        try:
            fut.result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop = None
        self._thread = None

    def __enter__(self) -> "MCPClientPool":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ---- 调用 ----
    def call(self, server: str, tool: str, args: dict | None = None,
             timeout: float = 30.0) -> Any:
        if self._loop is None:
            raise RuntimeError("pool not started")
        session = self._sessions.get(server)
        if session is None:
            raise KeyError(f"unknown MCP server: {server}")
        coro = session.call_tool(tool, args or {})
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        result = fut.result(timeout=timeout)
        if getattr(result, "isError", False):
            raise RuntimeError(f"MCP tool {server}.{tool} returned error: {result}")
        return _unwrap(result)

    def list_tools(self, server: str, timeout: float = 10.0) -> list[str]:
        session = self._sessions.get(server)
        if session is None:
            raise KeyError(f"unknown MCP server: {server}")
        fut = asyncio.run_coroutine_threadsafe(session.list_tools(), self._loop)
        resp = fut.result(timeout=timeout)
        return [t.name for t in resp.tools]

    # ---- 内部: 后台线程的 event loop ----
    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._bootstrap())
        except BaseException as exc:
            self._start_error = exc
            self._ready.set()
            return
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    async def _bootstrap(self) -> None:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        for spec in self._specs:
            read, write = await self._stack.enter_async_context(
                stdio_client(spec.to_params()))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[spec.name] = session

    async def _shutdown(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self._sessions.clear()
