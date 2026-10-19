import pytest

pytest.importorskip("fastapi")

from interviewforge.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    QuestionResponse,
    ReportResponse,
    StartRequest,
    StartResponse,
    StatusResponse,
)


def test_start_request_defaults():
    r = StartRequest(role="后端", topic="redis")
    assert r.profile == "" and r.num_questions == 3


def test_question_response_optional_fields():
    r = QuestionResponse(done=True, phase="halt")
    assert r.question is None and r.question_id is None


def test_answer_request_requires_answer():
    with pytest.raises(Exception):
        AnswerRequest()


def test_response_models_roundtrip():
    assert StartResponse(session_id="s1", role="后端", topic="redis").session_id == "s1"
    assert AnswerResponse(score=4, weakness_tags=["x"], feedback="ok").score == 4
    assert ReportResponse(answered=2, avg_score=3.5).answered == 2
    assert StatusResponse(session_id="s1", phase="idle", turn=1, asked=1,
                          halted=None).halted is None
