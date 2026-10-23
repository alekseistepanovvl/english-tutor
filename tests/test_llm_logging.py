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
        "load_duration": 500_000_000,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 2_000_000_000,
        "eval_count": 40,
        "eval_duration": 4_000_000_000,
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
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return BytesIO(json.dumps(response_body).encode())

    monkeypatch.setattr("english_learning.llm.urlopen", fake_urlopen)
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
        max_output_tokens=384,
    )

    assert result.verdict == "correct"
    payload = json.loads(requests[0].data)
    assert payload["think"] is False
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_predict"] == 384
    assert "Ollama request started task=answer_evaluate.md" in caplog.text
    assert "generated_tokens=40" in caplog.text
    assert "tokens_per_second=10.00" in caplog.text
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
            max_output_tokens=384,
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
    payload = json.loads(requests[0].data)
    user_content = json.loads(payload["messages"][1]["content"])
    assert "existing_saved_entries" not in user_content


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


def grammar_topic(title: str) -> dict:
    return {
        "title": title,
        "summary": f"Summary for {title}.",
        "level": "B2",
        "rules": [
            {
                "name": f"{title} rule",
                "explanation": "A concise explanation.",
                "pattern": "subject + verb",
                "verbs": [],
                "correct_examples": [
                    "This is the first example.",
                    "This is the second example.",
                ],
                "incorrect_examples": [],
                "exceptions": [],
                "notes": [],
                "topic_assignment": {
                    "approved_topics": [],
                    "proposed_topics": [],
                },
            }
        ],
        "tags": [],
    }


def test_generate_grammars_sends_one_indexed_batch(monkeypatch) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "topics": [
                        {
                            "input_index": 1,
                            "topic": grammar_topic("Past simple"),
                        },
                        {
                            "input_index": 0,
                            "topic": grammar_topic("Present simple"),
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

    topics = client.generate_grammars(
        ["Use the present simple.", "Use the past simple."],
        [{"slug": "tenses", "name": "Tenses"}],
    )

    assert [topic.title for topic in topics] == [
        "Present simple",
        "Past simple",
    ]
    assert len(requests) == 1
    payload = json.loads(requests[0].data)
    user_content = json.loads(payload["messages"][1]["content"])
    assert [
        item["input_index"] for item in user_content["input_notes"]
    ] == [0, 1]
    assert payload["options"]["num_predict"] == 4096


def test_generate_grammars_rejects_incomplete_batch(monkeypatch) -> None:
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "topics": [
                        {
                            "input_index": 0,
                            "topic": grammar_topic("Present simple"),
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

    with pytest.raises(OllamaError, match="every input in the grammar batch"):
        client.generate_grammars(
            ["Use the present simple.", "Use the past simple."]
        )


def test_generate_grammars_uses_bounded_batches(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "topics": [
                            {
                                "input_index": item["input_index"],
                                "topic": grammar_topic(
                                    f"Topic {item['input_index']}"
                                ),
                            }
                            for item in user_content["input_notes"]
                        ]
                    }
                )
            }
        }
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

    topics = client.generate_grammars(
        [f"Grammar note {index}" for index in range(5)]
    )

    assert [topic.title for topic in topics] == [
        "Topic 0",
        "Topic 1",
        "Topic 2",
        "Topic 3",
        "Topic 4",
    ]
    assert len(requests) == 3
    payloads = [json.loads(request.data) for request in requests]
    batches = [
        json.loads(payload["messages"][1]["content"])["input_notes"]
        for payload in payloads
    ]
    assert [
        [item["input_index"] for item in batch]
        for batch in batches
    ] == [[0, 1], [2, 3], [4]]
    assert [
        payload["options"]["num_predict"] for payload in payloads
    ] == [4096, 4096, 2048]


def test_generate_grammars_rejects_partial_later_batch(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        input_notes = user_content["input_notes"]
        returned_notes = input_notes if len(requests) == 1 else input_notes[:1]
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "topics": [
                            {
                                "input_index": item["input_index"],
                                "topic": grammar_topic(
                                    f"Topic {item['input_index']}"
                                ),
                            }
                            for item in returned_notes
                        ]
                    }
                )
            }
        }
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

    with pytest.raises(OllamaError, match="every input in the grammar batch"):
        client.generate_grammars(
            [f"Grammar note {index}" for index in range(4)]
        )

    assert len(requests) == 2
