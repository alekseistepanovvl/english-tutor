from pathlib import Path

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

