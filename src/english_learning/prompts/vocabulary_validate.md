Validate each submitted English vocabulary word or expression before learning
content is generated.

- Preserve every input_index exactly and return one result for each input.
- Mark valid English words and expressions as valid.
- Mark spelling mistakes, typos, or malformed expressions as corrected and
  provide the complete corrected expression in suggested_input.
- Mark text that is not a meaningful English word or expression as invalid.
- Treat synonyms, paraphrases, related expressions, different grammatical
  forms, and expressions with overlapping meanings as distinct valid learning
  material.
- Exact duplicate detection is handled by the application, not by the model.
- Do not change a valid expression merely to prefer a synonym or different
  style.
- Keep phrasal verbs, idioms, collocations, and multi-word expressions intact.
- Explain the result briefly for a {learner_level} learner.
- Use {english_variant} English spelling and usage.
- Return only data matching the supplied JSON schema.
