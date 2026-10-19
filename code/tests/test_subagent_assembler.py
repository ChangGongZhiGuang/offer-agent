"""子 Agent 经 ContextAssembler 注入 procedural 规则 + semantic 画像 (item 3 接线)。"""
from interviewforge.context.assembler import ContextAssembler, assemble_subagent_system
from interviewforge.memory.base import MemoryService
from interviewforge.memory.episodic import EpisodicMemory
from interviewforge.memory.procedural import ProceduralMemory
from interviewforge.memory.semantic import InMemorySemanticBackend, SemanticMemory
from interviewforge.memory.types import MemoryItem, MemoryKind
from interviewforge.memory.working import WorkingMemory
from interviewforge.subagents.base import SubTask
from interviewforge.subagents.examiner import Examiner
from interviewforge.subagents.grader import Grader
from interviewforge.tools.registry import Tool, ToolRegistry, ToolSpec


class FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.last_messages = None

    def chat(self, messages):
        self.last_messages = messages
        return self.reply


def _memory(tmp_path, *, with_profile=True):
    svc = MemoryService(
        working=WorkingMemory(),
        episodic=EpisodicMemory(tmp_path / "e.jsonl"),
        semantic=SemanticMemory(InMemorySemanticBackend()),
        procedural=ProceduralMemory([
            {"id": "no_duplicate_question", "desc": "同一场不得重复出题"},
            {"id": "score_in_range", "desc": "评分必须 1-5"},
        ]),
    )
    if with_profile:
        svc.remember(MemoryItem(kind=MemoryKind.SEMANTIC,
                                content={"role": "后端", "fact": "技能栈: Redis, MySQL"}))
    return svc


def _exam_registry():
    reg = ToolRegistry()
    spec = ToolSpec(name="search_questions", description="",
                    parameters={"role": {"required": True}, "topic": {"required": True},
                                "difficulty": {"required": False}})
    reg.register(Tool(spec, lambda role, topic, difficulty=None: [
        {"question_id": "be-1", "question": "锚点题", "difficulty": "hard"}]))
    return reg


def _grade_registry():
    reg = ToolRegistry()
    reg.register(Tool(ToolSpec("record_answer", "", {"question_id": {"required": True},
                                                     "score": {"required": True}}),
                      lambda **k: {"recorded": k.get("question_id")}))
    return reg


def test_assemble_subagent_system_injects_rules_and_profile(tmp_path):
    asm = ContextAssembler(token_budget=10000)
    sysctx = assemble_subagent_system(asm, _memory(tmp_path),
                                      base_system="你是出题官", role="后端")
    assert "你是出题官" in sysctx
    assert "no_duplicate_question" in sysctx        # procedural 规则被读到
    assert "Redis" in sysctx                         # semantic 画像被读到


def test_examiner_system_prompt_carries_rules_and_profile(tmp_path):
    model = FakeModel('{"question": "Q", "rubric": "r", "expected_points": []}')
    ex = Examiner(model, _exam_registry(), memory=_memory(tmp_path),
                  assembler=ContextAssembler(10000), role="后端")
    ex.run(SubTask(goal="出题", inputs={"role": "后端", "topic": "redis"}))
    sys_msg = model.last_messages[0].content
    assert "no_duplicate_question" in sys_msg
    assert "Redis" in sys_msg


def test_grader_system_prompt_carries_rules_and_profile(tmp_path):
    model = FakeModel('{"score": 4, "weakness_tags": [], "feedback": "ok"}')
    gr = Grader(model, _grade_registry(), memory=_memory(tmp_path),
                assembler=ContextAssembler(10000), role="后端")
    gr.run(SubTask(goal="评分", inputs={"question": "Q", "answer": "A",
                                        "question_id": "be-1"}))
    sys_msg = model.last_messages[0].content
    assert "score_in_range" in sys_msg               # grader 现在也能读到全局规则
    assert "Redis" in sys_msg


def test_subagent_without_memory_keeps_base_system(tmp_path):
    """未注入 memory/assembler 时, 系统提示原样 (向后兼容)。"""
    model = FakeModel('{"question": "Q", "rubric": "r", "expected_points": []}')
    ex = Examiner(model, _exam_registry())
    ex.run(SubTask(goal="出题", inputs={"role": "后端", "topic": "redis"}))
    sys_msg = model.last_messages[0].content
    assert "no_duplicate_question" not in sys_msg
    assert sys_msg.startswith("你是严谨的面试出题官")
