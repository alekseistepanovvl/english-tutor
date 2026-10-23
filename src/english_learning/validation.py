from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Iterable


VALIDATION_PROMPT_VERSION = "2"
TERMINAL_PUNCTUATION = ".,!?;:"
APOSTROPHE_TRANSLATION = str.maketrans({"‘": "'", "’": "'"})


def normalize_input(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(APOSTROPHE_TRANSLATION).casefold()
    normalized = " ".join(normalized.split())
    return normalized.rstrip(TERMINAL_PUNCTUATION).rstrip()


def find_duplicate_inputs(
    inputs: list[str],
    existing_values: Iterable[str],
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
) -> str:
    source = "\0".join(
        (
            VALIDATION_PROMPT_VERSION,
            kind,
            model,
            normalize_input(value),
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
