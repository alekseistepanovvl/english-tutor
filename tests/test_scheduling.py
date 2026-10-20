from datetime import UTC, datetime, timedelta

from english_learning.scheduling import (
    priority_score,
    select_adaptive_items,
    update_mastery,
)


def test_weak_item_has_higher_priority_than_strong_item() -> None:
    now = datetime.now(UTC)
    weak = {
        "attempt_count": 4,
        "mastery_score": 0.2,
        "last_practised_at": (now - timedelta(days=10)).isoformat(),
        "next_review_at": (now - timedelta(days=1)).isoformat(),
    }
    strong = {
        "attempt_count": 10,
        "mastery_score": 0.95,
        "last_practised_at": now.isoformat(),
        "next_review_at": (now + timedelta(days=20)).isoformat(),
    }

    assert priority_score(weak, now) > priority_score(strong, now)
    assert priority_score(strong, now) > 0


def test_adaptive_selection_includes_strong_maintenance_item() -> None:
    candidates = [
        {
            "item_key": "vocabulary:1",
            "attempt_count": 4,
            "mastery_score": 0.2,
        },
        {
            "item_key": "vocabulary:2",
            "attempt_count": 0,
            "mastery_score": 0,
        },
        {
            "item_key": "vocabulary:3",
            "attempt_count": 8,
            "mastery_score": 0.95,
        },
    ]

    selected = select_adaptive_items(candidates, 3, seed=1)

    assert {item["item_key"] for item in selected} == {
        "vocabulary:1",
        "vocabulary:2",
        "vocabulary:3",
    }


def test_first_attempt_sets_mastery_from_answer_score() -> None:
    assert update_mastery(
        previous_mastery=0,
        attempt_count=0,
        answer_score=0.75,
    ) == 0.75

