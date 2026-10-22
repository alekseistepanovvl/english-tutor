Validate each submitted English grammar note or rule before structured learning
content is generated.

- Preserve every input_index exactly and return one result for each input.
- Mark clear and grammatically meaningful rules or notes as valid.
- Mark fixable spelling, grammar, or wording problems as corrected and provide
  the complete corrected note in suggested_input.
- Mark text that is not a meaningful English grammar note or rule as invalid.
- Mark an input as invalid when it describes the same grammar rule as an item
  in existing_saved_entries, even if it is worded differently.
- Preserve the learner's intended grammatical distinction and examples.
- Do not rewrite a valid note merely for stylistic preference.
- Explain the result briefly for a {learner_level} learner.
- Use {english_variant} English spelling and usage.
- Return only data matching the supplied JSON schema.
