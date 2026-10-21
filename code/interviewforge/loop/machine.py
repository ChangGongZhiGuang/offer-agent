"""InterviewLoop: 有界 PEV 状态机, 编排前 5 阶段所有模块跑通整场面试。"""
from __future__ import annotations

from interviewforge.context.compaction import ContextState
from interviewforge.loop.planner import Plan, Planner, should_follow_up
from interviewforge.loop.types import Bounds, HaltReason, Phase, LoopState
from interviewforge.loop.verify import verify_plan, verify_question, verify_score
from interviewforge.memory.base import MemoryService
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.persistence.transcript import Transcript
from interviewforge.subagents.base import SubTask
from interviewforge.types import Message, Role, TranscriptEvent


class InterviewLoop:
    def __init__(self, *, memory: MemoryService, examiner, grader,
                 planner: Planner, registry, search_adapter,
                 transcript: Transcript | None = None, bounds: Bounds | None = None,
                 pipeline=None, token_budget: int = 24000,
                 compaction_ratio: float = 0.85):
        self.memory = memory
        self.examiner = examiner
        self.grader = grader
        self.planner = planner
        self.registry = registry
        self.search_adapter = search_adapter
        self.transcript = transcript
        self.bounds = bounds or Bounds()
        self.pipeline = pipeline
        self.token_budget = token_budget
        self.compaction_ratio = compaction_ratio
        self.state: LoopState | None = None

    # ---- 生命周期 ----
    def start(self, *, role: str, topic: str, profile: str = "",
              difficulty: str = "medium",
              jd_keywords: list[str] | None = None,
              dimension: str | None = None) -> None:
        self.state = LoopState(role=role, topic=topic, profile=profile,
                               difficulty=difficulty,
                               jd_keywords=list(jd_keywords or []),
                               dimension=dimension)

    # ---- 相位/转移记录 ----
    def _to(self, phase: Phase, *, gate: str | None = None) -> None:
        frm = self.state.phase.value
        self.state.phase = phase
        self._record("transition", {"from": frm, "to": phase.value, "gate": gate})

    def _record(self, type_: str, payload: dict) -> None:
        if self.transcript is not None:
            self.transcript.append(TranscriptEvent(type=type_, payload=payload))

    def _halt(self, reason: HaltReason) -> None:
        self.state.halted = reason
        self._to(Phase.HALT, gate=reason.value)

    def _halted(self) -> bool:
        return self.state.halted is not None

    def _replan(self, reason: str) -> bool:
        """记录失败并重规划; 超 max_replans 则 HALT。返回 True=可继续。"""
        self.state.last_error = reason
        self.state.replan_count += 1
        self._to(Phase.PLAN, gate=f"fail:{reason}")
        if self.state.replan_count > self.bounds.max_replans:
            self._halt(HaltReason.MAX_REPLANS)
            return False
        return True

    # ---- 出题 ----
    def ask_question(self) -> str | None:
        if self._halted():
            return None
        if self.state.turn >= self.bounds.max_turns:
            self._halt(HaltReason.MAX_TURNS)
            return None
        self.state.replan_count = 0
        while True:
            self._to(Phase.PLAN)
            plan = self.planner.plan_ask(self.state)
            remaining = self.bounds.max_questions - len(self.state.asked_ids)
            gate = verify_plan(plan, remaining_questions=remaining,
                               max_tool_calls=self.bounds.max_tool_calls_per_turn)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            # A: 让 SearchAdapter 这一轮检索用 Planner 拼好的 query (含维度/JD/简历),
            # 一次性消费, 不影响后续轮的回退行为。
            setter = getattr(self.search_adapter, "set_next_query", None)
            if setter is not None and plan.query:
                setter(plan.query)
            self._to(Phase.EXECUTE)
            item = None
            plan_obj = self.state.session_plan
            if plan_obj is not None and plan_obj.items:
                item = plan_obj.items[min(self.state.turn, len(plan_obj.items) - 1)]
            topic = item.topic if item else self.state.topic
            difficulty = item.difficulty if item else self.state.difficulty
            dimension = item.dimension if item else self.state.dimension
            sub = self.examiner.run(SubTask(goal="出题", inputs={
                "role": self.state.role, "topic": topic,
                "difficulty": difficulty, "dimension": dimension,
                "profile": self.state.profile,
                "profile_struct": self.state.profile_struct}))
            structured = dict(sub.structured)
            qid = self.search_adapter.last_id or f"q-{self.state.turn}"
            structured["question_id"] = qid
            # 注意: 不再用题库原文覆盖 LLM 题干 (混合方案要保留个性化改写)
            # D: 把题库的参考答案随题目一起带入 working memory, 供 Grader 评分时对照
            ref_answer = getattr(self.search_adapter, "last_reference_answer", None)
            if ref_answer:
                structured["reference_answer"] = ref_answer
            # 题库追问引导 (fu) 随题带入: 主问链未闭合时供追问题目生成参考
            fu_hint = getattr(self.search_adapter, "last_fu", "") or ""
            if fu_hint:
                structured["fu_hint"] = fu_hint
            structured.setdefault("dimension", dimension)
            self._to(Phase.VERIFY)
            gate = verify_question(structured, self.state.asked_ids)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            self.state.asked_ids.append(qid)
            self.state.current_question = structured
            self.memory.remember(MemoryItem(kind=MemoryKind.WORKING, content=structured))
            self.state.recent_messages.append(
                Message(role=Role.ASSISTANT, content=structured["question"]))
            self.state.turn += 1
            self._to(Phase.RESPOND)
            self._maybe_compact()
            self._to(Phase.IDLE)
            return structured["question"]

    # ---- 评分 ----
    def submit_answer(self, answer: str) -> dict | None:
        """作答入口: 主题/追问两条路径共用评分循环, 评分后决定是否继续追问。

        返回值除评分字段外携带追问信号:
        follow_up_question (紧接的追问题干) / follow_up_of (所属主问) /
        is_follow_up (本次被评的是追问) / follow_up_done (追问链已闭合)。
        """
        if self._halted():
            return None
        if self.state.current_question is None and self.state.pending_follow_up is None:
            raise RuntimeError("no current question to answer")
        # 追问优先: pending 非空时本次回答针对追问, 否则针对主题
        q = self.state.pending_follow_up or self.state.current_question
        is_fu = self.state.pending_follow_up is not None
        self.state.recent_messages.append(Message(role=Role.USER, content=answer))
        self.state.replan_count = 0
        while True:
            self._to(Phase.PLAN)
            plan = self.planner.plan_grade(self.state)
            gate = verify_plan(plan, remaining_questions=1,
                               max_tool_calls=self.bounds.max_tool_calls_per_turn)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            self._to(Phase.EXECUTE)
            sub = self.grader.run(SubTask(goal="评分", inputs={
                "question": q["question"], "rubric": q.get("rubric", ""),
                "answer": answer, "question_id": q["question_id"],
                "reference_answer": q.get("reference_answer", ""),
                "dimension": q.get("dimension"),
                "is_follow_up": is_fu,
                "parent_question_id": q.get("parent_question_id")}))
            structured = sub.structured
            self._to(Phase.VERIFY)
            gate = verify_score(structured)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            # 逐题问答流水: 题文 + 答案 + 得分/评语; 追问回合标记链归属
            entry = {
                "question_id": q.get("question_id"),
                "question": q.get("question", ""),
                "answer": answer,
                "score": structured.get("score"),
                "feedback": structured.get("feedback", ""),
                "dimension": q.get("dimension"),
                "is_follow_up": is_fu,
            }
            if is_fu:
                entry["parent_question_id"] = q.get("parent_question_id")
            self.state.qa_log.append(entry)
            self.state.recent_messages.append(
                Message(role=Role.ASSISTANT, content=structured.get("feedback", "")))
            self.state.pending_follow_up = None
            # 追问决策: Grader 的 LLM 判定 + 规则边界双重把关, 再受硬上限约束
            result = dict(structured)
            result["is_follow_up"] = is_fu
            parent_qid = (q.get("parent_question_id") if is_fu
                          else q.get("question_id"))
            follow_up = None
            if parent_qid and should_follow_up(self.state, structured,
                                               bounds=self.bounds,
                                               parent_qid=parent_qid) \
                    and self.state.turn + self.state.total_follow_ups < self.bounds.max_turns:
                follow_up = self._generate_follow_up(q, answer, structured, parent_qid)
            if follow_up is not None:
                self.state.pending_follow_up = follow_up
                result["follow_up_question"] = follow_up["question"]
                result["follow_up_of"] = parent_qid
                # 主问链未闭合: current_question 保留, 供下一层追问继承参考答案
            else:
                self.state.current_question = None
                if is_fu:
                    result["follow_up_done"] = True
            self._to(Phase.RESPOND)
            self._maybe_compact()
            self._to(Phase.IDLE)
            return result

    # ---- 追问生成小循环 (PLAN→EXECUTE→VERIFY, 失败走既有 _replan) ----
    def _generate_follow_up(self, prev_q: dict, prev_answer: str,
                            score_result: dict, parent_qid: str) -> dict | None:
        """基于上一题问答链生成一道追问; 无可用时返回 None (链闭合)。"""
        st = self.state
        depth = st.follow_up_counts.get(parent_qid, 0) + 1
        while True:
            self._to(Phase.PLAN)
            planner_fu = getattr(self.planner, "plan_follow_up", None)
            plan = planner_fu(st) if planner_fu is not None else Plan(
                intent="follow_up", tool_calls=[],
                expected_outcome="一道针对上一答的追问")
            gate = verify_plan(plan, remaining_questions=1,
                               max_tool_calls=self.bounds.max_tool_calls_per_turn)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            self._to(Phase.EXECUTE)
            main = st.current_question or {}
            sub = self.examiner.run(SubTask(goal="出追问", inputs={
                "role": st.role, "topic": st.topic,
                "dimension": prev_q.get("dimension") or main.get("dimension"),
                "profile": st.profile,
                "profile_struct": st.profile_struct,
                "prev_question": prev_q.get("question", ""),
                "prev_answer": prev_answer,
                "feedback": score_result.get("feedback", ""),
                "weakness_tags": score_result.get("weakness_tags", []),
                "follow_up_hint": score_result.get("follow_up_hint", ""),
                "fu_hint": prev_q.get("fu_hint") or main.get("fu_hint", "")}))
            structured = dict(sub.structured)
            structured["question_id"] = f"{parent_qid}-fu{depth}"
            structured["parent_question_id"] = parent_qid
            structured["depth"] = depth
            # 追问评分沿用主题命中的参考答案/维度, 保证 Grader/报告口径一致
            if "reference_answer" not in structured and main.get("reference_answer"):
                structured["reference_answer"] = main["reference_answer"]
            structured.setdefault("dimension", prev_q.get("dimension"))
            self._to(Phase.VERIFY)
            gate = verify_question(structured, st.asked_ids)
            if not gate.passed:
                if not self._replan(gate.reason):
                    return None
                continue
            st.follow_up_counts[parent_qid] = depth
            st.total_follow_ups += 1
            st.recent_messages.append(Message(role=Role.ASSISTANT,
                                              content=structured["question"]))
            self._record("follow_up", {"parent": parent_qid, "depth": depth,
                                       "question_id": structured["question_id"]})
            return structured

    # ---- 收尾 ----
    def finish(self) -> dict:
        report = self.registry.call("generate_report")
        self._halt(HaltReason.COMPLETED)
        return report

    # ---- 条件压缩 ----
    def _maybe_compact(self) -> None:
        if self.pipeline is None:
            return
        ctx = ContextState(messages=list(self.state.recent_messages),
                           pinned=set(), token_budget=self.token_budget)
        before = ctx.recompute_tokens()
        if before <= self.token_budget * self.compaction_ratio:
            return
        self._to(Phase.COMPACT)
        results = self.pipeline.run(ctx)
        self.state.recent_messages = ctx.messages
        self._record("compact", {"layers": [r.layer_name for r in results],
                                 "before": before, "after": ctx.current_tokens})
