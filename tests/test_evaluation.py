from english_learning.domain import Exercise
from english_learning.evaluation import (
    evaluate_answer_deterministically,
    normalize_answer,
    partition_answer_evaluations,
)


def exercise(
    *,
    expected_answers: list[str] | None = None,
    options: list[str] | None = None,
) -> Exercise:
    return Exercise(
        exercise_type="fill_blank",
        instruction="Complete the sentence.",
        question="She ___.",
        options=options or [],
        expected_answers=expected_answers or ["has been working"],
        explanation="Use the expected form.",
        primary_item_key="grammar_rule:1",
    )


def test_normalize_answer_ignores_safe_surface_differences() -> None:
    assert normalize_answer("  HAS   been working. ") == "has been working"
    assert normalize_answer("don’t") == "don't"


def test_exact_alternative_is_evaluated_as_correct() -> None:
    evaluation = evaluate_answer_deterministically(
        exercise(expected_answers=["has been working", "has worked"]),
        " Has worked! ",
    )

    assert evaluation is not None
    assert evaluation.verdict == "correct"
    assert evaluation.score == 1
    assert evaluation.review_again is False


def test_nonmatching_free_text_requires_model_evaluation() -> None:
    evaluation = evaluate_answer_deterministically(
        exercise(),
        "worked",
    )

    assert evaluation is None


def test_incorrect_choice_is_evaluated_without_model() -> None:
    evaluation = evaluate_answer_deterministically(
        exercise(
            expected_answers=["has been working"],
            options=["has been working", "worked"],
        ),
        "worked",
    )

    assert evaluation is not None
    assert evaluation.verdict == "incorrect"
    assert evaluation.corrected_answer == "has been working"
    assert evaluation.error_categories == ["incorrect-choice"]


def test_empty_answer_is_evaluated_without_model() -> None:
    evaluation = evaluate_answer_deterministically(exercise(), "  ")

    assert evaluation is not None
    assert evaluation.verdict == "incorrect"
    assert evaluation.error_categories == ["missing-answer"]


def test_partition_sends_only_ambiguous_answers_to_model() -> None:
    exact = exercise(expected_answers=["commutes"])
    ambiguous = exercise(expected_answers=["has been working"])
    choice = exercise(
        expected_answers=["left"],
        options=["left", "leaved"],
    )

    evaluations, unresolved = partition_answer_evaluations(
        [
            (2, exact, "Commutes."),
            (5, ambiguous, "worked"),
            (8, choice, "leaved"),
        ]
    )

    assert set(evaluations) == {2, 8}
    assert evaluations[2].verdict == "correct"
    assert evaluations[8].verdict == "incorrect"
    assert unresolved == [(5, ambiguous, "worked")]
