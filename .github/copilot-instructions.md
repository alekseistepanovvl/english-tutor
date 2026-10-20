# GitHub Copilot Instructions

Follow `AGENTS.md` as the canonical development guide.

This is a local-first Python application using Streamlit, SQLite, Pydantic,
and Ollama.

## Critical rules

- SQLite is the source of truth.
- Ollama must never write directly to the database.
- Validate structured model output with Pydantic.
- Keep deterministic logic outside the LLM.
- Preview generated learning content before saving it.
- Preserve learner data through explicit migrations.
- Keep Streamlit concerns out of database and domain modules.
- Add focused tests and update README when behaviour or setup changes.
- Do not add cloud dependencies, vector databases, or agent frameworks
  without an explicit requirement.

