from english_learning.domain import Exercise
from english_learning.scheduling import (
    select_practice_items,
    shuffle_exercises,
    update_mastery,
)


def test_random_practice_selection_returns_requested_subset() -> None:
    candidates = [
        {"item_key": f"vocabulary:{index}", "mastery_score": index / 10}
        for index in range(5)
    ]

    selected = select_practice_items(
        candidates,
        3,
        strategy="random",
        seed=1,
    )

    assert [item["item_key"] for item in selected] == [
        "vocabulary:1",
        "vocabulary:0",
        "vocabulary:4",
    ]
    assert len({item["item_key"] for item in selected}) == 3


def test_least_mastered_selection_chooses_lowest_mastery_first() -> None:
    candidates = [
        {"item_key": "grammar:strong", "mastery_score": 0.9},
        {"item_key": "grammar:weak", "mastery_score": 0.2},
        {"item_key": "grammar:new", "mastery_score": None},
        {"item_key": "grammar:medium", "mastery_score": 0.5},
    ]

    selected = select_practice_items(
        candidates,
        2,
        strategy="least_mastered",
        seed=1,
    )

    assert {item["item_key"] for item in selected} == {
        "grammar:new",
        "grammar:weak",
    }
    assert [item["item_key"] for item in candidates] == [
        "grammar:strong",
        "grammar:weak",
        "grammar:new",
        "grammar:medium",
    ]


def test_random_practice_selection_randomizes_order_when_all_fit() -> None:
    candidates = [
        {"item_key": f"vocabulary:{index}", "mastery_score": 0}
        for index in range(5)
    ]

    selected = select_practice_items(
        candidates,
        5,
        strategy="random",
        seed=1,
    )

    assert [item["item_key"] for item in selected] == [
        "vocabulary:1",
        "vocabulary:0",
        "vocabulary:4",
        "vocabulary:3",
        "vocabulary:2",
    ]
    assert [item["item_key"] for item in candidates] == [
        f"vocabulary:{index}" for index in range(5)
    ]


def test_first_attempt_sets_mastery_from_answer_score() -> None:
    assert update_mastery(
        previous_mastery=0,
        attempt_count=0,
        answer_score=0.75,
    ) == 0.75


def test_shuffle_exercises_reorders_without_losing_exercises() -> None:
    exercises = [
        Exercise(
            exercise_type="fill_blank",
            instruction="Complete the sentence.",
            question=f"Question {index} ___.",
            expected_answers=[str(index)],
            explanation="Test explanation.",
            primary_item_key=f"vocabulary:{index}",
        )
        for index in range(5)
    ]

    shuffled = shuffle_exercises(exercises, seed=1)

    assert shuffled != exercises
    assert [item.primary_item_key for item in shuffled] == [
        "vocabulary:2",
        "vocabulary:3",
        "vocabulary:4",
        "vocabulary:0",
        "vocabulary:1",
    ]
    assert [item.primary_item_key for item in exercises] == [
        f"vocabulary:{index}" for index in range(5)
    ]
