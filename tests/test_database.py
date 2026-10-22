import sqlite3
from pathlib import Path

import pytest

from english_learning.database import Database
from english_learning.domain import (
    GrammarRule,
    GrammarTopic,
    VocabularyExample,
    VocabularyItem,
)


def test_save_and_list_vocabulary(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    item = VocabularyItem(
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
        tags=["reliability"],
    )

    assert database.save_vocabulary([item]) == 1
    saved = database.list_vocabulary()

    assert len(saved) == 1
    assert saved[0]["expression"] == "a safe pair of hands"
    assert len(saved[0]["examples"]) == 2


def test_save_and_list_grammar(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    topic = GrammarTopic(
        title="Verb + to-infinitive",
        summary="Verbs followed by a to-infinitive.",
        level="B1",
        rules=[
            GrammarRule(
                name="Verb + to-infinitive",
                explanation="Some verbs take a to-infinitive.",
                pattern="verb + to + base verb",
                correct_examples=[
                    "She refused to help.",
                    "We managed to finish.",
                ],
            )
        ],
    )

    topic_id = database.save_grammar_topic(topic)
    saved = database.list_grammar_topics()

    assert topic_id > 0
    assert len(saved) == 1
    assert saved[0]["rules"][0]["pattern"] == "verb + to + base verb"


def test_save_multiple_grammar_topics(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    topics = [
        GrammarTopic(
            title=f"Grammar topic {index}",
            summary="A grammar summary.",
            rules=[
                GrammarRule(
                    name=f"Rule {index}",
                    explanation="A grammar explanation.",
                    pattern="subject + verb",
                    correct_examples=[
                        "She works.",
                        "They work.",
                    ],
                )
            ],
        )
        for index in range(2)
    ]

    topic_ids = database.save_grammar_topics(topics)

    assert len(topic_ids) == 2
    assert {topic["title"] for topic in database.list_grammar_topics()} == {
        "Grammar topic 1",
        "Grammar topic 0",
    }


def test_save_multiple_grammar_topics_is_atomic(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    topic = GrammarTopic(
        title="Verb forms",
        summary="A grammar summary.",
        rules=[
            GrammarRule(
                name="Present simple",
                explanation="Use for regular actions.",
                pattern="subject + base verb",
                correct_examples=["I work.", "They work."],
            )
        ],
    )

    with pytest.raises(sqlite3.IntegrityError):
        database.save_grammar_topics([topic, topic], [999])

    assert database.list_grammar_topics() == []
