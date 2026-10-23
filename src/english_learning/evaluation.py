from __future__ import annotations

import unicodedata

from english_learning.domain import AnswerEvaluation, Exercise


TERMINAL_PUNCTUATION = ".,!?;:"
APOSTROPHE_TRANSLATION = str.maketrans({"‘": "'", "’": "'"})


def normalize_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(APOSTROPHE_TRANSLATION).casefold()
    normalized = " ".join(normalized.split())
    return normalized.rstrip(TERMINAL_PUNCTUATION).rstrip()


def evaluate_answer_deterministically(
    exercise: Exercise,
    learner_answer: str,
) -> AnswerEvaluation | None:
    normalized_answer = normalize_answer(learner_answer)
    if not normalized_answer:
        return AnswerEvaluation(
            verdict="incorrect",
            score=0,
            corrected_answer=exercise.expected_answers[0],
            explanation="No answer was provided.",
            error_categories=["missing-answer"],
            review_again=True,
        )

    correct = any(
        normalized_answer == normalize_answer(expected)
        for expected in exercise.expected_answers
    )
    if correct:
        return AnswerEvaluation(
            verdict="correct",
            score=1,
            explanation="Correct.",
            review_again=False,
        )

    if exercise.options:
        return AnswerEvaluation(
            verdict="incorrect",
            score=0,
            corrected_answer=exercise.expected_answers[0],
            explanation="That option does not match the expected answer.",
            error_categories=["incorrect-choice"],
            review_again=True,
        )

    return None


def partition_answer_evaluations(
    answers: list[tuple[int, Exercise, str]],
) -> tuple[
    dict[int, AnswerEvaluation],
    list[tuple[int, Exercise, str]],
]:
    evaluations: dict[int, AnswerEvaluation] = {}
    unresolved = []
    for index, exercise, learner_answer in answers:
        evaluation = evaluate_answer_deterministically(
            exercise,
            learner_answer,
        )
        if evaluation is None:
            unresolved.append((index, exercise, learner_answer))
        else:
            evaluations[index] = evaluation
    return evaluations, unresolved
