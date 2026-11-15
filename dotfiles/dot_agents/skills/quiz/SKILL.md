---
name: quiz
description: Runs retrieval-first practice against the user's notes and records only useful missed concepts. Use when the user invokes /quiz or asks to test recall on a note, topic, or review material.
disable-model-invocation: true
---

# Quiz for retrieval

First pick the repository whose notes the quiz draws on ([PARA workflow settings](../vault-validator/references/workflows.md)).

Ground every question in the user's notes. Use the named note or topic; otherwise offer a small choice of stale or `#review` material.

## Run the quiz

1. Ask 5–8 questions, one at a time. Mix recall, application, and explanation.
2. Wait for the learner's answer before giving any hint or revealing the answer.
3. Give immediate feedback: correct, partly correct, or incorrect; then the answer and a concise explanation grounded in the source note.
4. Adapt later questions to demonstrated strengths and misses without silently changing the announced scope.
5. End with a scorecard and the one or two weakest concepts to retrieve later.

For multiple-choice questions, keep options comparable in length and formatting so presentation does not reveal the answer.

## Retain selectively

Offer to record missed concepts only after the quiz. With approval:

- encode atomic recall as `Question::Answer` or a cloze under `## Flashcards`;
- add `#flashcards`, and add `#review` only when the note merits durable review;
- bump `updated`.

Do not create cards for every covered fact. Promote only repeatedly useful or missed concepts. Do not commit, publish, share publicly, or push without separate explicit confirmation.
