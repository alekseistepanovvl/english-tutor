from __future__ import annotations

import json
import logging
from pathlib import Path
from time import perf_counter
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

from english_learning.config import Settings
from english_learning.domain import (
    AnswerEvaluation,
    AnswerEvaluationSet,
    Exercise,
    ExerciseSet,
    GrammarImport,
    GrammarTopic,
    InputValidation,
    InputValidationSet,
    VocabularyImport,
)


PROMPT_DIR = Path(__file__).with_name("prompts")
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
logger = logging.getLogger(__name__)

VALIDATION_OUTPUT_TOKENS = 768
VOCABULARY_OUTPUT_TOKENS_PER_ITEM = 1024
GRAMMAR_OUTPUT_TOKENS_PER_ITEM = 2048
EXERCISE_OUTPUT_TOKENS_PER_ITEM = 320
ANSWER_OUTPUT_TOKENS_PER_ITEM = 192
MAX_STRUCTURED_OUTPUT_TOKENS = 4096


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
        item_count = max(
            1,
            len([line for line in raw_input.splitlines() if line.strip()]),
        )
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
            max_output_tokens=min(
                MAX_STRUCTURED_OUTPUT_TOKENS,
                item_count * VOCABULARY_OUTPUT_TOKENS_PER_ITEM,
            ),
        )

    def generate_grammar(
        self,
        raw_input: str,
        approved_topics: list[dict] | None = None,
    ) -> GrammarTopic:
        return self.generate_grammars([raw_input], approved_topics)[0]

    def generate_grammars(
        self,
        raw_inputs: list[str],
        approved_topics: list[dict] | None = None,
    ) -> list[GrammarTopic]:
        if not raw_inputs:
            raise ValueError("At least one grammar note is required.")

        result = self._structured_chat(
            prompt_name="grammar_extract_many.md",
            user_content=json.dumps(
                {
                    "input_notes": [
                        {
                            "input_index": index,
                            "learner_input": raw_input,
                        }
                        for index, raw_input in enumerate(raw_inputs)
                    ],
                    "approved_topics": approved_topics or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            response_model=GrammarImport,
            temperature=0,
            max_output_tokens=min(
                MAX_STRUCTURED_OUTPUT_TOKENS,
                len(raw_inputs) * GRAMMAR_OUTPUT_TOKENS_PER_ITEM,
            ),
        )
        topics_by_index: dict[int, GrammarTopic] = {}
        for indexed_topic in result.topics:
            if indexed_topic.input_index in topics_by_index:
                raise OllamaError(
                    "The model returned duplicate grammar input indexes."
                )
            topics_by_index[indexed_topic.input_index] = indexed_topic.topic

        expected_indexes = set(range(len(raw_inputs)))
        if set(topics_by_index) != expected_indexes:
            raise OllamaError(
                "The model did not return exactly one grammar topic for "
                "every submitted input."
            )
        return [topics_by_index[index] for index in range(len(raw_inputs))]

    def validate_vocabulary_inputs(
        self,
        inputs: list[tuple[int, str]],
    ) -> dict[int, InputValidation]:
        return self._validate_inputs(
            prompt_name="vocabulary_validate.md",
            inputs=inputs,
        )

    def validate_grammar_inputs(
        self,
        inputs: list[tuple[int, str]],
    ) -> dict[int, InputValidation]:
        return self._validate_inputs(
            prompt_name="grammar_validate.md",
            inputs=inputs,
        )

    def _validate_inputs(
        self,
        *,
        prompt_name: str,
        inputs: list[tuple[int, str]],
    ) -> dict[int, InputValidation]:
        if not inputs:
            return {}
        result = self._structured_chat(
            prompt_name=prompt_name,
            user_content=json.dumps(
                {
                    "inputs": [
                        {"input_index": index, "input": value}
                        for index, value in inputs
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            response_model=InputValidationSet,
            temperature=0,
            max_output_tokens=min(
                MAX_STRUCTURED_OUTPUT_TOKENS,
                max(VALIDATION_OUTPUT_TOKENS, len(inputs) * 192),
            ),
        )
        expected_indexes = {index for index, _ in inputs}
        validations = {
            validation.input_index: validation
            for validation in result.validations
        }
        if (
            len(validations) != len(result.validations)
            or set(validations) != expected_indexes
        ):
            raise OllamaError(
                "The model did not return exactly one validation for each "
                "submitted input."
            )
        return validations

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
            max_output_tokens=min(
                MAX_STRUCTURED_OUTPUT_TOKENS,
                max(768, count * EXERCISE_OUTPUT_TOKENS_PER_ITEM),
            ),
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
        return self.evaluate_answers(
            [(0, exercise, learner_answer)]
        )[0]

    def evaluate_answers(
        self,
        answers: list[tuple[int, Exercise, str]],
    ) -> dict[int, AnswerEvaluation]:
        if not answers:
            return {}
        content = json.dumps(
            {
                "answers": [
                    {
                        "exercise_index": index,
                        "exercise": exercise.model_dump(),
                        "learner_answer": learner_answer,
                    }
                    for index, exercise, learner_answer in answers
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        result = self._structured_chat(
            prompt_name="answers_evaluate.md",
            user_content=content,
            response_model=AnswerEvaluationSet,
            temperature=0,
            max_output_tokens=min(
                MAX_STRUCTURED_OUTPUT_TOKENS,
                max(512, len(answers) * ANSWER_OUTPUT_TOKENS_PER_ITEM),
            ),
        )
        expected_indexes = {index for index, _, _ in answers}
        evaluations = {
            item.exercise_index: item.evaluation
            for item in result.evaluations
        }
        if (
            len(evaluations) != len(result.evaluations)
            or set(evaluations) != expected_indexes
        ):
            raise OllamaError(
                "The model did not return exactly one evaluation for each "
                "submitted answer."
            )
        return evaluations

    def _structured_chat(
        self,
        *,
        prompt_name: str,
        user_content: str,
        response_model: type[ResponseModel],
        temperature: float,
        max_output_tokens: int,
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
            "think": False,
            "keep_alive": self.settings.ollama_keep_alive,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "format": response_model.model_json_schema(),
            "options": {
                "temperature": temperature,
                "num_predict": max_output_tokens,
            },
        }
        request = Request(
            f"{self.settings.ollama_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started_at = perf_counter()
        logger.info(
            "Ollama request started task=%s model=%s max_output_tokens=%d",
            prompt_name,
            self.settings.model,
            max_output_tokens,
        )
        try:
            with urlopen(request, timeout=180) as response:
                body = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            logger.warning(
                "Ollama request failed task=%s status=%d elapsed=%.2fs",
                prompt_name,
                error.code,
                perf_counter() - started_at,
            )
            raise OllamaError(
                f"Ollama returned HTTP {error.code}: {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            logger.warning(
                "Ollama request failed task=%s reason=%s elapsed=%.2fs",
                prompt_name,
                type(error).__name__,
                perf_counter() - started_at,
            )
            raise OllamaError(
                "Could not contact Ollama. Confirm that it is installed, "
                "running, and configured correctly."
            ) from error

        self._log_response_metrics(prompt_name, body)
        try:
            content = body["message"]["content"]
            result = response_model.model_validate_json(content)
        except (KeyError, TypeError, ValueError) as error:
            logger.warning(
                "Ollama returned invalid structured data task=%s "
                "reason=%s: %s elapsed=%.2fs",
                prompt_name,
                type(error).__name__,
                error,
                perf_counter() - started_at,
            )
            raise OllamaError(
                "The model returned an invalid structured response. "
                "Try again or choose a model with stronger instruction "
                "following."
            ) from error
        logger.info(
            "Ollama request completed task=%s elapsed=%.2fs",
            prompt_name,
            perf_counter() - started_at,
        )
        return result

    @staticmethod
    def _log_response_metrics(
        prompt_name: str,
        body: dict[str, Any],
    ) -> None:
        load_seconds = OllamaClient._duration_seconds(
            body.get("load_duration")
        )
        prompt_seconds = OllamaClient._duration_seconds(
            body.get("prompt_eval_duration")
        )
        generation_seconds = OllamaClient._duration_seconds(
            body.get("eval_duration")
        )
        prompt_tokens = OllamaClient._token_count(
            body.get("prompt_eval_count")
        )
        generated_tokens = OllamaClient._token_count(body.get("eval_count"))
        tokens_per_second = (
            generated_tokens / generation_seconds
            if generation_seconds > 0
            else 0
        )
        logger.info(
            "Ollama metrics task=%s load=%.2fs prompt_tokens=%d "
            "prompt_eval=%.2fs generated_tokens=%d generation=%.2fs "
            "tokens_per_second=%.2f",
            prompt_name,
            load_seconds,
            prompt_tokens,
            prompt_seconds,
            generated_tokens,
            generation_seconds,
            tokens_per_second,
        )

    @staticmethod
    def _duration_seconds(value: Any) -> float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value / 1_000_000_000
        return 0

    @staticmethod
    def _token_count(value: Any) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return 0
