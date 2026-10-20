from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

from english_learning.config import Settings
from english_learning.domain import (
    AnswerEvaluation,
    Exercise,
    ExerciseSet,
    GrammarTopic,
    VocabularyImport,
)


PROMPT_DIR = Path(__file__).with_name("prompts")
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_available(self) -> bool:
        try:
            request = Request(f"{self.settings.ollama_url}/api/tags")
            with urlopen(request, timeout=2):
                return True
        except (HTTPError, URLError, TimeoutError):
            return False

    def generate_vocabulary(
        self,
        raw_input: str,
        approved_topics: list[dict] | None = None,
    ) -> VocabularyImport:
        return self._structured_chat(
            prompt_name="vocabulary_extract.md",
            user_content=json.dumps(
                {
                    "learner_input": raw_input,
                    "approved_topics": approved_topics or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            response_model=VocabularyImport,
            temperature=0,
        )

    def generate_grammar(
        self,
        raw_input: str,
        approved_topics: list[dict] | None = None,
    ) -> GrammarTopic:
        return self._structured_chat(
            prompt_name="grammar_extract.md",
            user_content=json.dumps(
                {
                    "learner_input": raw_input,
                    "approved_topics": approved_topics or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            response_model=GrammarTopic,
            temperature=0,
        )

    def generate_exercises(
        self,
        learning_material: list[dict],
        count: int,
    ) -> ExerciseSet:
        content = json.dumps(
            {
                "exercise_count": count,
                "learner_level": self.settings.learner_level,
                "learning_material": learning_material,
            },
            ensure_ascii=False,
            indent=2,
        )
        exercises = self._structured_chat(
            prompt_name="exercise_generate.md",
            user_content=content,
            response_model=ExerciseSet,
            temperature=0.4,
        )
        allowed_keys = {
            item["item_key"]
            for item in learning_material
            if "item_key" in item
        }
        for exercise in exercises.exercises:
            returned_keys = {
                exercise.primary_item_key,
                *exercise.supporting_item_keys,
            }
            unknown = returned_keys - allowed_keys
            if unknown:
                raise OllamaError(
                    "The model referenced learning items that were not "
                    f"provided: {', '.join(sorted(unknown))}"
                )
            if exercise.exercise_type != "fill_blank":
                raise OllamaError(
                    "The model returned an unsupported practice format. "
                    "All guided exercises must be fill-blank exercises."
                )
        return exercises

    def evaluate_answer(
        self,
        exercise: Exercise,
        learner_answer: str,
    ) -> AnswerEvaluation:
        content = json.dumps(
            {
                "exercise": exercise.model_dump(),
                "learner_answer": learner_answer,
            },
            ensure_ascii=False,
            indent=2,
        )
        return self._structured_chat(
            prompt_name="answer_evaluate.md",
            user_content=content,
            response_model=AnswerEvaluation,
            temperature=0,
        )

    def _structured_chat(
        self,
        *,
        prompt_name: str,
        user_content: str,
        response_model: type[ResponseModel],
        temperature: float,
    ) -> ResponseModel:
        system_prompt = (PROMPT_DIR / prompt_name).read_text(
            encoding="utf-8"
        ).format(
            learner_level=self.settings.learner_level,
            english_variant=self.settings.english_variant,
        )
        payload = {
            "model": self.settings.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "format": response_model.model_json_schema(),
            "options": {"temperature": temperature},
        }
        request = Request(
            f"{self.settings.ollama_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=180) as response:
                body = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise OllamaError(
                f"Ollama returned HTTP {error.code}: {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise OllamaError(
                "Could not contact Ollama. Confirm that it is installed, "
                "running, and configured correctly."
            ) from error

        try:
            content = body["message"]["content"]
            return response_model.model_validate_json(content)
        except (KeyError, TypeError, ValueError) as error:
            raise OllamaError(
                "The model returned an invalid structured response. "
                "Try again or choose a model with stronger instruction "
                "following."
            ) from error
