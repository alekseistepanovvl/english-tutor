from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VocabularyExample(StrictModel):
    sentence: str = Field(min_length=1)
    context: str | None = None


class ApprovedTopicAssignment(StrictModel):
    slug: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)


class ProposedTopicAssignment(StrictModel):
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)


class TopicAssignment(StrictModel):
    approved_topics: list[ApprovedTopicAssignment] = Field(default_factory=list)
    proposed_topics: list[ProposedTopicAssignment] = Field(default_factory=list)


class VocabularyItem(StrictModel):
    expression: str = Field(min_length=1)
    normalized_expression: str = Field(min_length=1)
    item_type: Literal[
        "word",
        "phrase",
        "idiom",
        "phrasal_verb",
        "collocation",
    ]
    meaning: str = Field(min_length=1)
    pattern: str | None = None
    usage_register: Literal[
        "formal",
        "neutral",
        "informal",
        "slang",
    ] = Field(default="neutral", alias="register")
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None = None
    examples: list[VocabularyExample] = Field(min_length=2)
    collocations: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    topic_assignment: TopicAssignment = Field(default_factory=TopicAssignment)


class VocabularyImport(StrictModel):
    items: list[VocabularyItem] = Field(min_length=1)


class IncorrectExample(StrictModel):
    incorrect: str = Field(min_length=1)
    correct: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class GrammarRule(StrictModel):
    name: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    verbs: list[str] = Field(default_factory=list)
    correct_examples: list[str] = Field(min_length=2)
    incorrect_examples: list[IncorrectExample] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    topic_assignment: TopicAssignment = Field(default_factory=TopicAssignment)


class GrammarTopic(StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    level: str | None = None
    rules: list[GrammarRule] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class Exercise(StrictModel):
    exercise_type: Literal[
        "multiple_choice",
        "fill_blank",
        "sentence_transformation",
        "error_correction",
        "free_production",
    ]
    instruction: str = Field(min_length=1)
    question: str = Field(min_length=1)
    cue: str | None = None
    options: list[str] = Field(default_factory=list)
    expected_answers: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    primary_item_key: str = Field(min_length=1)
    supporting_item_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_blank_exercise(self) -> "Exercise":
        if self.exercise_type == "fill_blank" and "___" not in self.question:
            raise ValueError("Fill-blank questions must contain a blank.")
        return self


class ExerciseSet(StrictModel):
    exercises: list[Exercise] = Field(min_length=1)


class AnswerEvaluation(StrictModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    score: float = Field(ge=0, le=1)
    corrected_answer: str | None = None
    explanation: str = Field(min_length=1)
    error_categories: list[str] = Field(default_factory=list)
    review_again: bool
