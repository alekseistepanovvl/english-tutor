Create exercises from the supplied learning material.

Requirements:

- Use exactly the requested number of exercises.
- Create exactly one exercise for each supplied exercise plan, in plan order.
- Use the plan's primary_item_key, context, setting, subject, and sentence
  shape. Do not exchange plans between learning items.
- Avoid every sentence in questions_to_avoid.
- Do not create superficial rewrites of another exercise in the same response.
- Vary sentence openings and grammatical structures across the response.
- Target a {learner_level} learner.
- Test only the supplied vocabulary and grammar.
- Every exercise must use exercise_type `fill_blank`.
- Every question must be a natural sentence containing exactly one `_____`.
- The learner writes only the missing word, phrase, or grammatical segment.
- Give a short instruction explaining what the learner must insert.
- Give an unambiguous expected answer.
- Keep answers separate from questions.
- Keep options empty.
- For a vocabulary item, the missing text must be the tested word or phrase.
- Make the context specific enough that the vocabulary answer is natural.
- For a grammar rule, test the grammatical form or construction described by
  the rule.
- For grammar, add a short cue in brackets when useful, such as `(go)` or
  `(refuse / help)`. Otherwise return cue as null.
- Do not reveal the exact answer in the sentence, instruction, or cue.
- Put only the missing text in expected_answers, not the complete sentence.
- Explain why the expected answer fits the vocabulary meaning or grammar rule.
- Keep instructions and explanations concise.
- Use {english_variant} English.
- Copy one supplied item_key into primary_item_key for every exercise.
- Include other genuinely tested supplied keys in supporting_item_keys.
- Never create, alter, or guess an item key.
- Return only data matching the supplied JSON schema.
