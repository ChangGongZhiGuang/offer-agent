"""append-only JSONL 转录。是 episodic memory 的物理载体, 可重放/审计/resume。"""
from __future__ import annotations

import json
from pathlib import Path

from interviewforge.types import TranscriptEvent


class Transcript:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: TranscriptEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def replay(self) -> list[TranscriptEvent]:
        if not self.path.exists():
            return []
        events: list[TranscriptEvent] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(TranscriptEvent.from_dict(json.loads(line)))
        return events
