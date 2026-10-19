"""ReportGenerator: 维度聚合 + LLM 总评, 产维度雷达报告。"""
from __future__ import annotations

from interviewforge.subagents.base import parse_structured
from interviewforge.types import Message, Role

_SYSTEM = "你是面试官, 基于维度得分与薄弱点写中肯总评与改进建议, 只输出 JSON。"


def _aggregate(episodic: list[dict]) -> dict:
    scores = [e["score"] for e in episodic if "score" in e]
    answered = len(scores)
    overall = sum(scores) / answered if answered else 0
    by_dim: dict[str, list[int]] = {}
    for e in episodic:
        dim = e.get("dimension")
        if dim and "score" in e:
            by_dim.setdefault(dim, []).append(e["score"])
    dimensions = [{"name": d, "score": sum(v) / len(v)} for d, v in by_dim.items()]
    weakness: list[str] = []
    for e in episodic:
        for t in e.get("weakness_tags", []) or []:
            if t not in weakness:
                weakness.append(t)
    per_question = [{"question_id": e.get("question_id"), "score": e.get("score"),
                     "dimension": e.get("dimension"), "notes": e.get("notes", "")}
                    for e in episodic]
    return {"answered": answered, "avg_score": overall, "overall_score": overall,
            "dimensions": dimensions, "per_question": per_question,
            "weakness_tags": weakness}


class ReportGenerator:
    def __init__(self, model_client=None):
        self._model = model_client

    def build(self, episodic: list[dict], *, profile_text: str = "") -> dict:
        report = _aggregate(episodic)
        summary, suggestions = self._narrative(report, profile_text)
        report["summary"] = summary
        report["suggestions"] = suggestions
        return report

    def _narrative(self, report: dict, profile_text: str) -> tuple[str, list[str]]:
        if self._model is None or report["answered"] == 0:
            avg = report["overall_score"]
            verdict = "表现合格" if avg >= 3 else "基础待加强"
            return (f"共答 {report['answered']} 题, 综合 {avg:.1f} 分, {verdict}。",
                    [f"重点复盘: {t}" for t in report["weakness_tags"][:3]])
        dims = ", ".join(f"{d['name']}:{d['score']:.1f}" for d in report["dimensions"])
        prompt = (
            f"候选人画像:\n{profile_text}\n"
            f"维度得分: {dims}\n综合分: {report['overall_score']:.2f}\n"
            f"薄弱标签: {', '.join(report['weakness_tags'])}\n"
            '请以 JSON 返回 {"summary": 一段总评, "suggestions": [3条针对性改进建议]}。'
        )
        try:
            reply = self._model.chat([
                Message(role=Role.SYSTEM, content=_SYSTEM),
                Message(role=Role.USER, content=prompt),
            ])
            data = parse_structured(reply)
            return data.get("summary", ""), list(data.get("suggestions", []) or [])
        except Exception:
            avg = report["overall_score"]
            return (f"综合 {avg:.1f} 分。", [f"重点复盘: {t}" for t in report["weakness_tags"][:3]])
