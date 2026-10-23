from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

from english_learning.domain import Exercise


CONTEXTS = (
    "work",
    "travel",
    "education",
    "family life",
    "technology",
    "shopping",
    "health",
    "current events",
)
SETTINGS = (
    "an office",
    "a railway station",
    "a classroom",
    "a home",
    "a shop",
    "a public meeting",
    "an online conversation",
)
SUBJECTS = (
    "one person",
    "two colleagues",
    "a family",
    "a group of students",
    "a customer",
    "a local resident",
)
SENTENCE_SHAPES = (
    "routine",
    "cause and consequence",
    "contrast",
    "personal preference",
    "problem and response",
)
QUESTION_SIMILARITY_THRESHOLD = 0.92


def build_exercise_plans(
    learning_material: list[dict],
    count: int,
    *,
    rotation: int = 0,
) -> list[dict]:
    if not learning_material or count <= 0:
        return []

    occurrences: dict[str, int] = {}
    plans = []
    for plan_index in range(count):
        item = learning_material[plan_index % len(learning_material)]
        item_key = item["item_key"]
        occurrence = occurrences.get(item_key, 0)
        occurrences[item_key] = occurrence + 1
        variation_index = (
            _item_id(item_key)
            + int(item.get("attempt_count") or 0)
            + rotation
            + occurrence
        )
        plans.append(
            _exercise_plan(
                plan_index=plan_index,
                item_key=item_key,
                variation_index=variation_index,
            )
        )
    return plans


def advance_exercise_plan(plan: dict) -> dict:
    return _exercise_plan(
        plan_index=plan["plan_index"],
        item_key=plan["primary_item_key"],
        variation_index=plan["variation_index"] + 1,
    )


def find_repeated_exercise_indexes(
    exercises: list[Exercise],
    *,
    reference_questions: list[str] | None = None,
) -> set[int]:
    accepted = [
        normalize_question(question)
        for question in reference_questions or []
    ]
    repeated: set[int] = set()
    for index, exercise in enumerate(exercises):
        normalized = normalize_question(exercise.question)
        if any(
            _questions_are_too_similar(normalized, previous)
            for previous in accepted
        ):
            repeated.add(index)
        else:
            accepted.append(normalized)
    return repeated


def normalize_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split()).rstrip(".,!?;:").rstrip()


def _exercise_plan(
    *,
    plan_index: int,
    item_key: str,
    variation_index: int,
) -> dict:
    return {
        "plan_index": plan_index,
        "primary_item_key": item_key,
        "variation_index": variation_index,
        "context": CONTEXTS[variation_index % len(CONTEXTS)],
        "setting": SETTINGS[(variation_index * 3 + 1) % len(SETTINGS)],
        "subject": SUBJECTS[(variation_index * 5 + 2) % len(SUBJECTS)],
        "sentence_shape": SENTENCE_SHAPES[
            (variation_index * 2 + 3) % len(SENTENCE_SHAPES)
        ],
    }


def _item_id(item_key: str) -> int:
    _, raw_id = item_key.split(":", 1)
    return int(raw_id)


def _questions_are_too_similar(first: str, second: str) -> bool:
    return first == second or (
        SequenceMatcher(None, first, second).ratio()
        >= QUESTION_SIMILARITY_THRESHOLD
    )
