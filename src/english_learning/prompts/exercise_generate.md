Create exercises from the supplied learning material.

Requirements:

- Use exactly the requested number of exercises.
- Target a {learner_level} learner.
- Test only the supplied vocabulary and grammar.
- Mix suitable exercise types when possible.
- Give an unambiguous expected answer where possible.
- Keep answers separate from questions.
- For multiple-choice exercises, provide one correct answer and three
  plausible distractors.
- Do not reveal the answer in the question.
- Use {english_variant} English.
- Copy one supplied item_key into primary_item_key for every exercise.
- Include other genuinely tested supplied keys in supporting_item_keys.
- Never create, alter, or guess an item key.
- Return only data matching the supplied JSON schema.
