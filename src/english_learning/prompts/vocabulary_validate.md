Validate each submitted English vocabulary word or expression before learning
content is generated.

- Preserve every input_index exactly and return one result for each input.
- Mark valid English words and expressions as valid.
- Mark spelling mistakes, typos, or malformed expressions as corrected and
  provide the complete corrected expression in suggested_input.
- Mark text that is not a meaningful English word or expression as invalid.
- Mark an input as invalid when it is the same vocabulary entry as an item in
  existing_saved_entries. Do not treat a synonym as a duplicate.
- Do not change a valid expression merely to prefer a synonym or different
  style.
- Keep phrasal verbs, idioms, collocations, and multi-word expressions intact.
- Explain the result briefly for a {learner_level} learner.
- Use {english_variant} English spelling and usage.
- Return only data matching the supplied JSON schema.
