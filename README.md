# Local English Learning

A local-first English learning application for building structured vocabulary
and grammar libraries, generating exercises, and evaluating answers with a
local LLM.

The application keeps learning data in SQLite on your computer. Ollama is used
only for structured content generation and semantic answer evaluation; it does
not write directly to the database.

## Current draft features

- Import words, phrases, idioms, phrasal verbs, and collocations.
- Generate meanings, patterns, register, examples, collocations, and mistakes.
- Import grammar notes and split them into structured rules.
- Preview and edit generated JSON before saving it.
- Organise vocabulary and individual grammar rules into manual lesson topics.
- Classify learning items with an approved LLM topic taxonomy.
- Review, approve, merge, or reject new LLM topic proposals.
- Browse the vocabulary and grammar library.
- Generate vocabulary, grammar, or mixed exercises by one or several topics.
- Prioritise weak, new, inactive, and overdue learning items.
- Retain a maintenance probability for well-known material.
- Evaluate free-text and multiple-choice answers.
- Check multiple-choice answers deterministically in Python.
- Store attempt history, mastery, streaks, and next-review dates in SQLite.
- Display vocabulary and grammar progress summaries.
- Upgrade existing databases through versioned migrations.
- Validate every LLM response with Pydantic.

This is an initial implementation. Full FSRS scheduling, saved-content editing,
automatic backups, topic charts, and deterministic checking of fill-in answers
are not implemented yet.

## Architecture

```text
Streamlit UI
    |
Application workflow
    |-- Pydantic validation
    |-- SQLite database
    `-- Ollama HTTP API
          `-- Local instruct model
```

The model produces a proposed structured record. The application validates it,
shows it for review, and saves it only after confirmation:

```text
Input -> Ollama -> JSON schema -> Pydantic -> preview/edit -> SQLite
```

## Requirements

- macOS, Windows, or Linux
- Python 3.11 or newer
- Ollama
- At least 8 GB RAM for a small model

A MacBook Pro with 48 GB unified memory can comfortably run the default 8B
model and can experiment with larger quantised models. Start with a smaller
model because interactive response time is more important than maximum model
size for most exercises.

## 1. Install Ollama

Download and install Ollama from:

<https://ollama.com/download>

After installation, open a terminal and confirm it is available:

```bash
ollama --version
```

Ollama normally runs its local API automatically at
`http://localhost:11434`. If it is not running, start it:

```bash
ollama serve
```

Keep that terminal open when `ollama serve` is started manually.

## 2. Download a model

The default configuration uses:

```bash
ollama pull qwen3:8b
```

Confirm that the model responds:

```bash
ollama run qwen3:8b "Give one example of a phrasal verb."
```

You can use another instruct model if it supports reliable structured output.
Set its Ollama name through `ENGLISH_LEARNING_MODEL`.

For a first run, use an 8B-14B model. Larger models may provide more nuanced
examples and corrections but consume more memory and respond more slowly.

## 3. Create the Python environment

### macOS or Linux

```bash
cd english-learning
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### Windows PowerShell

```powershell
Set-Location D:\Development\personal\english-learning
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

If PowerShell prevents virtual-environment activation, run this for the current
PowerShell process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Configure the application

Configuration is read from environment variables. The defaults work when
Ollama is local and `qwen3:8b` is installed.

| Variable | Default | Description |
|---|---|---|
| `ENGLISH_LEARNING_MODEL` | `qwen3:8b` | Ollama model name |
| `ENGLISH_LEARNING_OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `ENGLISH_LEARNING_DB` | `data/english_learning.sqlite3` | SQLite path |
| `ENGLISH_LEARNING_LEVEL` | `B2` | Target learner level |
| `ENGLISH_LEARNING_VARIANT` | `British` | English variety |

Example for macOS or Linux:

```bash
export ENGLISH_LEARNING_MODEL=qwen3:8b
export ENGLISH_LEARNING_LEVEL=B2
export ENGLISH_LEARNING_VARIANT=British
```

Example for Windows PowerShell:

```powershell
$env:ENGLISH_LEARNING_MODEL = "qwen3:8b"
$env:ENGLISH_LEARNING_LEVEL = "B2"
$env:ENGLISH_LEARNING_VARIANT = "British"
```

The included `.env.example` is documentation only; the draft deliberately does
not load `.env` files automatically. Use environment variables or add a
`.env` loader later.

## 5. Run the application

From the project directory with the virtual environment active:

```bash
streamlit run src/english_learning/app.py
```

Streamlit normally opens:

<http://localhost:8501>

## Basic workflow

### Add vocabulary

1. Open **Vocabulary**.
2. Optionally select one or more manual lesson topics.
3. Paste one or more words or expressions.
4. Select **Generate vocabulary**.
5. Review the generated content and LLM topic suggestions.
6. Correct anything inaccurate or unnatural.
7. Select **Validate and save vocabulary**.

Saving an expression with the same normalised value updates the existing
vocabulary record instead of creating a duplicate. Existing lesson memberships
are preserved when no replacement lesson selection is supplied.

### Add grammar

1. Open **Grammar**.
2. Optionally select one or more manual lesson topics.
3. Paste a grammar rule, lesson, or personal notes.
4. Select **Generate grammar**.
5. Review individual rule classifications and edit the structured data.
6. Select **Validate and save grammar**.

Grammar topics are currently inserted as new topics. Duplicate detection and
topic versioning should be added before importing a large library.

### Manage topics

1. Open **Topics**.
2. Create manual lesson topics for units, courses, or study sessions.
3. Add or remove vocabulary and individual grammar rules.
4. Review pending topics proposed by the LLM.
5. Approve, rename and approve, merge, or reject each proposal.

Seeded LLM topics are controlled taxonomy entries. The LLM may assign them
immediately, but a new proposed topic does not become a normal practice filter
until it is approved or merged.

### Practise

1. Open **Practice**.
2. Select vocabulary, grammar, or mixed material.
3. Optionally filter by one or several lesson topics and LLM topics.
4. Select the exercise count.
5. Generate the adaptive exercise set.
6. Enter each answer and select **Check answer**.

Multiple selected topics use union semantics: an item is included when it
belongs to any selected topic. With no topic filter, all material of the
selected type is eligible.

The selector favours weak, new, inactive, and overdue items. Strong items retain
a non-zero maintenance probability so they are not forgotten. Questions,
answers, scores, feedback, stable item references, mastery, streaks, and review
dates are stored in SQLite.

### View progress

Open **Progress** to see:

- vocabulary and grammar item counts
- average mastery
- due-item counts
- vocabulary and grammar needing attention
- lesson-topic sizes

## Data storage and backup

The default database is:

```text
data/english_learning.sqlite3
```

Stop the application before making a simple file-level backup:

```bash
cp data/english_learning.sqlite3 data/english_learning.backup.sqlite3
```

Windows PowerShell:

```powershell
Copy-Item data\english_learning.sqlite3 data\english_learning.backup.sqlite3
```

Do not commit the database to a public repository. The `.gitignore` excludes
SQLite database files by default.

## Prompt design

Prompts are version-controlled in:

```text
src/english_learning/prompts/
```

- `vocabulary_extract.md` creates vocabulary records.
- `grammar_extract.md` creates grammar topics and rules.
- `exercise_generate.md` creates exercises from selected saved material.
- `answer_evaluate.md` assesses an answer.

Pydantic models in `domain.py` are converted into JSON schemas and sent through
Ollama's `format` field. This is more reliable than requesting JSON only in
natural-language instructions.

Extraction and evaluation use temperature `0`. Exercise generation uses a
small amount of variation. Prompt changes should eventually receive explicit
version numbers so content can be traced to the prompt that generated it.

## Run tests

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run:

```bash
pytest
```

The tests cover persistence, migrations, manual and LLM topics, statistics, and
adaptive scheduling. They do not require Ollama.

## Project structure

```text
english-learning/
|-- AGENTS.md
|-- CLAUDE.md
|-- .claude/
|   `-- commands/
|       |-- implement-feature.md
|       |-- add-llm-workflow.md
|       |-- change-database.md
|       `-- verify.md
|-- .github/
|   `-- copilot-instructions.md
|-- pyproject.toml
|-- README.md
|-- src/
|   `-- english_learning/
|       |-- app.py
|       |-- config.py
|       |-- database.py
|       |-- domain.py
|       |-- llm.py
|       |-- migrations.py
|       |-- scheduling.py
|       `-- prompts/
|-- tests/
`-- data/
```

## Development agent instructions

`AGENTS.md` is the canonical, tool-independent development guide. It defines
the architecture, persistence rules, LLM boundaries, testing requirements, and
scope constraints.

`CLAUDE.md` provides the Claude Code entry point, while
`.github/copilot-instructions.md` gives GitHub Copilot the same core rules.

Claude Code workflow commands are available under `.claude/commands/`:

```text
/implement-feature Add vocabulary editing
/add-llm-workflow Add progressive exercise hints
/change-database Add spaced-repetition review tables
/verify
```

## Recommended next implementation steps

1. Add FSRS-based spaced-repetition scheduling.
2. Add a due-review session separate from unrestricted practice.
3. Check exact fill-in and transformation answers in Python.
4. Show and edit individual LLM topic assignments.
5. Add editing and deletion for saved library records.
6. Add JSON export and automatic SQLite backups.
7. Add prompt versions and model metadata to generated records.
8. Add progress charts and detailed topic statistics.
9. Add optional local embeddings for semantic search and duplicate detection.

Avoid adding a vector database until semantic search is actually needed.
SQLite is simpler and sufficient for thousands of learning records.

## Troubleshooting

### Ollama is not reachable

Check:

```bash
ollama list
```

Then verify the API:

```bash
curl http://localhost:11434/api/tags
```

If the request fails, start Ollama or run `ollama serve`.

### The configured model is missing

Download it:

```bash
ollama pull qwen3:8b
```

Or set `ENGLISH_LEARNING_MODEL` to a model shown by:

```bash
ollama list
```

### The model returns invalid structured data

- Retry once.
- Use a stronger instruct model.
- Keep extraction temperature at `0`.
- Reduce the amount of material imported in one request.
- Confirm that the selected model supports reliable JSON-schema output.

### The first response is slow

The first request loads the model into memory. Subsequent requests are normally
faster. A larger model also takes longer to load and generate responses.
