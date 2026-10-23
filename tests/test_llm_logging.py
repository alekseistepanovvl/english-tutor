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


def exercise_response(
    primary_item_key: str,
    question: str,
) -> dict:
    return {
        "exercise_type": "fill_blank",
        "instruction": "Complete the sentence.",
        "question": question,
        "cue": None,
        "options": [],
        "expected_answers": ["commute"],
        "explanation": "Use the saved vocabulary.",
        "primary_item_key": primary_item_key,
        "supporting_item_keys": [],
    }


def test_generate_exercises_uses_one_request_for_distinct_output(
    monkeypatch,
) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        plans = user_content["exercise_plans"]
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "exercises": [
                            exercise_response(
                                plans[0]["primary_item_key"],
                                "She _____ to work by train every morning.",
                            ),
                            exercise_response(
                                plans[1]["primary_item_key"],
                                "The manager is _____ during difficult projects.",
                            ),
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
    material = [
        {
            "item_key": "vocabulary:1",
            "kind": "vocabulary",
            "expression": "commute",
            "attempt_count": 0,
        },
        {
            "item_key": "vocabulary:2",
            "kind": "vocabulary",
            "expression": "reliable",
            "attempt_count": 0,
        },
    ]

    result = client.generate_exercises(material, 2, variation_rotation=4)

    assert len(result.exercises) == 2
    assert len(requests) == 1
    payload = json.loads(requests[0].data)
    user_content = json.loads(payload["messages"][1]["content"])
    assert len(user_content["exercise_plans"]) == 2
    assert user_content["questions_to_avoid"] == []
    assert {
        "context",
        "setting",
        "subject",
        "sentence_shape",
    } <= set(user_content["exercise_plans"][0])


def test_generate_exercises_retries_only_repeated_question(
    monkeypatch,
) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        plans = user_content["exercise_plans"]
        if len(requests) == 1:
            questions = [
                "She _____ to work by train every morning.",
                "She _____ to work by train every morning.",
            ]
        else:
            questions = [
                "During the rail strike, they _____ from another town."
            ]
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "exercises": [
                            exercise_response(
                                plan["primary_item_key"],
                                question,
                            )
                            for plan, question in zip(
                                plans,
                                questions,
                                strict=True,
                            )
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
    material = [
        {
            "item_key": "vocabulary:1",
            "kind": "vocabulary",
            "expression": "commute",
            "attempt_count": 0,
        },
        {
            "item_key": "vocabulary:2",
            "kind": "vocabulary",
            "expression": "reliable",
            "attempt_count": 0,
        },
    ]

    result = client.generate_exercises(material, 2, variation_rotation=4)

    assert len(requests) == 2
    assert result.exercises[0].question == (
        "She _____ to work by train every morning."
    )
    assert result.exercises[1].question == (
        "During the rail strike, they _____ from another town."
    )
    retry_payload = json.loads(requests[1].data)
    retry_content = json.loads(
        retry_payload["messages"][1]["content"]
    )
    assert len(retry_content["exercise_plans"]) == 1
    assert retry_content["exercise_plans"][0]["plan_index"] == 1
    assert len(retry_content["questions_to_avoid"]) == 2


def test_generate_exercises_rejects_repeated_retry(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "exercises": [
                            exercise_response(
                                plan["primary_item_key"],
                                "She _____ to work by train every morning.",
                            )
                            for plan in user_content["exercise_plans"]
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
    material = [
        {
            "item_key": "vocabulary:1",
            "kind": "vocabulary",
            "expression": "commute",
            "attempt_count": 0,
        },
        {
            "item_key": "vocabulary:2",
            "kind": "vocabulary",
            "expression": "reliable",
            "attempt_count": 0,
        },
    ]

    with pytest.raises(OllamaError, match="repeated practice exercises"):
        client.generate_exercises(material, 2)


def test_generate_exercises_rejects_swapped_plan_items(
    monkeypatch,
) -> None:
    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        user_content = json.loads(payload["messages"][1]["content"])
        plans = user_content["exercise_plans"]
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "exercises": [
                            exercise_response(
                                plans[1]["primary_item_key"],
                                "She _____ to work every morning.",
                            ),
                            exercise_response(
                                plans[0]["primary_item_key"],
                                "The manager is always _____.",
                            ),
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
    material = [
        {
            "item_key": "vocabulary:1",
            "kind": "vocabulary",
            "expression": "commute",
            "attempt_count": 0,
        },
        {
            "item_key": "vocabulary:2",
            "kind": "vocabulary",
            "expression": "reliable",
            "attempt_count": 0,
        },
    ]

    with pytest.raises(OllamaError, match="planned learning item"):
        client.generate_exercises(material, 2)


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
