from __future__ import annotations

import json
import logging
import sqlite3

import streamlit as st
from pydantic import ValidationError

logger = logging.getLogger("english_learning")
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(console_handler)
    logger.propagate = False
logger.setLevel(logging.INFO)

from english_learning.config import load_settings
from english_learning.database import Database
from english_learning.domain import (
    AnswerEvaluation,
    GrammarTopic,
    VocabularyImport,
)
from english_learning.llm import OllamaClient, OllamaError
from english_learning.scheduling import (
    select_practice_items,
    shuffle_exercises,
)


st.set_page_config(
    page_title="Local English Learning",
    page_icon="📚",
    layout="wide",
)

settings = load_settings()
database = Database(settings.database_path)
database.initialize()
llm = OllamaClient(settings)


def formatted_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True)
    return json.dumps(value, ensure_ascii=False, indent=2)


def lesson_topic_selector(key: str) -> list[int]:
    topics = database.list_lesson_topics()
    names = [topic["name"] for topic in topics]
    selected_names = st.multiselect(
        "Lesson topics",
        names,
        key=key,
        help="Optional manual lesson groups. LLM topics are assigned separately.",
    )
    return [
        topic["id"] for topic in topics if topic["name"] in selected_names
    ]


def vocabulary_page() -> None:
    st.header("Learn vocabulary")
    st.write(
        "Paste words or expressions. The model creates structured records "
        "and suggests semantic topics."
    )
    selected_lesson_topics = lesson_topic_selector("vocabulary_lessons")
    raw_input = st.text_area(
        "Words and expressions",
        height=220,
        placeholder=(
            "a safe pair of hands\n"
            "to knock around with\n"
            "to keep oneself to oneself"
        ),
    )
    if st.button("Generate vocabulary", type="primary"):
        if not raw_input.strip():
            st.warning("Enter at least one word or expression.")
        else:
            try:
                generated = llm.generate_vocabulary(
                    raw_input,
                    database.approved_topic_catalog("vocabulary"),
                )
                st.session_state["vocabulary_preview"] = formatted_json(
                    generated
                )
                st.session_state["vocabulary_lesson_ids"] = (
                    selected_lesson_topics
                )
            except OllamaError as error:
                st.error(str(error))

    if preview := st.session_state.get("vocabulary_preview"):
        edited = st.text_area(
            "Review vocabulary and LLM topic suggestions",
            value=preview,
            height=500,
            key="vocabulary_editor",
        )
        if st.button("Validate and save vocabulary"):
            try:
                vocabulary = VocabularyImport.model_validate_json(edited)
                count = database.save_vocabulary(
                    vocabulary.items,
                    st.session_state.get("vocabulary_lesson_ids", []),
                )
                logger.info("Saved %d vocabulary item(s)", count)
                st.success(f"Saved {count} vocabulary item(s).")
                del st.session_state["vocabulary_preview"]
                st.rerun()
            except (ValidationError, ValueError, sqlite3.IntegrityError) as error:
                st.error(f"Could not save vocabulary:\n\n{error}")


def grammar_page() -> None:
    st.header("Learn grammar")
    st.write(
        "Paste a grammar topic or your notes. The model classifies each "
        "individual rule."
    )
    selected_lesson_topics = lesson_topic_selector("grammar_lessons")
    raw_input = st.text_area(
        "Grammar notes",
        height=300,
        placeholder=(
            "Verb + to-infinitive: Some verbs are followed by to + verb..."
        ),
    )
    if st.button("Generate grammar", type="primary"):
        if not raw_input.strip():
            st.warning("Enter a grammar rule or topic.")
        else:
            try:
                generated = llm.generate_grammar(
                    raw_input,
                    database.approved_topic_catalog("grammar"),
                )
                st.session_state["grammar_preview"] = formatted_json(generated)
                st.session_state["grammar_lesson_ids"] = selected_lesson_topics
            except OllamaError as error:
                st.error(str(error))

    if preview := st.session_state.get("grammar_preview"):
        edited = st.text_area(
            "Review grammar and LLM topic suggestions",
            value=preview,
            height=560,
            key="grammar_editor",
        )
        if st.button("Validate and save grammar"):
            try:
                topic = GrammarTopic.model_validate_json(edited)
                database.save_grammar_topic(
                    topic,
                    st.session_state.get("grammar_lesson_ids", []),
                )
                logger.info("Saved grammar topic: %s", topic.title)
                st.success(f'Saved grammar topic "{topic.title}".')
                del st.session_state["grammar_preview"]
                st.rerun()
            except (ValidationError, ValueError, sqlite3.IntegrityError) as error:
                st.error(f"Could not save grammar:\n\n{error}")


def deterministic_evaluation(
    learner_answer: str,
    expected_answers: list[str],
) -> AnswerEvaluation:
    normalised = learner_answer.strip().casefold()
    correct = any(
        normalised == expected.strip().casefold()
        for expected in expected_answers
    )
    return AnswerEvaluation(
        verdict="correct" if correct else "incorrect",
        score=1.0 if correct else 0.0,
        corrected_answer=None if correct else expected_answers[0],
        explanation=(
            "Correct."
            if correct
            else "That option does not match the expected answer."
        ),
        error_categories=[] if correct else ["incorrect-choice"],
        review_again=not correct,
    )


def practice_page() -> None:
    st.header("Practice")
    source = st.radio(
        "Material",
        ["Vocabulary", "Grammar", "Mixed"],
        horizontal=True,
    )
    lesson_topics = database.list_lesson_topics()
    llm_topics = database.list_llm_topics(status="approved")
    lesson_names = [topic["name"] for topic in lesson_topics]
    llm_names = [
        topic["name"]
        for topic in llm_topics
        if source == "Mixed"
        or topic["topic_kind"] == source.lower()
        or topic["topic_kind"] == "both"
    ]

    selected_lessons = st.multiselect(
        "Filter by lesson topics",
        lesson_names,
    )
    selected_llm_topics = st.multiselect(
        "Filter by LLM topics",
        llm_names,
    )
    selection_strategy = st.radio(
        "Choose practice items",
        ["Random", "Least mastered"],
        horizontal=True,
        help=(
            "Least mastered selects items with the lowest mastery first; "
            "unpractised items count as not yet mastered."
        ),
    )
    exercise_count = st.slider("Number of exercises", 1, 10, 5)

    lesson_ids = [
        topic["id"]
        for topic in lesson_topics
        if topic["name"] in selected_lessons
    ]
    llm_ids = [
        topic["id"]
        for topic in llm_topics
        if topic["name"] in selected_llm_topics
    ]
    candidates = database.get_practice_candidates(
        source=source,
        lesson_topic_ids=lesson_ids,
        llm_topic_ids=llm_ids,
    )
    st.caption(
        f"{len(candidates)} learning item(s) match the current filters."
    )

    if st.button("Generate practice", type="primary"):
        if not candidates:
            st.warning("No saved learning items match the selected filters.")
        else:
            selected_items = select_practice_items(
                candidates,
                min(exercise_count, len(candidates)),
                strategy=(
                    "random"
                    if selection_strategy == "Random"
                    else "least_mastered"
                ),
            )
            try:
                generated = llm.generate_exercises(
                    selected_items,
                    exercise_count,
                )
                generated.exercises = shuffle_exercises(generated.exercises)
                session_id = database.create_practice_session(
                    source.lower(),
                    {
                        "source": source,
                        "lesson_topic_ids": lesson_ids,
                        "llm_topic_ids": llm_ids,
                        "selected_item_keys": [
                            item["item_key"] for item in selected_items
                        ],
                    },
                )
                st.session_state["exercise_set"] = generated
                st.session_state["practice_material"] = selected_items
                st.session_state["practice_source"] = source
                st.session_state["practice_session_id"] = session_id
                st.session_state["evaluations"] = {}
                st.session_state["recorded_exercises"] = []
                logger.info(
                    "Started %s practice with %d selected item(s)",
                    source.lower(),
                    len(selected_items),
                )
            except OllamaError as error:
                st.error(str(error))

    exercise_set = st.session_state.get("exercise_set")
    if not exercise_set:
        return

    practice_material = st.session_state.get("practice_material", [])
    vocabulary_material = [
        item for item in practice_material if item["kind"] == "vocabulary"
    ]
    grammar_material = [
        item for item in practice_material if item["kind"] == "grammar"
    ]

    st.divider()
    st.header("Material for this practice")
    if vocabulary_material:
        st.subheader("Vocabulary bank")
        st.write(
            "Use these words or phrases to complete the vocabulary sentences."
        )
        for item in vocabulary_material:
            st.markdown(
                f"- **{item['expression']}** — {item['meaning']}"
            )
    if grammar_material:
        st.subheader("Grammar rules")
        st.write("Use these rules to form the missing part of each sentence.")
        for item in grammar_material:
            with st.expander(
                f"{item['grammar_topic']} — {item['name']}",
                expanded=True,
            ):
                st.write(item["explanation"])
                st.write(f"**Pattern:** `{item['pattern']}`")
                if item.get("correct_examples"):
                    st.markdown("**Examples:**")
                    for example in item["correct_examples"]:
                        st.write(f"- {example}")

    st.header("Exercises")
    for index, exercise in enumerate(exercise_set.exercises):
        st.divider()
        st.subheader(f"{index + 1}. {exercise.question}")
        if exercise.cue:
            st.write(f"**Cue:** {exercise.cue}")
        if exercise.options:
            answer = st.radio(
                "Choose an answer",
                exercise.options,
                key=f"answer_{index}",
                index=None,
            )
        else:
            answer = st.text_input(
                "Text for the blank",
                key=f"answer_{index}",
                placeholder="Type only the missing word or phrase",
            )

        already_recorded = index in st.session_state["recorded_exercises"]
        if st.button(
            "Check answer",
            key=f"check_{index}",
            disabled=already_recorded,
        ):
            if not answer:
                st.warning("Enter an answer first.")
            else:
                try:
                    if exercise.options:
                        evaluation = deterministic_evaluation(
                            str(answer),
                            exercise.expected_answers,
                        )
                    else:
                        evaluation = llm.evaluate_answer(
                            exercise,
                            str(answer),
                        )
                    st.session_state["evaluations"][index] = evaluation
                    item_keys = [
                        exercise.primary_item_key,
                        *exercise.supporting_item_keys,
                    ]
                    database.save_attempt(
                        item_type=st.session_state.get(
                            "practice_source",
                            source,
                        ).lower(),
                        item_key=None,
                        item_keys=item_keys,
                        question=exercise.question,
                        learner_answer=str(answer),
                        verdict=evaluation.verdict,
                        score=evaluation.score,
                        feedback=evaluation.explanation,
                        practice_session_id=st.session_state.get(
                            "practice_session_id"
                        ),
                    )
                    st.session_state["recorded_exercises"].append(index)
                    logger.info(
                        "Recorded practice answer verdict=%s",
                        evaluation.verdict,
                    )
                except (OllamaError, ValueError, sqlite3.IntegrityError) as error:
                    st.error(str(error))

        evaluation = st.session_state["evaluations"].get(index)
        if evaluation:
            if evaluation.verdict == "correct":
                st.success("Correct")
            elif evaluation.verdict == "partially_correct":
                st.warning("Partially correct")
            else:
                st.error("Incorrect")
            st.write(f"**Why:** {evaluation.explanation}")
            if evaluation.verdict != "correct":
                correct_answer = (
                    evaluation.corrected_answer
                    or exercise.expected_answers[0]
                )
                st.write(f"**Correct answer:** {correct_answer}")
            with st.expander("Rule or usage explanation"):
                st.write(exercise.explanation)
                st.write(
                    "**Accepted answer(s):** "
                    + ", ".join(exercise.expected_answers)
                )


def topics_page() -> None:
    st.header("Topics")
    lesson_tab, approved_tab, pending_tab = st.tabs(
        ["Lesson topics", "Approved LLM topics", "Pending proposals"]
    )

    vocabulary = database.list_vocabulary()
    grammar_topics = database.list_grammar_topics()
    grammar_rules = [
        {
            "id": rule["id"],
            "label": f"{topic['title']} — {rule['name']}",
        }
        for topic in grammar_topics
        for rule in topic["rules"]
    ]

    with lesson_tab:
        with st.form("create_lesson_topic"):
            name = st.text_input("New lesson topic name")
            description = st.text_area("Description", height=80)
            if st.form_submit_button("Create lesson topic"):
                if not name.strip():
                    st.warning("Enter a topic name.")
                else:
                    try:
                        database.create_lesson_topic(name, description)
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("A lesson topic with that name already exists.")

        for topic in database.list_lesson_topics():
            memberships = database.get_lesson_topic_memberships(topic["id"])
            with st.expander(
                f"{topic['name']} "
                f"({topic['vocabulary_count']} vocabulary, "
                f"{topic['grammar_count']} grammar)"
            ):
                edited_name = st.text_input(
                    "Name",
                    topic["name"],
                    key=f"lesson_name_{topic['id']}",
                )
                edited_description = st.text_area(
                    "Description",
                    topic["description"] or "",
                    key=f"lesson_description_{topic['id']}",
                )
                selected_vocabulary = st.multiselect(
                    "Vocabulary",
                    [item["expression"] for item in vocabulary],
                    default=[
                        item["expression"]
                        for item in vocabulary
                        if item["id"] in memberships["vocabulary_ids"]
                    ],
                    key=f"lesson_vocab_{topic['id']}",
                )
                selected_grammar = st.multiselect(
                    "Grammar rules",
                    [rule["label"] for rule in grammar_rules],
                    default=[
                        rule["label"]
                        for rule in grammar_rules
                        if rule["id"] in memberships["grammar_rule_ids"]
                    ],
                    key=f"lesson_grammar_{topic['id']}",
                )
                left, right = st.columns(2)
                if left.button(
                    "Save topic",
                    key=f"save_lesson_{topic['id']}",
                ):
                    try:
                        database.update_lesson_topic(
                            topic["id"],
                            edited_name,
                            edited_description,
                        )
                        database.set_lesson_topic_memberships(
                            topic["id"],
                            [
                                item["id"]
                                for item in vocabulary
                                if item["expression"] in selected_vocabulary
                            ],
                            [
                                rule["id"]
                                for rule in grammar_rules
                                if rule["label"] in selected_grammar
                            ],
                        )
                        st.rerun()
                    except sqlite3.IntegrityError as error:
                        st.error(f"Could not save topic: {error}")
                if right.button(
                    "Delete topic",
                    key=f"delete_lesson_{topic['id']}",
                ):
                    database.delete_lesson_topic(topic["id"])
                    st.rerun()

    with approved_tab:
        approved = database.list_llm_topics(status="approved")
        if not approved:
            st.info("No approved LLM topics.")
        for topic in approved:
            st.write(
                f"**{topic['name']}** · {topic['topic_kind']} · "
                f"{topic['vocabulary_count']} vocabulary · "
                f"{topic['grammar_count']} grammar"
            )

    with pending_tab:
        pending = database.list_llm_topics(status="pending")
        approved = database.list_llm_topics(status="approved")
        approved_labels = [topic["name"] for topic in approved]
        if not pending:
            st.info("No pending LLM topic proposals.")
        for topic in pending:
            with st.expander(
                f"{topic['name']} ({topic['topic_kind']})"
            ):
                approved_name = st.text_input(
                    "Approved name",
                    topic["name"],
                    key=f"pending_name_{topic['id']}",
                )
                merge_target = st.selectbox(
                    "Merge into",
                    [""] + approved_labels,
                    key=f"pending_merge_{topic['id']}",
                )
                approve_col, merge_col, reject_col = st.columns(3)
                if approve_col.button(
                    "Approve",
                    key=f"approve_{topic['id']}",
                ):
                    try:
                        database.resolve_llm_topic(
                            topic["id"],
                            "approve",
                            approved_name=approved_name,
                        )
                        st.rerun()
                    except sqlite3.IntegrityError as error:
                        st.error(f"Could not approve topic: {error}")
                if merge_col.button(
                    "Merge",
                    key=f"merge_{topic['id']}",
                    disabled=not merge_target,
                ):
                    target_id = next(
                        item["id"]
                        for item in approved
                        if item["name"] == merge_target
                    )
                    database.resolve_llm_topic(
                        topic["id"],
                        "merge",
                        target_topic_id=target_id,
                    )
                    st.rerun()
                if reject_col.button(
                    "Reject",
                    key=f"reject_{topic['id']}",
                ):
                    database.resolve_llm_topic(topic["id"], "reject")
                    st.rerun()


def learning_page() -> None:
    st.header("Learn by topic")
    st.write(
        "Choose a lesson topic or an approved LLM topic to study all of its "
        "vocabulary and grammar explanations."
    )
    topic_source_label = st.radio(
        "Topic source",
        ["Lesson topics", "LLM topics"],
        horizontal=True,
    )
    if topic_source_label == "Lesson topics":
        topic_source = "lesson"
        topics = database.list_lesson_topics()
    else:
        topic_source = "llm"
        topics = database.list_llm_topics(status="approved")

    if not topics:
        st.info(f"No {topic_source_label.lower()} are available yet.")
        return

    topic_names = [topic["name"] for topic in topics]
    selected_name = st.selectbox("Topic", topic_names)
    selected_topic = next(
        topic for topic in topics if topic["name"] == selected_name
    )
    material = st.radio(
        "Learning material",
        ["Vocabulary", "Grammar", "Both"],
        horizontal=True,
    )
    content = database.get_learning_content(
        topic_source=topic_source,
        topic_id=selected_topic["id"],
    )
    vocabulary = content["vocabulary"]
    grammar_rules = content["grammar_rules"]

    if topic_source == "lesson" and content["topic"].get("description"):
        st.write(content["topic"]["description"])
    st.caption(
        f"{len(vocabulary)} vocabulary item(s) · "
        f"{len(grammar_rules)} grammar rule(s)"
    )

    if material in {"Vocabulary", "Both"}:
        st.subheader("Vocabulary")
        if not vocabulary:
            st.info("This topic does not contain vocabulary yet.")
        for item in vocabulary:
            with st.expander(item["expression"], expanded=True):
                st.write(f"**Meaning:** {item['meaning']}")
                if item["pattern"]:
                    st.write(f"**Pattern:** `{item['pattern']}`")
                st.write(
                    f"**Type:** {item['item_type']} · "
                    f"**Register:** {item['register']} · "
                    f"**Level:** {item['level'] or 'Not set'}"
                )
                st.markdown("**Examples:**")
                for example in item["examples"]:
                    context = (
                        f" _({example['context']})_"
                        if example["context"]
                        else ""
                    )
                    st.write(f"- {example['sentence']}{context}")
                if item["collocations"]:
                    st.write(
                        "**Collocations:** "
                        + ", ".join(item["collocations"])
                    )
                if item["common_mistakes"]:
                    st.markdown("**Common mistakes:**")
                    for mistake in item["common_mistakes"]:
                        st.write(f"- {mistake}")

    if material in {"Grammar", "Both"}:
        st.subheader("Grammar")
        if not grammar_rules:
            st.info("This topic does not contain grammar rules yet.")
        for rule in grammar_rules:
            with st.expander(
                f"{rule['grammar_topic_title']} — {rule['name']}",
                expanded=True,
            ):
                st.write(rule["explanation"])
                st.write(f"**Pattern:** `{rule['pattern']}`")
                if rule["verbs"]:
                    st.write("**Common verbs:** " + ", ".join(rule["verbs"]))
                st.markdown("**Examples:**")
                for example in rule["correct_examples"]:
                    st.write(f"- {example}")
                if rule["incorrect_examples"]:
                    st.markdown("**Common mistakes:**")
                    for example in rule["incorrect_examples"]:
                        st.write(
                            f"- ~~{example['incorrect']}~~ → "
                            f"**{example['correct']}** — {example['reason']}"
                        )
                if rule["exceptions"]:
                    st.markdown("**Exceptions:**")
                    for exception in rule["exceptions"]:
                        st.write(f"- {exception}")
                if rule["notes"]:
                    st.markdown("**Notes:**")
                    for note in rule["notes"]:
                        st.write(f"- {note}")


def library_page() -> None:
    st.header("Library")
    vocabulary_tab, grammar_tab = st.tabs(["Vocabulary", "Grammar"])

    with vocabulary_tab:
        vocabulary = database.list_vocabulary()
        if not vocabulary:
            st.info("No vocabulary has been saved yet.")
        for item in vocabulary:
            with st.expander(item["expression"]):
                st.write(f"**Meaning:** {item['meaning']}")
                if item["pattern"]:
                    st.write(f"**Pattern:** `{item['pattern']}`")
                st.write(
                    f"**Type:** {item['item_type']} · "
                    f"**Register:** {item['register']} · "
                    f"**Level:** {item['level'] or 'Not set'}"
                )
                for example in item["examples"]:
                    st.write(f"- {example['sentence']}")
                if item["tags"]:
                    st.caption("Tags: " + ", ".join(item["tags"]))

    with grammar_tab:
        topics = database.list_grammar_topics()
        if not topics:
            st.info("No grammar topics have been saved yet.")
        for topic in topics:
            with st.expander(topic["title"]):
                st.write(topic["summary"])
                for rule in topic["rules"]:
                    st.markdown(f"#### {rule['name']}")
                    st.write(rule["explanation"])
                    st.write(f"**Pattern:** `{rule['pattern']}`")
                    for example in rule["correct_examples"]:
                        st.write(f"- {example}")


def progress_page() -> None:
    st.header("Progress")
    summary = database.progress_summary()
    vocabulary = summary["vocabulary"]
    grammar = summary["grammar"]
    columns = st.columns(4)
    columns[0].metric("Vocabulary items", vocabulary["item_count"])
    columns[1].metric(
        "Vocabulary mastery",
        f"{float(vocabulary['mastery']) * 100:.0f}%",
    )
    columns[2].metric("Grammar rules", grammar["item_count"])
    columns[3].metric(
        "Grammar mastery",
        f"{float(grammar['mastery']) * 100:.0f}%",
    )
    st.write(
        f"**Due now:** {vocabulary['due_count'] or 0} vocabulary item(s), "
        f"{grammar['due_count'] or 0} grammar rule(s)"
    )
    vocabulary_col, grammar_col = st.columns(2)
    with vocabulary_col:
        st.subheader("Vocabulary needing attention")
        if summary["weakest_vocabulary"]:
            st.dataframe(
                summary["weakest_vocabulary"],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No vocabulary attempts yet.")
    with grammar_col:
        st.subheader("Grammar needing attention")
        if summary["weakest_grammar"]:
            st.dataframe(
                summary["weakest_grammar"],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No grammar attempts yet.")

    st.subheader("Lesson topics")
    st.dataframe(
        database.list_lesson_topics(),
        use_container_width=True,
        hide_index=True,
    )


st.title("Local English Learning")
st.caption(
    f"Model: {settings.model} · Level: {settings.learner_level} · "
    f"Variant: {settings.english_variant}"
)

if not llm.is_available():
    st.warning(
        "Ollama is not reachable. Saved content, topics, and statistics remain "
        "available, but generation and free-text evaluation require Ollama."
    )

page = st.sidebar.radio(
    "Navigation",
    [
        "Vocabulary",
        "Grammar",
        "Learn",
        "Practice",
        "Topics",
        "Library",
        "Progress",
    ],
)

if not st.session_state.get("application_started"):
    logger.info("Application session started with model=%s", settings.model)
    st.session_state["application_started"] = True
if st.session_state.get("logged_page") != page:
    logger.info("Opened %s page", page)
    st.session_state["logged_page"] = page

if page == "Vocabulary":
    vocabulary_page()
elif page == "Grammar":
    grammar_page()
elif page == "Learn":
    learning_page()
elif page == "Practice":
    practice_page()
elif page == "Topics":
    topics_page()
elif page == "Library":
    library_page()
else:
    progress_page()
