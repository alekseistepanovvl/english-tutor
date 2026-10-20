from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta


MASTERY_OLD_WEIGHT = 0.8
MASTERY_ANSWER_WEIGHT = 0.2
MAINTENANCE_FLOOR = 0.05


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


def priority_score(candidate: dict, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    mastery = float(candidate.get("mastery_score") or 0)
    attempts = int(candidate.get("attempt_count") or 0)
    weakness = 1 - mastery

    next_review_value = candidate.get("next_review_at")
    if not next_review_value:
        overdue = 1.0
    else:
        next_review = datetime.fromisoformat(next_review_value)
        seconds_until = (next_review - current).total_seconds()
        if seconds_until <= 0:
            overdue = 1.0
        else:
            overdue = max(0.0, 1 - seconds_until / (14 * 86400))

    last_practised_value = candidate.get("last_practised_at")
    if not last_practised_value:
        inactivity = 1.0
    else:
        last_practised = datetime.fromisoformat(last_practised_value)
        inactivity = min(
            1.0,
            max(0.0, (current - last_practised).total_seconds() / 86400 / 30),
        )

    uncertainty = 1 / math.sqrt(attempts + 1)
    return (
        0.45 * weakness
        + 0.30 * overdue
        + 0.15 * inactivity
        + 0.10 * uncertainty
        + MAINTENANCE_FLOOR
    )


def select_adaptive_items(
    candidates: list[dict],
    count: int,
    *,
    seed: int | None = None,
) -> list[dict]:
    if count <= 0 or not candidates:
        return []
    if len(candidates) <= count:
        return list(candidates)

    rng = random.Random(seed)
    scored = [
        {**candidate, "_priority": priority_score(candidate)}
        for candidate in candidates
    ]
    weak = [
        item
        for item in scored
        if item.get("attempt_count", 0) > 0
        and float(item.get("mastery_score") or 0) < 0.6
    ]
    new_or_medium = [
        item
        for item in scored
        if item.get("attempt_count", 0) == 0
        or 0.6 <= float(item.get("mastery_score") or 0) < 0.85
    ]
    strong = [
        item
        for item in scored
        if float(item.get("mastery_score") or 0) >= 0.85
    ]

    targets = [
        (weak, round(count * 0.6)),
        (new_or_medium, round(count * 0.2)),
        (strong, count - round(count * 0.6) - round(count * 0.2)),
    ]
    selected: list[dict] = []
    selected_keys: set[str] = set()

    def choose(pool: list[dict], wanted: int) -> None:
        available = [
            item for item in pool if item["item_key"] not in selected_keys
        ]
        for _ in range(min(wanted, len(available))):
            weights = [item["_priority"] for item in available]
            chosen = rng.choices(available, weights=weights, k=1)[0]
            selected.append(chosen)
            selected_keys.add(chosen["item_key"])
            available.remove(chosen)

    for pool, target in targets:
        choose(pool, target)

    if len(selected) < count:
        choose(scored, count - len(selected))

    for item in selected:
        item.pop("_priority", None)
    return selected

