# English Learning Application - Development Instructions

## Project purpose

This is a local-first English learning application for:

- structured vocabulary learning
- structured grammar learning
- generated exercises
- answer evaluation
- spaced repetition and revision

The application uses Python, Streamlit, SQLite, Pydantic, and Ollama.

## Architecture

Keep the application as a modular monolith:

- `app.py` contains Streamlit presentation logic.
- `domain.py` contains Pydantic domain and LLM response models.
- `database.py` owns SQLite persistence.
- `llm.py` owns Ollama communication.
- `prompts/` contains runtime LLM prompts.
- Application workflows should move into service modules as they grow.

Dependency direction:

```text
UI -> services -> database
               -> LLM client
               -> scheduling
```

Do not make the database or LLM modules depend on Streamlit.

## Core invariants

- SQLite is the source of truth.
- The LLM must never write directly to SQLite.
- Validate all structured LLM output with Pydantic.
- Show generated learning content for preview before saving it.
- Use database transactions for multi-record writes.
- Do not silently ignore malformed model responses.
- Do not use the LLM for deterministic operations.
- Review scheduling must be implemented in Python.
- Exact and multiple-choice answers should be checked in Python.
- Keep learner data local by default.
- Do not introduce cloud services without an explicit requirement.

## LLM integration

- Store runtime prompts under `src/english_learning/prompts/`.
- Use one focused prompt for each LLM task.
- Send learner content in the user message, not the system prompt.
- Use Ollama structured output with Pydantic JSON schemas.
- Use temperature `0` for extraction and evaluation.
- Use a low non-zero temperature for exercise generation.
- Record model and prompt versions when persistent generated content is added.
- Treat model output as untrusted input.

## Database conventions

- Use explicit foreign keys.
- Enable `PRAGMA foreign_keys = ON`.
- Never modify an existing deployed schema without a migration.
- Avoid storing data only as large opaque JSON documents when it must be
  queried or related to other records.
- JSON columns are acceptable for small lists such as tags or notes.
- Database methods must not contain Streamlit calls.
- Preserve learner history when editing learning content.

## Domain conventions

- Prefer explicit Pydantic models over untyped dictionaries.
- Use `Field(default_factory=list)` for mutable collection defaults.
- Reject unknown structured LLM fields unless compatibility requires them.
- Keep persistence IDs separate from model-generated identifiers.
- Use stable item keys when exercises refer to saved material.

## UI conventions

- Never save generated content before the learner previews it.
- Display actionable errors rather than raw tracebacks.
- Preserve user input after recoverable failures.
- Keep learning, practice, review, and library workflows separate.
- Do not put domain or persistence rules directly in Streamlit callbacks.

## Testing

For each behavioural change:

- Add focused tests covering the new behaviour.
- Test persistence without requiring Ollama.
- Mock the Ollama boundary in application workflow tests.
- Do not call a real model from the normal test suite.
- Test malformed and incomplete model responses.
- Run the smallest relevant test set, then the complete suite.

Standard command:

```bash
python -m pytest -q
```

## Documentation

Update `README.md` when changing:

- installation
- environment variables
- database location
- required models
- startup commands
- user-visible workflows

Do not document unfinished functionality as available.

## Scope discipline

- Make focused changes.
- Do not rewrite working modules without a concrete reason.
- Do not add agent frameworks, vector databases, or cloud infrastructure
  without an explicit requirement.
- Prefer standard-library functionality when it remains clear and reliable.
- Do not commit the SQLite database, local models, `.env`, or learner data.

