Verify the current implementation.

1. Read `AGENTS.md`.
2. Inspect the current changes.
3. Run the smallest relevant test selection.
4. Run the complete test suite when shared modules changed.
5. Compile or import the application to detect syntax and import failures.
6. Verify database initialization on a temporary database.
7. If UI code changed, start Streamlit headlessly and check its health endpoint.
8. Do not require a real Ollama model for ordinary automated tests.
9. Report failures with their root cause; do not hide or bypass them.

