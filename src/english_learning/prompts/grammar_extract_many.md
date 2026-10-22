Transform every submitted grammar note into one structured grammar topic.

- Return exactly one topic for every submitted input_index.
- Preserve every input_index unchanged.
- Keep each submitted note as a separate topic; do not merge notes.
- Give every rule a concise name and a concise explanation suitable for a
  {learner_level} learner.
- Provide a clear grammatical pattern.
- Preserve important distinctions from the learner's input.
- Include two or three natural correct examples per rule.
- Include no more than two useful incorrect examples with corrections and
  reasons.
- Include no more than three exceptions and three notes per rule.
- Include no more than five rules per topic.
- Assign no more than three approved topics to each rule, using only supplied
  approved topic slugs.
- Propose at most one concise reusable topic when no approved topic fits.
- Include confidence as a decimal from 0 to 1, never as a percentage, with a
  short rationale.
- Do not claim that a rule is absolute when common exceptions exist.
- Use {english_variant} English spelling and usage.
- Do not create exercises.
- Return only data matching the supplied JSON schema.
