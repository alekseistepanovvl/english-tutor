from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from english_learning.domain import (
    GrammarTopic,
    TopicAssignment,
    VocabularyItem,
)
from english_learning.migrations import migrate, slugify
from english_learning.scheduling import next_review_at, update_mastery


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vocabulary_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expression TEXT NOT NULL,
    normalized_expression TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    meaning TEXT NOT NULL,
    pattern TEXT,
    register TEXT NOT NULL,
    level TEXT,
    collocations_json TEXT NOT NULL,
    common_mistakes_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vocabulary_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary_items(id)
        ON DELETE CASCADE,
    sentence TEXT NOT NULL,
    context TEXT
);

CREATE TABLE IF NOT EXISTS grammar_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    level TEXT,
    tags_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grammar_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES grammar_topics(id)
        ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    explanation TEXT NOT NULL,
    pattern TEXT NOT NULL,
    verbs_json TEXT NOT NULL,
    correct_examples_json TEXT NOT NULL,
    incorrect_examples_json TEXT NOT NULL,
    exceptions_json TEXT NOT NULL,
    notes_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exercise_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    item_key TEXT,
    question TEXT NOT NULL,
    learner_answer TEXT NOT NULL,
    verdict TEXT NOT NULL,
    score REAL NOT NULL,
    feedback TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            migrate(connection)

    def save_vocabulary(
        self,
        items: list[VocabularyItem],
        lesson_topic_ids: list[int] | None = None,
    ) -> int:
        saved = 0
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            for item in items:
                cursor = connection.execute(
                    """
                    INSERT INTO vocabulary_items (
                        expression, normalized_expression, item_type, meaning,
                        pattern, register, level, collocations_json,
                        common_mistakes_json, tags_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(normalized_expression) DO UPDATE SET
                        expression = excluded.expression,
                        item_type = excluded.item_type,
                        meaning = excluded.meaning,
                        pattern = excluded.pattern,
                        register = excluded.register,
                        level = excluded.level,
                        collocations_json = excluded.collocations_json,
                        common_mistakes_json = excluded.common_mistakes_json,
                        tags_json = excluded.tags_json,
                        updated_at = excluded.updated_at
                    RETURNING id
                    """,
                    (
                        item.expression,
                        item.normalized_expression,
                        item.item_type,
                        item.meaning,
                        item.pattern,
                        item.usage_register,
                        item.level,
                        json.dumps(item.collocations, ensure_ascii=False),
                        json.dumps(item.common_mistakes, ensure_ascii=False),
                        json.dumps(item.tags, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                vocabulary_id = cursor.fetchone()["id"]
                connection.execute(
                    "DELETE FROM vocabulary_examples WHERE vocabulary_id = ?",
                    (vocabulary_id,),
                )
                connection.executemany(
                    """
                    INSERT INTO vocabulary_examples (
                        vocabulary_id, sentence, context
                    ) VALUES (?, ?, ?)
                    """,
                    [
                        (vocabulary_id, example.sentence, example.context)
                        for example in item.examples
                    ],
                )
                if lesson_topic_ids is not None:
                    self._replace_lesson_vocabulary_memberships(
                        connection,
                        vocabulary_id,
                        lesson_topic_ids,
                        now,
                    )
                self._save_topic_assignment(
                    connection,
                    item.topic_assignment,
                    item_kind="vocabulary",
                    item_id=vocabulary_id,
                    now=now,
                )
                saved += 1
        return saved

    def save_grammar_topic(
        self,
        topic: GrammarTopic,
        lesson_topic_ids: list[int] | None = None,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO grammar_topics (
                    title, summary, level, tags_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    topic.title,
                    topic.summary,
                    topic.level,
                    json.dumps(topic.tags, ensure_ascii=False),
                    now,
                ),
            )
            topic_id = cursor.lastrowid
            for position, rule in enumerate(topic.rules):
                rule_cursor = connection.execute(
                    """
                    INSERT INTO grammar_rules (
                        topic_id, position, name, explanation, pattern,
                        verbs_json, correct_examples_json,
                        incorrect_examples_json, exceptions_json, notes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        position,
                        rule.name,
                        rule.explanation,
                        rule.pattern,
                        json.dumps(rule.verbs, ensure_ascii=False),
                        json.dumps(rule.correct_examples, ensure_ascii=False),
                        json.dumps(
                            [
                                example.model_dump()
                                for example in rule.incorrect_examples
                            ],
                            ensure_ascii=False,
                        ),
                        json.dumps(rule.exceptions, ensure_ascii=False),
                        json.dumps(rule.notes, ensure_ascii=False),
                    ),
                )
                grammar_rule_id = int(rule_cursor.lastrowid)
                if lesson_topic_ids is not None:
                    self._replace_lesson_grammar_memberships(
                        connection,
                        grammar_rule_id,
                        lesson_topic_ids,
                        now,
                    )
                self._save_topic_assignment(
                    connection,
                    rule.topic_assignment,
                    item_kind="grammar",
                    item_id=grammar_rule_id,
                    now=now,
                )
        return int(topic_id)

    def list_vocabulary(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, expression, normalized_expression, item_type,
                       meaning, pattern, register, level, collocations_json,
                       common_mistakes_json, tags_json
                FROM vocabulary_items
                ORDER BY expression COLLATE NOCASE
                """
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                examples = connection.execute(
                    """
                    SELECT sentence, context
                    FROM vocabulary_examples
                    WHERE vocabulary_id = ?
                    ORDER BY id
                    """,
                    (row["id"],),
                ).fetchall()
                item["examples"] = [dict(example) for example in examples]
                for key in (
                    "collocations_json",
                    "common_mistakes_json",
                    "tags_json",
                ):
                    item[key.removesuffix("_json")] = json.loads(item.pop(key))
                results.append(item)
            return results

    def list_grammar_topics(self) -> list[dict]:
        with self.connect() as connection:
            topics = connection.execute(
                """
                SELECT id, title, summary, level, tags_json, created_at
                FROM grammar_topics
                ORDER BY created_at DESC
                """
            ).fetchall()
            results = []
            for topic_row in topics:
                topic = dict(topic_row)
                topic["tags"] = json.loads(topic.pop("tags_json"))
                rule_rows = connection.execute(
                    """
                    SELECT id, name, explanation, pattern, verbs_json,
                           correct_examples_json, incorrect_examples_json,
                           exceptions_json, notes_json
                    FROM grammar_rules
                    WHERE topic_id = ?
                    ORDER BY position
                    """,
                    (topic["id"],),
                ).fetchall()
                topic["rules"] = []
                for rule_row in rule_rows:
                    rule = dict(rule_row)
                    for key in (
                        "verbs_json",
                        "correct_examples_json",
                        "incorrect_examples_json",
                        "exceptions_json",
                        "notes_json",
                    ):
                        rule[key.removesuffix("_json")] = json.loads(
                            rule.pop(key)
                        )
                    topic["rules"].append(rule)
                results.append(topic)
            return results

    def list_lesson_topics(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT lt.id, lt.name, lt.description,
                       COUNT(DISTINCT ltv.vocabulary_id) AS vocabulary_count,
                       COUNT(DISTINCT ltg.grammar_rule_id) AS grammar_count
                FROM lesson_topics lt
                LEFT JOIN lesson_topic_vocabulary ltv
                    ON ltv.lesson_topic_id = lt.id
                LEFT JOIN lesson_topic_grammar_rules ltg
                    ON ltg.lesson_topic_id = lt.id
                GROUP BY lt.id
                ORDER BY lt.name COLLATE NOCASE
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def create_lesson_topic(
        self,
        name: str,
        description: str | None = None,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO lesson_topics (
                    name, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (name.strip(), description or None, now, now),
            )
            return int(cursor.lastrowid)

    def update_lesson_topic(
        self,
        topic_id: int,
        name: str,
        description: str | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE lesson_topics
                SET name = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    description or None,
                    datetime.now(UTC).isoformat(),
                    topic_id,
                ),
            )

    def delete_lesson_topic(self, topic_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM lesson_topics WHERE id = ?",
                (topic_id,),
            )

    def get_lesson_topic_memberships(self, topic_id: int) -> dict:
        with self.connect() as connection:
            vocabulary_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT vocabulary_id
                    FROM lesson_topic_vocabulary
                    WHERE lesson_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
            ]
            grammar_rule_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT grammar_rule_id
                    FROM lesson_topic_grammar_rules
                    WHERE lesson_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
            ]
            return {
                "vocabulary_ids": vocabulary_ids,
                "grammar_rule_ids": grammar_rule_ids,
            }

    def set_lesson_topic_memberships(
        self,
        topic_id: int,
        vocabulary_ids: list[int],
        grammar_rule_ids: list[int],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM lesson_topic_vocabulary WHERE lesson_topic_id = ?",
                (topic_id,),
            )
            connection.execute(
                """
                DELETE FROM lesson_topic_grammar_rules
                WHERE lesson_topic_id = ?
                """,
                (topic_id,),
            )
            connection.executemany(
                """
                INSERT INTO lesson_topic_vocabulary (
                    lesson_topic_id, vocabulary_id, created_at
                ) VALUES (?, ?, ?)
                """,
                [(topic_id, item_id, now) for item_id in vocabulary_ids],
            )
            connection.executemany(
                """
                INSERT INTO lesson_topic_grammar_rules (
                    lesson_topic_id, grammar_rule_id, created_at
                ) VALUES (?, ?, ?)
                """,
                [(topic_id, item_id, now) for item_id in grammar_rule_ids],
            )

    def list_llm_topics(
        self,
        *,
        status: str | None = None,
        topic_kind: str | None = None,
    ) -> list[dict]:
        conditions = []
        params: list[object] = []
        if status:
            conditions.append("t.status = ?")
            params.append(status)
        if topic_kind:
            conditions.append("t.topic_kind IN (?, 'both')")
            params.append(topic_kind)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT t.id, t.name, t.slug, t.topic_kind, t.status,
                       t.created_by, t.merged_into_id,
                       COUNT(DISTINCT tv.vocabulary_id) AS vocabulary_count,
                       COUNT(DISTINCT tg.grammar_rule_id) AS grammar_count
                FROM llm_topics t
                LEFT JOIN llm_topic_vocabulary tv ON tv.llm_topic_id = t.id
                LEFT JOIN llm_topic_grammar_rules tg ON tg.llm_topic_id = t.id
                {where}
                GROUP BY t.id
                ORDER BY t.name COLLATE NOCASE
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def approved_topic_catalog(self, topic_kind: str) -> list[dict]:
        return [
            {"name": topic["name"], "slug": topic["slug"]}
            for topic in self.list_llm_topics(
                status="approved",
                topic_kind=topic_kind,
            )
        ]

    def get_learning_content(
        self,
        *,
        topic_source: str,
        topic_id: int,
    ) -> dict:
        with self.connect() as connection:
            if topic_source == "lesson":
                topic_row = connection.execute(
                    """
                    SELECT id, name, description
                    FROM lesson_topics
                    WHERE id = ?
                    """,
                    (topic_id,),
                ).fetchone()
                vocabulary_rows = connection.execute(
                    """
                    SELECT vocabulary_id
                    FROM lesson_topic_vocabulary
                    WHERE lesson_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
                grammar_rows = connection.execute(
                    """
                    SELECT grammar_rule_id
                    FROM lesson_topic_grammar_rules
                    WHERE lesson_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
            elif topic_source == "llm":
                topic_row = connection.execute(
                    """
                    SELECT id, name, topic_kind, slug
                    FROM llm_topics
                    WHERE id = ? AND status = 'approved'
                    """,
                    (topic_id,),
                ).fetchone()
                vocabulary_rows = connection.execute(
                    """
                    SELECT vocabulary_id
                    FROM llm_topic_vocabulary
                    WHERE llm_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
                grammar_rows = connection.execute(
                    """
                    SELECT grammar_rule_id
                    FROM llm_topic_grammar_rules
                    WHERE llm_topic_id = ?
                    """,
                    (topic_id,),
                ).fetchall()
            else:
                raise ValueError(f"Unknown topic source: {topic_source}")

        if topic_row is None:
            raise ValueError("The selected topic does not exist.")

        vocabulary_ids = {row[0] for row in vocabulary_rows}
        grammar_rule_ids = {row[0] for row in grammar_rows}
        vocabulary = [
            item
            for item in self.list_vocabulary()
            if item["id"] in vocabulary_ids
        ]
        grammar_rules = []
        for grammar_topic in self.list_grammar_topics():
            for rule in grammar_topic["rules"]:
                if rule["id"] in grammar_rule_ids:
                    grammar_rules.append(
                        {
                            **rule,
                            "grammar_topic_title": grammar_topic["title"],
                            "grammar_topic_summary": grammar_topic["summary"],
                            "level": grammar_topic["level"],
                        }
                    )
        return {
            "topic": dict(topic_row),
            "vocabulary": vocabulary,
            "grammar_rules": grammar_rules,
        }

    def resolve_llm_topic(
        self,
        topic_id: int,
        action: str,
        *,
        target_topic_id: int | None = None,
        approved_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            if action == "approve":
                if approved_name:
                    connection.execute(
                        """
                        UPDATE llm_topics
                        SET name = ?, slug = ?, status = 'approved',
                            updated_at = ?
                        WHERE id = ? AND status = 'pending'
                        """,
                        (
                            approved_name.strip(),
                            slugify(approved_name),
                            now,
                            topic_id,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE llm_topics
                        SET status = 'approved', updated_at = ?
                        WHERE id = ? AND status = 'pending'
                        """,
                        (now, topic_id),
                    )
            elif action == "reject":
                connection.execute(
                    """
                    UPDATE llm_topics
                    SET status = 'rejected', updated_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (now, topic_id),
                )
            elif action == "merge":
                if target_topic_id is None:
                    raise ValueError("A merge target is required.")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO llm_topic_vocabulary (
                        llm_topic_id, vocabulary_id, confidence, rationale,
                        assigned_by, created_at
                    )
                    SELECT ?, vocabulary_id, confidence, rationale,
                           assigned_by, created_at
                    FROM llm_topic_vocabulary
                    WHERE llm_topic_id = ?
                    """,
                    (target_topic_id, topic_id),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO llm_topic_grammar_rules (
                        llm_topic_id, grammar_rule_id, confidence, rationale,
                        assigned_by, created_at
                    )
                    SELECT ?, grammar_rule_id, confidence, rationale,
                           assigned_by, created_at
                    FROM llm_topic_grammar_rules
                    WHERE llm_topic_id = ?
                    """,
                    (target_topic_id, topic_id),
                )
                connection.execute(
                    """
                    UPDATE llm_topics
                    SET status = 'merged', merged_into_id = ?, updated_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (target_topic_id, now, topic_id),
                )
            else:
                raise ValueError(f"Unknown topic action: {action}")

    def get_practice_candidates(
        self,
        *,
        source: str,
        lesson_topic_ids: list[int] | None = None,
        llm_topic_ids: list[int] | None = None,
    ) -> list[dict]:
        lesson_topic_ids = lesson_topic_ids or []
        llm_topic_ids = llm_topic_ids or []
        candidates: list[dict] = []
        with self.connect() as connection:
            if source in {"Vocabulary", "Mixed"}:
                rows = connection.execute(
                    """
                    SELECT v.id, v.expression, v.meaning, v.pattern,
                           COALESCE(s.attempt_count, 0) AS attempt_count,
                           COALESCE(s.mastery_score, 0) AS mastery_score,
                           s.last_practised_at, s.next_review_at
                    FROM vocabulary_items v
                    LEFT JOIN vocabulary_statistics s
                        ON s.vocabulary_id = v.id
                    ORDER BY v.expression COLLATE NOCASE
                    """
                ).fetchall()
                for row in rows:
                    if not self._matches_topic_filters(
                        connection,
                        "vocabulary",
                        row["id"],
                        lesson_topic_ids,
                        llm_topic_ids,
                    ):
                        continue
                    candidate = dict(row)
                    candidate["item_key"] = f"vocabulary:{row['id']}"
                    candidate["kind"] = "vocabulary"
                    candidates.append(candidate)

            if source in {"Grammar", "Mixed"}:
                rows = connection.execute(
                    """
                    SELECT r.id, r.name, r.explanation, r.pattern,
                           r.correct_examples_json,
                           t.title AS grammar_topic,
                           COALESCE(s.attempt_count, 0) AS attempt_count,
                           COALESCE(s.mastery_score, 0) AS mastery_score,
                           s.last_practised_at, s.next_review_at
                    FROM grammar_rules r
                    JOIN grammar_topics t ON t.id = r.topic_id
                    LEFT JOIN grammar_rule_statistics s
                        ON s.grammar_rule_id = r.id
                    ORDER BY t.title COLLATE NOCASE, r.position
                    """
                ).fetchall()
                for row in rows:
                    if not self._matches_topic_filters(
                        connection,
                        "grammar",
                        row["id"],
                        lesson_topic_ids,
                        llm_topic_ids,
                    ):
                        continue
                    candidate = dict(row)
                    candidate["correct_examples"] = json.loads(
                        candidate.pop("correct_examples_json")
                    )
                    candidate["item_key"] = f"grammar_rule:{row['id']}"
                    candidate["kind"] = "grammar"
                    candidates.append(candidate)
        return candidates

    def create_practice_session(
        self,
        practice_mode: str,
        selection: dict,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO practice_sessions (
                    practice_mode, selection_json, started_at
                ) VALUES (?, ?, ?)
                """,
                (
                    practice_mode,
                    json.dumps(selection, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def progress_summary(self) -> dict:
        with self.connect() as connection:
            vocabulary = connection.execute(
                """
                SELECT COUNT(v.id) AS item_count,
                       COALESCE(AVG(s.mastery_score), 0) AS mastery,
                       COALESCE(SUM(s.attempt_count), 0) AS attempts,
                       SUM(CASE WHEN s.next_review_at <= ? THEN 1 ELSE 0 END)
                           AS due_count
                FROM vocabulary_items v
                LEFT JOIN vocabulary_statistics s ON s.vocabulary_id = v.id
                """,
                (datetime.now(UTC).isoformat(),),
            ).fetchone()
            grammar = connection.execute(
                """
                SELECT COUNT(r.id) AS item_count,
                       COALESCE(AVG(s.mastery_score), 0) AS mastery,
                       COALESCE(SUM(s.attempt_count), 0) AS attempts,
                       SUM(CASE WHEN s.next_review_at <= ? THEN 1 ELSE 0 END)
                           AS due_count
                FROM grammar_rules r
                LEFT JOIN grammar_rule_statistics s
                    ON s.grammar_rule_id = r.id
                """,
                (datetime.now(UTC).isoformat(),),
            ).fetchone()
            weakest_vocabulary = connection.execute(
                """
                SELECT v.expression AS name, s.mastery_score, s.attempt_count
                FROM vocabulary_statistics s
                JOIN vocabulary_items v ON v.id = s.vocabulary_id
                ORDER BY s.mastery_score, s.attempt_count DESC
                LIMIT 10
                """
            ).fetchall()
            weakest_grammar = connection.execute(
                """
                SELECT r.name, s.mastery_score, s.attempt_count
                FROM grammar_rule_statistics s
                JOIN grammar_rules r ON r.id = s.grammar_rule_id
                ORDER BY s.mastery_score, s.attempt_count DESC
                LIMIT 10
                """
            ).fetchall()
            return {
                "vocabulary": dict(vocabulary),
                "grammar": dict(grammar),
                "weakest_vocabulary": [
                    dict(row) for row in weakest_vocabulary
                ],
                "weakest_grammar": [dict(row) for row in weakest_grammar],
            }

    def save_attempt(
        self,
        *,
        item_type: str,
        item_key: str | None,
        question: str,
        learner_answer: str,
        verdict: str,
        score: float,
        feedback: str,
        item_keys: list[str] | None = None,
        practice_session_id: int | None = None,
    ) -> int:
        resolved_keys = item_keys or ([item_key] if item_key else [])
        with self.connect() as connection:
            return self._save_attempt(
                connection,
                item_type=item_type,
                item_key=item_key,
                resolved_keys=resolved_keys,
                question=question,
                learner_answer=learner_answer,
                verdict=verdict,
                score=score,
                feedback=feedback,
                practice_session_id=practice_session_id,
            )

    def save_attempts(self, attempts: list[dict]) -> list[int]:
        with self.connect() as connection:
            return [
                self._save_attempt(
                    connection,
                    item_type=attempt["item_type"],
                    item_key=attempt.get("item_key"),
                    resolved_keys=attempt.get("item_keys")
                    or (
                        [attempt["item_key"]]
                        if attempt.get("item_key")
                        else []
                    ),
                    question=attempt["question"],
                    learner_answer=attempt["learner_answer"],
                    verdict=attempt["verdict"],
                    score=attempt["score"],
                    feedback=attempt["feedback"],
                    practice_session_id=attempt.get("practice_session_id"),
                )
                for attempt in attempts
            ]

    def _save_attempt(
        self,
        connection: sqlite3.Connection,
        *,
        item_type: str,
        item_key: str | None,
        resolved_keys: list[str],
        question: str,
        learner_answer: str,
        verdict: str,
        score: float,
        feedback: str,
        practice_session_id: int | None,
    ) -> int:
        cursor = connection.execute(
                """
                INSERT INTO exercise_attempts (
                    item_type, item_key, question, learner_answer,
                    verdict, score, feedback, created_at, practice_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_type,
                    ", ".join(resolved_keys) or item_key,
                    question,
                    learner_answer,
                    verdict,
                    score,
                    feedback,
                    datetime.now(UTC).isoformat(),
                    practice_session_id,
                ),
        )
        attempt_id = int(cursor.lastrowid)
        for position, key in enumerate(resolved_keys):
            self._link_attempt_and_update_statistics(
                connection,
                attempt_id,
                key,
                is_primary=position == 0,
                verdict=verdict,
                score=score,
            )
        return attempt_id

    def _replace_lesson_vocabulary_memberships(
        self,
        connection: sqlite3.Connection,
        vocabulary_id: int,
        lesson_topic_ids: list[int],
        now: str,
    ) -> None:
        connection.execute(
            "DELETE FROM lesson_topic_vocabulary WHERE vocabulary_id = ?",
            (vocabulary_id,),
        )
        connection.executemany(
            """
            INSERT INTO lesson_topic_vocabulary (
                lesson_topic_id, vocabulary_id, created_at
            ) VALUES (?, ?, ?)
            """,
            [
                (topic_id, vocabulary_id, now)
                for topic_id in lesson_topic_ids
            ],
        )

    def _replace_lesson_grammar_memberships(
        self,
        connection: sqlite3.Connection,
        grammar_rule_id: int,
        lesson_topic_ids: list[int],
        now: str,
    ) -> None:
        connection.execute(
            "DELETE FROM lesson_topic_grammar_rules WHERE grammar_rule_id = ?",
            (grammar_rule_id,),
        )
        connection.executemany(
            """
            INSERT INTO lesson_topic_grammar_rules (
                lesson_topic_id, grammar_rule_id, created_at
            ) VALUES (?, ?, ?)
            """,
            [
                (topic_id, grammar_rule_id, now)
                for topic_id in lesson_topic_ids
            ],
        )

    def _save_topic_assignment(
        self,
        connection: sqlite3.Connection,
        assignment: TopicAssignment,
        *,
        item_kind: str,
        item_id: int,
        now: str,
    ) -> None:
        mapping_table = (
            "llm_topic_vocabulary"
            if item_kind == "vocabulary"
            else "llm_topic_grammar_rules"
        )
        item_column = (
            "vocabulary_id"
            if item_kind == "vocabulary"
            else "grammar_rule_id"
        )
        connection.execute(
            f"DELETE FROM {mapping_table} WHERE {item_column} = ? "
            "AND assigned_by = 'llm'",
            (item_id,),
        )
        for topic in assignment.approved_topics:
            row = connection.execute(
                """
                SELECT id FROM llm_topics
                WHERE slug = ? AND status = 'approved'
                  AND topic_kind IN (?, 'both')
                """,
                (topic.slug, item_kind),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"Unknown approved {item_kind} topic: {topic.slug}"
                )
            connection.execute(
                f"""
                INSERT OR REPLACE INTO {mapping_table} (
                    llm_topic_id, {item_column}, confidence, rationale,
                    assigned_by, created_at
                ) VALUES (?, ?, ?, ?, 'llm', ?)
                """,
                (
                    row["id"],
                    item_id,
                    topic.confidence,
                    topic.rationale,
                    now,
                ),
            )

        for proposal in assignment.proposed_topics:
            proposal_slug = slugify(proposal.name)
            row = connection.execute(
                """
                SELECT id, status, topic_kind
                FROM llm_topics
                WHERE slug = ?
                """,
                (proposal_slug,),
            ).fetchone()
            if row is None:
                cursor = connection.execute(
                    """
                    INSERT INTO llm_topics (
                        name, slug, topic_kind, status, created_by,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 'pending', 'llm', ?, ?)
                    """,
                    (
                        proposal.name.strip(),
                        proposal_slug,
                        item_kind,
                        now,
                        now,
                    ),
                )
                topic_id = int(cursor.lastrowid)
            elif (
                row["status"] in {"approved", "pending"}
                and row["topic_kind"] in {item_kind, "both"}
            ):
                topic_id = int(row["id"])
            else:
                continue
            connection.execute(
                f"""
                INSERT OR REPLACE INTO {mapping_table} (
                    llm_topic_id, {item_column}, confidence, rationale,
                    assigned_by, created_at
                ) VALUES (?, ?, ?, ?, 'llm', ?)
                """,
                (
                    topic_id,
                    item_id,
                    proposal.confidence,
                    proposal.rationale,
                    now,
                ),
            )

    def _matches_topic_filters(
        self,
        connection: sqlite3.Connection,
        item_kind: str,
        item_id: int,
        lesson_topic_ids: list[int],
        llm_topic_ids: list[int],
    ) -> bool:
        if not lesson_topic_ids and not llm_topic_ids:
            return True
        lesson_table = (
            "lesson_topic_vocabulary"
            if item_kind == "vocabulary"
            else "lesson_topic_grammar_rules"
        )
        llm_table = (
            "llm_topic_vocabulary"
            if item_kind == "vocabulary"
            else "llm_topic_grammar_rules"
        )
        item_column = (
            "vocabulary_id"
            if item_kind == "vocabulary"
            else "grammar_rule_id"
        )
        if lesson_topic_ids:
            placeholders = ",".join("?" for _ in lesson_topic_ids)
            row = connection.execute(
                f"""
                SELECT 1 FROM {lesson_table}
                WHERE {item_column} = ?
                  AND lesson_topic_id IN ({placeholders})
                LIMIT 1
                """,
                [item_id, *lesson_topic_ids],
            ).fetchone()
            if row:
                return True
        if llm_topic_ids:
            placeholders = ",".join("?" for _ in llm_topic_ids)
            row = connection.execute(
                f"""
                SELECT 1 FROM {llm_table} m
                JOIN llm_topics t ON t.id = m.llm_topic_id
                WHERE m.{item_column} = ?
                  AND m.llm_topic_id IN ({placeholders})
                  AND t.status = 'approved'
                LIMIT 1
                """,
                [item_id, *llm_topic_ids],
            ).fetchone()
            if row:
                return True
        return False

    def _link_attempt_and_update_statistics(
        self,
        connection: sqlite3.Connection,
        attempt_id: int,
        item_key: str,
        *,
        is_primary: bool,
        verdict: str,
        score: float,
    ) -> None:
        try:
            item_type, raw_id = item_key.split(":", 1)
            item_id = int(raw_id)
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid learning item key: {item_key}") from error

        if item_type == "vocabulary":
            link_table = "attempt_vocabulary"
            link_column = "vocabulary_id"
            stats_table = "vocabulary_statistics"
            stats_column = "vocabulary_id"
        elif item_type == "grammar_rule":
            link_table = "attempt_grammar_rules"
            link_column = "grammar_rule_id"
            stats_table = "grammar_rule_statistics"
            stats_column = "grammar_rule_id"
        else:
            raise ValueError(f"Unsupported learning item type: {item_type}")

        connection.execute(
            f"""
            INSERT INTO {link_table} (
                attempt_id, {link_column}, is_primary
            ) VALUES (?, ?, ?)
            """,
            (attempt_id, item_id, int(is_primary)),
        )
        previous = connection.execute(
            f"SELECT * FROM {stats_table} WHERE {stats_column} = ?",
            (item_id,),
        ).fetchone()
        attempt_count = int(previous["attempt_count"]) if previous else 0
        previous_mastery = (
            float(previous["mastery_score"]) if previous else 0.0
        )
        previous_streak = int(previous["current_streak"]) if previous else 0
        current_streak = (
            previous_streak + 1 if verdict == "correct" else 0
        )
        longest_streak = max(
            int(previous["longest_streak"]) if previous else 0,
            current_streak,
        )
        mastery = update_mastery(
            previous_mastery=previous_mastery,
            attempt_count=attempt_count,
            answer_score=score,
        )
        now = datetime.now(UTC)
        counters = {
            "correct": (1, 0, 0),
            "partially_correct": (0, 1, 0),
            "incorrect": (0, 0, 1),
        }
        correct, partial, incorrect = counters[verdict]
        connection.execute(
            f"""
            INSERT INTO {stats_table} (
                {stats_column}, attempt_count, correct_count, partial_count,
                incorrect_count, total_score, mastery_score, current_streak,
                longest_streak, last_practised_at, next_review_at, updated_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT({stats_column}) DO UPDATE SET
                attempt_count = attempt_count + 1,
                correct_count = correct_count + excluded.correct_count,
                partial_count = partial_count + excluded.partial_count,
                incorrect_count = incorrect_count + excluded.incorrect_count,
                total_score = total_score + excluded.total_score,
                mastery_score = excluded.mastery_score,
                current_streak = excluded.current_streak,
                longest_streak = excluded.longest_streak,
                last_practised_at = excluded.last_practised_at,
                next_review_at = excluded.next_review_at,
                updated_at = excluded.updated_at
            """,
            (
                item_id,
                correct,
                partial,
                incorrect,
                score,
                mastery,
                current_streak,
                longest_streak,
                now.isoformat(),
                next_review_at(
                    verdict=verdict,
                    current_streak=current_streak,
                    now=now,
                ).isoformat(),
                now.isoformat(),
            ),
        )
