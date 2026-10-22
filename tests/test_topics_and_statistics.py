import json
import sqlite3
from pathlib import Path

from english_learning.database import SCHEMA, Database
from english_learning.domain import (
    ApprovedTopicAssignment,
    GrammarRule,
    GrammarTopic,
    ProposedTopicAssignment,
    TopicAssignment,
    VocabularyExample,
    VocabularyItem,
)


def vocabulary_item() -> VocabularyItem:
    return VocabularyItem(
        expression="a safe pair of hands",
        normalized_expression="a safe pair of hands",
        item_type="idiom",
        meaning="A reliable and trustworthy person.",
        pattern="be + a safe pair of hands",
        register="neutral",
        level="B2",
        examples=[
            VocabularyExample(
                sentence="Sarah is a safe pair of hands.",
                context="work",
            ),
            VocabularyExample(
                sentence="The goalkeeper is a safe pair of hands.",
                context="sport",
            ),
        ],
        topic_assignment=TopicAssignment(
            approved_topics=[
                ApprovedTopicAssignment(
                    slug="work-and-employment",
                    confidence=0.95,
                    rationale="The expression is commonly used at work.",
                )
            ],
            proposed_topics=[
                ProposedTopicAssignment(
                    name="Trust and reliability",
                    confidence=0.8,
                    rationale="The expression describes a reliable person.",
                )
            ],
        ),
    )


def test_topic_assignment_and_lesson_membership(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    lesson_id = database.create_lesson_topic("Job interview")

    database.save_vocabulary([vocabulary_item()], [lesson_id])

    vocabulary = database.list_vocabulary()
    memberships = database.get_lesson_topic_memberships(lesson_id)
    approved = database.list_llm_topics(status="approved")
    pending = database.list_llm_topics(status="pending")

    assert memberships["vocabulary_ids"] == [vocabulary[0]["id"]]
    assert any(
        topic["name"] == "Work and employment"
        and topic["vocabulary_count"] == 1
        for topic in approved
    )
    assert [topic["name"] for topic in pending] == ["Trust and reliability"]

    database.resolve_llm_topic(pending[0]["id"], "approve")
    assert database.list_llm_topics(status="pending") == []


def test_attempt_updates_vocabulary_statistics(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    database.save_vocabulary([vocabulary_item()])
    item_id = database.list_vocabulary()[0]["id"]

    database.save_attempt(
        item_type="vocabulary",
        item_key=None,
        item_keys=[f"vocabulary:{item_id}"],
        question="Complete the sentence.",
        learner_answer="a safe pair of hands",
        verdict="correct",
        score=1.0,
        feedback="Correct.",
    )

    candidates = database.get_practice_candidates(source="Vocabulary")
    candidate = candidates[0]
    assert candidate["attempt_count"] == 1
    assert candidate["mastery_score"] == 1.0
    assert candidate["next_review_at"] is not None

    database.save_attempt(
        item_type="vocabulary",
        item_key=None,
        item_keys=[f"vocabulary:{item_id}"],
        question="Complete another sentence.",
        learner_answer="wrong answer",
        verdict="incorrect",
        score=0.0,
        feedback="Try again.",
    )

    candidate = database.get_practice_candidates(source="Vocabulary")[0]
    assert candidate["attempt_count"] == 2
    assert candidate["mastery_score"] == 0.8
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM exercise_attempts"
        ).fetchone()[0] == 2


def test_learning_content_returns_topic_vocabulary_and_grammar(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    lesson_id = database.create_lesson_topic(
        "Job interview",
        "Vocabulary and grammar for interview preparation.",
    )
    database.save_vocabulary([vocabulary_item()], [lesson_id])
    database.save_grammar_topic(
        GrammarTopic(
            title="Verb patterns",
            summary="Verbs followed by infinitives.",
            level="B1",
            rules=[
                GrammarRule(
                    name="Verb + to-infinitive",
                    explanation="Some verbs take a to-infinitive.",
                    pattern="verb + to + base verb",
                    correct_examples=[
                        "She refused to answer.",
                        "We managed to finish.",
                    ],
                )
            ],
        ),
        [lesson_id],
    )

    content = database.get_learning_content(
        topic_source="lesson",
        topic_id=lesson_id,
    )

    assert content["topic"]["name"] == "Job interview"
    assert content["vocabulary"][0]["examples"]
    assert content["grammar_rules"][0]["correct_examples"]
    assert (
        content["grammar_rules"][0]["grammar_topic_title"] == "Verb patterns"
    )
    grammar_candidates = database.get_practice_candidates(source="Grammar")
    assert grammar_candidates[0]["correct_examples"] == [
        "She refused to answer.",
        "We managed to finish.",
    ]


def test_initialization_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")

    database.initialize()
    initial_topics = database.list_llm_topics(status="approved")
    database.initialize()

    assert database.list_llm_topics(status="approved") == initial_topics


def test_version_one_data_survives_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.execute(
        """
        INSERT INTO vocabulary_items (
            expression, normalized_expression, item_type, meaning, pattern,
            register, level, collocations_json, common_mistakes_json,
            tags_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "reliable",
            "reliable",
            "word",
            "Able to be trusted.",
            None,
            "neutral",
            "B1",
            json.dumps([]),
            json.dumps([]),
            json.dumps([]),
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()

    database = Database(path)
    database.initialize()

    assert database.list_vocabulary()[0]["expression"] == "reliable"
    assert database.list_lesson_topics() == []
    assert database.list_llm_topics(status="approved")
