# Claude Code Instructions

Read and follow `AGENTS.md` before modifying this project.

## Before implementation

1. Read `README.md`.
2. Inspect the relevant domain, database, LLM, prompt, and UI code.
3. Identify whether the change affects persistent data.
4. Identify whether deterministic logic can replace an LLM call.

## While implementing

- Preserve the architectural boundaries in `AGENTS.md`.
- Make minimal, complete changes.
- Add or update focused tests.
- Update documentation when setup or behaviour changes.
- Never let the LLM write directly to the database.
- Never bypass Pydantic validation for structured model output.
- Never weaken error handling to make a test pass.

## Before finishing

1. Run relevant tests.
2. Run the complete test suite if shared code changed.
3. Confirm that new runtime prompts have matching response schemas.
4. Report changed files, important decisions, and remaining limitations.

