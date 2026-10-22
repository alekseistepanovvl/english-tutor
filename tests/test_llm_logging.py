import json
import logging
from io import BytesIO
from pathlib import Path

from english_learning.config import Settings
from english_learning.domain import AnswerEvaluation
from english_learning.llm import OllamaClient


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
