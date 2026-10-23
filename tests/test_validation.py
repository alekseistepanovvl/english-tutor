from english_learning.validation import (
    find_duplicate_inputs,
    normalize_input,
    validation_cache_key,
)


def test_normalize_input_ignores_case_and_repeated_whitespace() -> None:
    assert normalize_input("  A Safe   Pair of Hands. ") == (
        "a safe pair of hands"
    )
    assert normalize_input("don’t") == "don't"


def test_find_duplicate_inputs_checks_library_and_current_submission() -> None:
    duplicates = find_duplicate_inputs(
        ["commute", "Reliable", "COMMUTE", "A safe pair of hands."],
        ["reliable", "A safe pair of hands"],
    )

    assert duplicates == {1, 2, 3}


def test_related_vocabulary_is_not_a_duplicate() -> None:
    duplicates = find_duplicate_inputs(
        ["reliable", "dependable", "a safe pair of hands"],
        ["someone you can rely on"],
    )

    assert duplicates == set()


def test_validation_cache_key_uses_normalized_input() -> None:
    first = validation_cache_key(
        kind="vocabulary",
        model="qwen3:8b",
        value="  A Safe   Pair of Hands ",
    )
    second = validation_cache_key(
        kind="vocabulary",
        model="qwen3:8b",
        value="a safe pair of hands",
    )

    assert first == second


def test_validation_cache_key_changes_with_model_or_task() -> None:
    base = validation_cache_key(
        kind="grammar",
        model="qwen3:8b",
        value="Use the present simple.",
    )

    assert base != validation_cache_key(
        kind="grammar",
        model="qwen3:4b",
        value="Use the present simple.",
    )
    assert base != validation_cache_key(
        kind="vocabulary",
        model="qwen3:8b",
        value="Use the present simple.",
    )
