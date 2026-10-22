from __future__ import annotations

import hashlib


VALIDATION_PROMPT_VERSION = "1"

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


def validation_cache_key(
    *,
    kind: str,
    model: str,
    value: str,
    existing_values: list[str],
) -> str:
    normalized_existing = "\n".join(
        sorted(
            normalize_input(existing_value)
            for existing_value in existing_values
            if existing_value.strip()
        )
    )
    source = "\0".join(
        (
            VALIDATION_PROMPT_VERSION,
            kind,
            model,
            normalize_input(value),
            normalized_existing,
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
