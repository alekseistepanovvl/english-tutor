import pytest
from pydantic import ValidationError

from english_learning.domain import Exercise


def test_fill_blank_exercise_requires_visible_blank() -> None:
    with pytest.raises(ValidationError):
        Exercise(
            exercise_type="fill_blank",
            instruction="Complete the sentence.",
            question="She refused to answer.",
            expected_answers=["to answer"],
            explanation="Refuse is followed by a to-infinitive.",
            primary_item_key="grammar_rule:1",
        )


def test_guided_fill_blank_exercise_accepts_optional_cue() -> None:
    exercise = Exercise(
        exercise_type="fill_blank",
        instruction="Use the correct form of the words in brackets.",
        question="She _____ my question.",
        cue="(refuse / answer)",
        expected_answers=["refused to answer"],
        explanation="Refuse is followed by a to-infinitive.",
        primary_item_key="grammar_rule:1",
    )

    assert exercise.cue == "(refuse / answer)"
    assert "___" in exercise.question

