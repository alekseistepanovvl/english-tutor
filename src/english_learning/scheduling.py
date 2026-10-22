from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Literal

from english_learning.domain import Exercise


MASTERY_OLD_WEIGHT = 0.8
MASTERY_ANSWER_WEIGHT = 0.2


def update_mastery(
    *,
    previous_mastery: float,
    attempt_count: int,
    answer_score: float,
) -> float:
    score = min(1.0, max(0.0, answer_score))
    if attempt_count == 0:
        return score
    return round(
        previous_mastery * MASTERY_OLD_WEIGHT
        + score * MASTERY_ANSWER_WEIGHT,
        4,
    )


def next_review_at(
    *,
    verdict: str,
    current_streak: int,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(UTC)
    if verdict == "incorrect":
        days = 1
    elif verdict == "partially_correct":
        days = 3
    elif current_streak <= 1:
        days = 7
    elif current_streak == 2:
        days = 14
    else:
        days = min(60, round(14 * (1.7 ** (current_streak - 2))))
    return current + timedelta(days=days)


def select_practice_items(
    candidates: list[dict],
    count: int,
    *,
    strategy: Literal["random", "least_mastered"],
    seed: int | None = None,
) -> list[dict]:
    if count <= 0 or not candidates:
        return []
    rng = random.Random(seed)
    shuffled = rng.sample(candidates, len(candidates))
    if strategy == "least_mastered":
        shuffled.sort(key=lambda item: float(item.get("mastery_score") or 0))
    return shuffled[:count]


def shuffle_exercises(
    exercises: list[Exercise],
    *,
    seed: int | None = None,
) -> list[Exercise]:
    shuffled = list(exercises)
    random.Random(seed).shuffle(shuffled)
    return shuffled
