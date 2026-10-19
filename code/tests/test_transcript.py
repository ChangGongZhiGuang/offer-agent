from interviewforge.persistence.transcript import Transcript
from interviewforge.types import TranscriptEvent


def test_append_and_replay_roundtrip(tmp_path):
    path = tmp_path / "session.jsonl"
    t = Transcript(path)
    t.append(TranscriptEvent(type="user", ts=1.0, payload={"content": "hi"}))
    t.append(TranscriptEvent(type="assistant", ts=2.0, payload={"content": "yo"}))

    events = Transcript(path).replay()
    assert [e.type for e in events] == ["user", "assistant"]
    assert events[0].payload == {"content": "hi"}
    assert events[1].ts == 2.0


def test_append_is_append_only(tmp_path):
    path = tmp_path / "session.jsonl"
    Transcript(path).append(TranscriptEvent(type="user", ts=1.0, payload={}))
    Transcript(path).append(TranscriptEvent(type="user", ts=2.0, payload={}))
    # 第二个 Transcript 复用同一文件, 追加而非覆盖
    assert len(Transcript(path).replay()) == 2


def test_replay_missing_file_returns_empty(tmp_path):
    assert Transcript(tmp_path / "nope.jsonl").replay() == []


def test_unicode_preserved(tmp_path):
    path = tmp_path / "session.jsonl"
    t = Transcript(path)
    t.append(TranscriptEvent(type="user", ts=1.0, payload={"content": "分布式锁"}))
    assert t.replay()[0].payload["content"] == "分布式锁"
