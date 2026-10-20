Add or modify this LLM workflow:

$ARGUMENTS

## Requirements

1. Read `AGENTS.md`.
2. Inspect existing Pydantic schemas, `llm.py`, and runtime prompts.
3. Define the input and output contract before editing the prompt.
4. Add an explicit Pydantic response model.
5. Add a focused prompt under `src/english_learning/prompts/`.
6. Send dynamic learner content as a user message.
7. Treat the response as untrusted input.
8. Surface invalid responses as explicit application errors.
9. Keep database writes outside the LLM client.
10. Add tests with a mocked LLM boundary.
11. Document any new model or configuration requirement.

Use temperature zero for extraction and assessment. Use a low non-zero
temperature only when useful variation is required.

