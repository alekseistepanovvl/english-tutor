from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


VOCABULARY_TOPICS = [
    "Daily life",
    "Work and employment",
    "Education",
    "Travel and transport",
    "Relationships and people",
    "Communication",
    "Emotions and personality",
    "Health",
    "Money and business",
    "Technology",
    "Food and shopping",
    "Time and planning",
    "Formal language",
    "Informal language",
    "Idioms and figurative language",
    "Phrasal verbs",
]

GRAMMAR_TOPICS = [
    "Verb patterns",
    "Infinitives",
    "Gerunds",
    "Tenses and aspect",
    "Modal verbs",
    "Conditionals",
    "Passive voice",
    "Reported speech",
    "Articles and determiners",
    "Prepositions",
    "Relative clauses",
    "Questions",
    "Negation",
    "Word order",
    "Comparatives",
    "Pronouns",
    "Countability and quantity",
    "Linking and discourse",
]


def slugify(value: str) -> str:
    characters = [
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    ]
    return "-".join(filter(None, "".join(characters).split("-")))


MIGRATION_2 = """
CREATE TABLE lesson_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE lesson_topic_vocabulary (
    lesson_topic_id INTEGER NOT NULL
        REFERENCES lesson_topics(id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL
        REFERENCES vocabulary_items(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (lesson_topic_id, vocabulary_id)
);

CREATE TABLE lesson_topic_grammar_rules (
    lesson_topic_id INTEGER NOT NULL
        REFERENCES lesson_topics(id) ON DELETE CASCADE,
    grammar_rule_id INTEGER NOT NULL
        REFERENCES grammar_rules(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (lesson_topic_id, grammar_rule_id)
);

CREATE TABLE llm_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    slug TEXT NOT NULL UNIQUE,
    topic_kind TEXT NOT NULL
        CHECK (topic_kind IN ('vocabulary', 'grammar', 'both')),
    status TEXT NOT NULL
        CHECK (status IN ('approved', 'pending', 'rejected', 'merged')),
    merged_into_id INTEGER REFERENCES llm_topics(id),
    created_by TEXT NOT NULL
        CHECK (created_by IN ('seed', 'llm', 'learner')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE llm_topic_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    llm_topic_id INTEGER NOT NULL
        REFERENCES llm_topics(id) ON DELETE CASCADE,
    alias TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE llm_topic_vocabulary (
    llm_topic_id INTEGER NOT NULL
        REFERENCES llm_topics(id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL
        REFERENCES vocabulary_items(id) ON DELETE CASCADE,
    confidence REAL,
    rationale TEXT,
    assigned_by TEXT NOT NULL
        CHECK (assigned_by IN ('llm', 'learner')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (llm_topic_id, vocabulary_id)
);

CREATE TABLE llm_topic_grammar_rules (
    llm_topic_id INTEGER NOT NULL
        REFERENCES llm_topics(id) ON DELETE CASCADE,
    grammar_rule_id INTEGER NOT NULL
        REFERENCES grammar_rules(id) ON DELETE CASCADE,
    confidence REAL,
    rationale TEXT,
    assigned_by TEXT NOT NULL
        CHECK (assigned_by IN ('llm', 'learner')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (llm_topic_id, grammar_rule_id)
);

CREATE TABLE practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    practice_mode TEXT NOT NULL,
    selection_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

ALTER TABLE exercise_attempts
    ADD COLUMN practice_session_id INTEGER
        REFERENCES practice_sessions(id);

CREATE TABLE attempt_vocabulary (
    attempt_id INTEGER NOT NULL
        REFERENCES exercise_attempts(id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL
        REFERENCES vocabulary_items(id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (attempt_id, vocabulary_id)
);

CREATE TABLE attempt_grammar_rules (
    attempt_id INTEGER NOT NULL
        REFERENCES exercise_attempts(id) ON DELETE CASCADE,
    grammar_rule_id INTEGER NOT NULL
        REFERENCES grammar_rules(id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (attempt_id, grammar_rule_id)
);

CREATE TABLE vocabulary_statistics (
    vocabulary_id INTEGER PRIMARY KEY
        REFERENCES vocabulary_items(id) ON DELETE CASCADE,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    partial_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    total_score REAL NOT NULL DEFAULT 0,
    mastery_score REAL NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_practised_at TEXT,
    next_review_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE grammar_rule_statistics (
    grammar_rule_id INTEGER PRIMARY KEY
        REFERENCES grammar_rules(id) ON DELETE CASCADE,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    partial_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    total_score REAL NOT NULL DEFAULT 0,
    mastery_score REAL NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_practised_at TEXT,
    next_review_at TEXT,
    updated_at TEXT NOT NULL
);
"""


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    versions = {
        row[0]
        for row in connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
    }
    now = datetime.now(UTC).isoformat()
    if not versions:
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
            (now,),
        )
        versions.add(1)
    if 2 not in versions:
        for statement in MIGRATION_2.split(";"):
            if statement.strip():
                connection.execute(statement)
        _seed_topics(connection, now)
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (2, ?)",
            (now,),
        )


def _seed_topics(connection: sqlite3.Connection, now: str) -> None:
    rows = [
        (name, slugify(name), "vocabulary", "approved", "seed", now, now)
        for name in VOCABULARY_TOPICS
    ]
    rows.extend(
        (name, slugify(name), "grammar", "approved", "seed", now, now)
        for name in GRAMMAR_TOPICS
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO llm_topics (
            name, slug, topic_kind, status, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
