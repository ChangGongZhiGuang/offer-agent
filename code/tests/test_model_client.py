import pytest

from interviewforge.model_client import ModelClient, ModelClientError
from interviewforge.types import Message, Role


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeChatCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeEmbeddingItem:
    def __init__(self, vec):
        self.embedding = vec


class _FakeEmbeddingResponse:
    def __init__(self, vecs):
        self.data = [_FakeEmbeddingItem(v) for v in vecs]


class _FakeClient:
    """模拟 openai.OpenAI 的 chat.completions.create / embeddings.create。"""
    def __init__(self, chat_behavior=None, embed_vecs=None):
        self._chat_behavior = chat_behavior or []
        self._embed_vecs = embed_vecs or []
        self.chat_calls = 0

        outer = self

        class _Completions:
            def create(self, **kwargs):
                idx = outer.chat_calls
                outer.chat_calls += 1
                behavior = outer._chat_behavior[idx]
                if isinstance(behavior, Exception):
                    raise behavior
                return _FakeChatCompletion(behavior)

        class _Chat:
            completions = _Completions()

        class _Embeddings:
            def create(self, **kwargs):
                return _FakeEmbeddingResponse(outer._embed_vecs)

        self.chat = _Chat()
        self.embeddings = _Embeddings()


def test_chat_returns_assistant_text():
    fake = _FakeClient(chat_behavior=["回答内容"])
    mc = ModelClient(client=fake, model_name="m")
    out = mc.chat([Message(role=Role.USER, content="问题")])
    assert out == "回答内容"
    assert fake.chat_calls == 1


def test_chat_retries_transient_then_succeeds():
    fake = _FakeClient(chat_behavior=[RuntimeError("boom"), "ok"])
    mc = ModelClient(client=fake, model_name="m", max_retries=2, backoff_base=0.0)
    out = mc.chat([Message(role=Role.USER, content="q")])
    assert out == "ok"
    assert fake.chat_calls == 2


def test_chat_exhausts_retries_raises_normalized_error():
    fake = _FakeClient(chat_behavior=[RuntimeError("a"), RuntimeError("b")])
    mc = ModelClient(client=fake, model_name="m", max_retries=2, backoff_base=0.0)
    with pytest.raises(ModelClientError):
        mc.chat([Message(role=Role.USER, content="q")])
    assert fake.chat_calls == 2


def test_embed_returns_vectors():
    fake = _FakeClient(embed_vecs=[[0.1, 0.2], [0.3, 0.4]])
    mc = ModelClient(client=fake, model_name="m", embed_model_name="e")
    out = mc.embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]
