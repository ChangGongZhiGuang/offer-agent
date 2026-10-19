import time

from interviewforge.types import Message, Role, TranscriptEvent


def test_message_roundtrip():
    m = Message(role=Role.USER, content="你好")
    d = m.to_dict()
    assert d == {"role": "user", "content": "你好"}
    assert Message.from_dict(d) == m


def test_message_rejects_unknown_role():
    import pytest
    with pytest.raises(ValueError):
        Message(role="wizard", content="x")  # type: ignore[arg-type]


def test_transcript_event_roundtrip():
    ev = TranscriptEvent(type="user", ts=123.0, payload={"content": "hi"})
    d = ev.to_dict()
    assert d == {"type": "user", "ts": 123.0, "payload": {"content": "hi"}}
    assert TranscriptEvent.from_dict(d) == ev


def test_transcript_event_defaults_ts_to_now():
    before = time.time()
    ev = TranscriptEvent(type="transition", payload={})
    assert ev.ts >= before
