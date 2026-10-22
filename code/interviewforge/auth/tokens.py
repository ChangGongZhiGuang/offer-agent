"""登录凭证: 进程内 token → user_id 映射。

登录/注册时签发随机 token, 请求经 Authorization: Bearer <token> 回传解析。
服务重启后旧 token 失效 (用户/历史仍存于 MySQL), 需重新登录。
"""
from __future__ import annotations

import threading
from uuid import uuid4


class TokenStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._token_to_user: dict[str, str] = {}

    def issue(self, user_id: str) -> str:
        """为用户签发新 token (可多端并存)。"""
        token = uuid4().hex
        with self._lock:
            self._token_to_user[token] = user_id
        return token

    def resolve(self, token: str | None) -> str | None:
        """token → user_id; 无效/缺失返回 None。"""
        if not token:
            return None
        with self._lock:
            return self._token_to_user.get(token)

    def revoke(self, token: str) -> None:
        """登出: 移除该 token。"""
        with self._lock:
            self._token_to_user.pop(token, None)

    def revoke_all(self, user_id: str) -> int:
        """吊销某用户全部 token (改密/注销后强制重新登录); 返回吊销数。"""
        with self._lock:
            dead = [t for t, uid in self._token_to_user.items() if uid == user_id]
            for t in dead:
                self._token_to_user.pop(t, None)
        return len(dead)
