Implement this persistence change:

$ARGUMENTS

## Before editing

1. Read `AGENTS.md`.
2. Inspect the current SQLite schema and every method using affected tables.
3. Identify existing data that must be preserved.
4. Design a forward migration.

## Requirements

- Do not delete or recreate the learner's database.
- Use a transaction.
- Keep foreign-key enforcement enabled.
- Make migrations safe to run exactly once.
- Preserve exercise and review history.
- Update read and write paths together.
- Add migration and persistence tests.
- Update README if backup or upgrade instructions change.

Do not store queryable relationships only inside JSON fields.

