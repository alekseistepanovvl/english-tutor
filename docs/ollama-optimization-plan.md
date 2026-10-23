# Ollama Optimization Plan

## Purpose

This plan prioritizes improvements to local Ollama response time, resource use,
and structured-output reliability. Optimization must preserve the application
invariants:

- deterministic work stays in Python
- Ollama never writes to SQLite
- structured model output is validated with Pydantic
- generated learning content is previewed before saving
- learner data remains local

## Current baseline

The following optimizations are already implemented:

- Qwen thinking is disabled for structured requests
- the model remains loaded for 30 minutes by default
- grammar notes are generated in one indexed request
- output-token limits are set by task
- generated list sizes are bounded in prompts and response schemas
- successful input validation is cached in Streamlit session state
- exact duplicate checks are local and saved catalogues are excluded from
  validation prompts
- vocabulary duplicate checks use bounded indexed SQLite queries rather than
  loading the library into application memory
- exact, empty, and multiple-choice answers are evaluated in Python
- Ollama load, prompt evaluation, generation, token count, and throughput
  metrics are logged in the terminal

The configured model remains `qwen3:8b` unless the learner changes
`ENGLISH_LEARNING_MODEL`.

## Priority overview

| Priority | Recommendation | Expected influence | Primary benefit |
|---|---|---|---|
| Complete | Evaluate obvious answers in Python | High | Avoid model requests |
| Complete | Keep duplicate checks exact and local | High | Remove catalogue prompts and preserve synonyms |
| Complete | Bound grammar request batches | High | Balance speed and reliability |
| P0 | Benchmark smaller models and GPU residency | High | Increase generation speed |
| P1 | Compact request serialization | Medium | Reduce prompt tokens |
| P1 | Add optional model prewarming | Medium | Reduce first-request latency |
| P1 | Cache generated previews | Medium | Avoid repeated generation |
| P2 | Handle Ollama completion reasons | Low for speed, high for reliability | Recover from truncation |
| Continuous | Use metrics to tune each task | Indirect | Target the actual bottleneck |

## P0: High-influence optimizations

### 1. Evaluate obvious answers in Python (completed)

Normalize learner answers and expected alternatives using deterministic rules:

- case folding
- leading, trailing, and repeated whitespace removal
- punctuation normalization where it does not change meaning
- comparison with every saved expected answer

An exact normalized match should be marked correct without Ollama. Only
ambiguous or non-matching free-text answers should be included in the batched
model-evaluation request.

Acceptance criteria:

- exact answers do not produce an Ollama request
- multiple-choice behavior remains deterministic
- ambiguous answers retain the existing model-based evaluation
- results remain attached to their original exercise indexes
- focused tests cover normalization, alternatives, mixed deterministic/model
  batches, and attempt persistence

### 2. Keep duplicate checks exact and local (completed)

Python blocks only normalized copies of the same submitted or saved expression.
Normalization covers Unicode width, case, whitespace, typographic apostrophes,
and harmless terminal punctuation.

Saved vocabulary and grammar catalogues are not sent to Ollama validation.
Vocabulary synonyms, paraphrases, related expressions, and different
grammatical forms remain separate learning entries. Related or differently
scoped grammar explanations are also allowed.

Acceptance criteria:

- exact duplicate detection remains entirely deterministic
- saved catalogues are absent from validation requests
- vocabulary synonyms and related expressions are not rejected
- spelling and English-validity checks remain model-validated
- a growing library does not increase validation prompt size

### 3. Bound grammar request batches (completed)

Validated grammar notes are split into deterministic batches of at most two
notes. Every request uses the original global input indexes, and results are
returned only after all batches pass Pydantic and exact-index validation.

Acceptance criteria:

- small submissions still use one request
- large submissions are divided into deterministic bounded batches
- missing or duplicate model indexes fail explicitly
- results are restored to original input order
- no partial result is presented as a complete successful generation

### 4. Benchmark model size and GPU residency

Use the existing terminal metrics to compare the current model with a smaller
structured-output-capable model. Record:

- model and quantization
- CPU/GPU allocation from `ollama ps`
- prompt evaluation time
- generated tokens per second
- total request duration
- structured-response success rate
- output quality on representative vocabulary, grammar, exercise, and
  evaluation tasks

A faster model should be adopted only if it maintains acceptable structured
output and learning-content quality. Prefer a model that fits fully in
available GPU memory. This is a configuration and deployment decision, not an
automatic model download or code-level dependency.

## P1: Medium-influence optimizations

### 5. Compact request serialization

Remove indentation and unnecessary whitespace from JSON sent to Ollama.
Preserve Unicode content and the existing request structure.

Acceptance criteria:

- requests contain equivalent data
- structured responses remain unchanged
- prompt token counts do not increase
- learner content is still excluded from logs

### 6. Optional model prewarming

Provide an explicit model warm-up mechanism rather than blocking every
application startup. Possible interfaces are a sidebar action or a documented
startup command.

Acceptance criteria:

- warm-up does not generate or persist learning content
- failure is shown as an actionable error
- normal application startup remains usable when Ollama is unavailable
- the next real request shows negligible model load time when warm-up succeeds

### 7. Cache generated previews

Reuse successfully validated generated previews when all generation inputs are
unchanged. A cache key must include:

- task
- normalized learner input
- model
- prompt version
- learner level and English variant
- approved topic catalogue

Keep the initial cache session-local. Do not add durable database caching
without an explicit requirement and migration design.

Acceptance criteria:

- repeated generation with an identical key avoids Ollama
- edits or configuration changes invalidate the result
- clearing the current page clears the relevant preview cache
- cached content still passes through the editable preview before saving

## P2: Reliability optimization

### 8. Handle Ollama completion reasons

Log Ollama's completion reason. When a response is truncated because of its
output limit, retry once with a larger safe budget when the task can still fit
the configured context.

Do not retry malformed output indiscriminately. Validation failures unrelated
to truncation should remain explicit.

Acceptance criteria:

- completion reasons are visible in terminal diagnostics
- length truncation receives at most one bounded retry
- transport errors and schema errors are not hidden
- tests cover successful retry, repeated truncation, and non-length failures

## Continuous measurement

Interpret the existing metrics as follows:

| Observation | Likely bottleneck | Response |
|---|---|---|
| High model load duration | Cold model | Keep alive or prewarm |
| High prompt evaluation time/count | Large request context | Reduce and compact input |
| Low generated tokens per second | Model or hardware | Smaller model or better GPU residency |
| Excessive generated token count | Verbose output | Tighten prompt and response bounds |
| Low Ollama time but high UI latency | Application workflow | Profile Streamlit reruns and database queries |

Benchmark representative tasks before and after each optimization. Change one
major variable at a time so improvements can be attributed correctly.

## Suggested implementation order

1. Deterministic answer evaluation
2. Exact-only local duplicate validation
3. Bounded grammar batches
4. Compact request serialization
5. Model and GPU benchmark
6. Optional model prewarming
7. Generated-preview caching
8. Completion-reason handling

No database migration is currently expected for this plan. Reassess that
decision if a future implementation introduces durable caches, benchmark
history, or persisted model and prompt metadata.
