"""OpenAI 兼容模型客户端封装。唯一与模型 API 通信的地方。"""
from __future__ import annotations

import time
from typing import Sequence

from interviewforge.types import Message


class ModelClientError(RuntimeError):
    """归一化的模型调用错误 (重试耗尽后抛出)。"""


class ModelClient:
    def __init__(
        self,
        client=None,
        *,
        model_name: str,
        embed_model_name: str = "text-embedding-3-small",
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ):
        self._client = client
        self._model_name = model_name
        self._embed_model_name = embed_model_name
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    @classmethod
    def from_settings(cls, settings) -> "ModelClient":
        """用 Settings 构造真实 openai 客户端。"""
        from openai import OpenAI
        client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        return cls(
            client=client,
            model_name=settings.model_name,
            embed_model_name=settings.embed_model_name,
        )

    def _with_retry(self, fn):
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return fn()
            except Exception as exc:  # 归一化: 任何底层异常都重试
                last_exc = exc
                if attempt < self._max_retries - 1:
                    time.sleep(self._backoff_base * (2 ** attempt))
        raise ModelClientError(str(last_exc)) from last_exc

    def chat(self, messages: Sequence[Message], **kwargs) -> str:
        payload = [m.to_dict() for m in messages]

        def _call():
            resp = self._client.chat.completions.create(
                model=self._model_name, messages=payload, **kwargs
            )
            return resp.choices[0].message.content

        return self._with_retry(_call)

    def embed(self, texts: Sequence[str], *, batch_size: int = 10) -> list[list[float]]:
        items = list(texts)
        result: list[list[float]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]

            def _call(c=chunk):
                resp = self._client.embeddings.create(
                    model=self._embed_model_name, input=c
                )
                return [item.embedding for item in resp.data]

            result.extend(self._with_retry(_call))
        return result
