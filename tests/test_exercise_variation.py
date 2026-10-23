from english_learning.domain import Exercise
from english_learning.exercise_variation import (
    advance_exercise_plan,
    build_exercise_plans,
    find_repeated_exercise_indexes,
)


def exercise(question: str, item_key: str = "vocabulary:1") -> Exercise:
    return Exercise(
        exercise_type="fill_blank",
        instruction="Complete the sentence.",
        question=question,
        expected_answers=["commute"],
        explanation="Use the saved vocabulary.",
        primary_item_key=item_key,
    )


def test_build_exercise_plans_rotates_items_and_variations() -> None:
    material = [
        {"item_key": "vocabulary:10", "attempt_count": 2},
        {"item_key": "vocabulary:20", "attempt_count": 0},
    ]

    plans = build_exercise_plans(material, 5, rotation=3)

    assert [plan["primary_item_key"] for plan in plans] == [
        "vocabulary:10",
        "vocabulary:20",
        "vocabulary:10",
        "vocabulary:20",
        "vocabulary:10",
    ]
    assert [plan["variation_index"] for plan in plans] == [
        15,
        23,
        16,
        24,
        17,
    ]
    assert advance_exercise_plan(plans[0])["variation_index"] == 16


def test_find_repeated_exercises_detects_exact_and_close_questions() -> None:
    exercises = [
        exercise("She _____ to work by train every morning."),
        exercise("She _____ to work by train every morning!"),
        exercise("She _____ to work by train every mornings."),
        exercise("During the strike, they _____ from another town."),
    ]

    assert find_repeated_exercise_indexes(exercises) == {1, 2}
