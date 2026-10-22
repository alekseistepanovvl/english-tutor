from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    model: str
    ollama_url: str
    database_path: Path
    learner_level: str
    english_variant: str
    ollama_keep_alive: str = "30m"


def load_settings() -> Settings:
    database_value = os.getenv(
        "ENGLISH_LEARNING_DB",
        "data/english_learning.sqlite3",
    )
    database_path = Path(database_value)
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    return Settings(
        model=os.getenv("ENGLISH_LEARNING_MODEL", "qwen3:8b"),
        ollama_url=os.getenv(
            "ENGLISH_LEARNING_OLLAMA_URL",
            "http://localhost:11434",
        ).rstrip("/"),
        database_path=database_path,
        learner_level=os.getenv("ENGLISH_LEARNING_LEVEL", "B2"),
        english_variant=os.getenv("ENGLISH_LEARNING_VARIANT", "British"),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
    )
