import json
import logging
from io import BytesIO
from pathlib import Path

import pytest

from english_learning.config import Settings
from english_learning.domain import AnswerEvaluation, Exercise
from english_learning.llm import OllamaClient, OllamaError


def test_structured_request_logs_status_without_logging_content(
    monkeypatch,
    caplog,
) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "verdict": "correct",
                    "score": 1,
                    "explanation": "Correct.",
                    "review_again": False,
                }
            )
        }
    }
    monkeypatch.setattr(
        "english_learning.llm.urlopen",
        lambda request, timeout: BytesIO(json.dumps(response_body).encode()),
    )
    caplog.set_level(logging.INFO, logger="english_learning.llm")
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )

    result = client._structured_chat(
        prompt_name="answer_evaluate.md",
        user_content="private learner content",
        response_model=AnswerEvaluation,
        temperature=0,
    )

    assert result.verdict == "correct"
    assert "Ollama request started task=answer_evaluate.md" in caplog.text
    assert "Ollama request completed task=answer_evaluate.md" in caplog.text
    assert "private learner content" not in caplog.text


def test_invalid_structured_response_logs_validation_reason(
    monkeypatch,
    caplog,
) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "verdict": "correct",
                    "score": 1,
                }
            )
        }
    }
    monkeypatch.setattr(
        "english_learning.llm.urlopen",
        lambda request, timeout: BytesIO(json.dumps(response_body).encode()),
    )
    caplog.set_level(logging.WARNING, logger="english_learning.llm")
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )

    with pytest.raises(OllamaError):
        client._structured_chat(
            prompt_name="answer_evaluate.md",
            user_content="private learner content",
            response_model=AnswerEvaluation,
            temperature=0,
        )

    assert "reason=ValidationError" in caplog.text
    assert "explanation" in caplog.text
    assert "review_again" in caplog.text
    assert "private learner content" not in caplog.text


def test_evaluate_answers_sends_one_batch_request(monkeypatch) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "evaluations": [
                        {
                            "exercise_index": index,
                            "evaluation": {
                                "verdict": "correct",
                                "score": 1,
                                "explanation": "Correct.",
                                "review_again": False,
                            },
                        }
                        for index in (2, 5)
                    ]
                }
            )
        }
    }
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return BytesIO(json.dumps(response_body).encode())

    monkeypatch.setattr("english_learning.llm.urlopen", fake_urlopen)
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )
    exercise = Exercise(
        exercise_type="fill_blank",
        instruction="Complete the sentence.",
        question="She ___.",
        expected_answers=["left"],
        explanation="Use the past tense.",
        primary_item_key="grammar_rule:1",
    )

    evaluations = client.evaluate_answers(
        [(2, exercise, "left"), (5, exercise, "left")]
    )

    assert set(evaluations) == {2, 5}
    assert len(requests) == 1
    payload = json.loads(requests[0].data)
    user_content = json.loads(payload["messages"][1]["content"])
    assert [item["exercise_index"] for item in user_content["answers"]] == [
        2,
        5,
    ]


def test_evaluate_answers_rejects_incomplete_batch(monkeypatch) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "evaluations": [
                        {
                            "exercise_index": 2,
                            "evaluation": {
                                "verdict": "correct",
                                "score": 1,
                                "explanation": "Correct.",
                                "review_again": False,
                            },
                        }
                    ]
                }
            )
        }
    }
    monkeypatch.setattr(
        "english_learning.llm.urlopen",
        lambda request, timeout: BytesIO(json.dumps(response_body).encode()),
    )
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )
    exercise = Exercise(
        exercise_type="fill_blank",
        instruction="Complete the sentence.",
        question="She ___.",
        expected_answers=["left"],
        explanation="Use the past tense.",
        primary_item_key="grammar_rule:1",
    )

    with pytest.raises(OllamaError, match="exactly one evaluation"):
        client.evaluate_answers(
            [(2, exercise, "left"), (5, exercise, "left")]
        )


def test_validate_vocabulary_inputs_returns_indexed_results(
    monkeypatch,
) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "validations": [
                        {
                            "input_index": 0,
                            "status": "corrected",
                            "suggested_input": "commute",
                            "explanation": "Corrected a spelling mistake.",
                        },
                        {
                            "input_index": 2,
                            "status": "valid",
                            "explanation": "This is a valid expression.",
                        },
                    ]
                }
            )
        }
    }
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return BytesIO(json.dumps(response_body).encode())

    monkeypatch.setattr("english_learning.llm.urlopen", fake_urlopen)
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )

    validations = client.validate_vocabulary_inputs(
        [(0, "comute"), (2, "a safe pair of hands")]
    )

    assert validations[0].suggested_input == "commute"
    assert validations[2].status == "valid"
    assert len(requests) == 1


def test_validate_inputs_rejects_incomplete_results(monkeypatch) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "validations": [
                        {
                            "input_index": 0,
                            "status": "valid",
                            "explanation": "This is valid.",
                        }
                    ]
                }
            )
        }
    }
    monkeypatch.setattr(
        "english_learning.llm.urlopen",
        lambda request, timeout: BytesIO(json.dumps(response_body).encode()),
    )
    client = OllamaClient(
        Settings(
            model="test-model",
            ollama_url="http://localhost:11434",
            database_path=Path("test.sqlite3"),
            learner_level="B2",
            english_variant="British",
        )
    )

    with pytest.raises(OllamaError, match="exactly one validation"):
        client.validate_grammar_inputs(
            [(0, "Use the present simple."), (1, "Use the past simple.")]
        )
