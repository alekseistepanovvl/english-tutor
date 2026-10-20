Implement the following feature:

$ARGUMENTS

## Process

1. Read `AGENTS.md` and `README.md`.
2. Inspect all existing code related to the feature.
3. Describe the affected data flow: UI -> service -> database/LLM.
4. Determine whether the database schema needs a migration.
5. Implement the smallest complete solution.
6. Add focused tests for new behaviour and important error cases.
7. Update README documentation when necessary.
8. Run the relevant tests.

## Constraints

- Preserve existing learner data.
- Do not let Ollama control persistence or application flow.
- Validate structured Ollama responses with Pydantic.
- Keep deterministic behaviour outside the LLM.
- Do not perform unrelated refactoring.

