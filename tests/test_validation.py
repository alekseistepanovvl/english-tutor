from english_learning.validation import (
    find_duplicate_inputs,
    normalize_input,
)


def test_normalize_input_ignores_case_and_repeated_whitespace() -> None:
    assert normalize_input("  A Safe   Pair of Hands ") == (
        "a safe pair of hands"
    )


def test_find_duplicate_inputs_checks_library_and_current_submission() -> None:
    duplicates = find_duplicate_inputs(
        ["commute", "Reliable", "COMMUTE", "a safe pair of hands"],
        ["reliable", "A safe pair of hands"],
    )

    assert duplicates == {1, 2, 3}
