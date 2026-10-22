from __future__ import annotations


def normalize_input(value: str) -> str:
    return " ".join(value.casefold().split())


def find_duplicate_inputs(
    inputs: list[str],
    existing_values: list[str],
) -> set[int]:
    existing = {
        normalize_input(value)
        for value in existing_values
        if value.strip()
    }
    seen: set[str] = set()
    duplicates: set[int] = set()
    for index, value in enumerate(inputs):
        normalized = normalize_input(value)
        if normalized in existing or normalized in seen:
            duplicates.add(index)
        seen.add(normalized)
    return duplicates
