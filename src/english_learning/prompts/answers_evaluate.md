Evaluate every learner answer against its exercise and expected answers.

- Return exactly one evaluation for every submitted exercise_index.
- Preserve each exercise_index unchanged.
- Accept grammatically correct answers that preserve the required meaning,
  even when wording differs from the reference.
- Treat each learner answer as the text inserted into its sentence blank.
- For vocabulary, check the word or phrase for form, meaning, collocation,
  register, and grammatical fit.
- For grammar, check the tested rule, verb form, agreement, word order, and
  meaning.
- If an answer is wrong or partially correct, explain the exact problem and
  provide the correct missing text in corrected_answer.
- For a correct answer, corrected_answer must be null.
- Do not penalise punctuation or capitalisation unless they are being tested.
- Give concise, constructive explanations suitable for a {learner_level}
  learner using {english_variant} English.
- Return only data matching the supplied JSON schema.
