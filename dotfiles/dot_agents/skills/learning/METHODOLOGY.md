# Learning methodology

Use this reference to choose pedagogy and media. It summarizes independently phrased principles; it does not reproduce third-party prompts.

## Core model

1. Define a practical capability and evidence of success.
2. Assess prior knowledge and choose novice, intermediate, or advanced support.
3. Activate retrieval when knowledge exists; use a worked example when it does not.
4. Diagnose one gap and give the minimum useful scaffold.
5. Require self-explanation or application.
6. Give specific corrective feedback.
7. Test transfer where relevant.
8. Verify independent performance without AI help.
9. Record evidence and schedule later retrieval.
10. Fade scaffolding as repeated unassisted evidence improves.

## Evidence-backed patterns

- **Retrieval and spacing:** retrieval generally improves durable retention over passive restudy; spacing and successive relearning support longer-term retention.
  - [Agarwal, Nunes & Blunt (2021), systematic review](https://doi.org/10.1007/s10648-021-09595-9)
  - [Carpenter, Pan & Butler (2022), review](https://doi.org/10.1038/s44159-022-00089-1)
- **Worked examples and fading:** novices benefit from examples and gradual completion; redundant scaffolds can hinder more knowledgeable learners.
  - [Kalyuga et al. (2003), expertise reversal](https://doi.org/10.1207/S15326985EP3801_4)
  - [Renkl & Atkinson (2003), fading](https://doi.org/10.1023/A:1023053325971)
- **Self-explanation and concrete examples:** asking learners to explain why and connecting ideas to concrete cases can improve understanding and transfer.
  - [Weinstein, Sumeracki & Caviglioli (2018), learning-science overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC5780548/)
- **Feedback:** focus on the task, process, and self-regulation; make feedback specific and actionable rather than generically positive.
  - [Hattie & Timperley (2007)](https://doi.org/10.3102/003465430298487)
  - [Shute (2008)](https://doi.org/10.3102/0034654307313795)
- **Multimedia and cognitive load:** words plus relevant visuals can help; coherence, signaling, contiguity, and removal of extraneous detail matter.
  - [Mayer, multimedia learning principles](https://doi.org/10.1017/CBO9780511816819.013)
  - [Noetel et al. (2022), overview of reviews](https://doi.org/10.3102/00346543211052329)
- **Unassisted evidence:** assisted performance is not proof of independent capability. Include unsupported attempts and label the assistance used.
- **Self-regulation:** short plan → monitor → reflect prompts can improve strategy selection, but they should remain brief and voluntary.

## Community pattern provenance

### Matt Pocock `teach`

Reviewed: [mattpocock/skills — teach](https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/SKILL.md)

Adapted ideas:

- a mission that grounds every lesson;
- trusted, cited resources;
- a stateful learning record;
- selecting the next gap near the learner's current capability;
- tightly scoped optional interactive explanations.

Not adopted:

- mandatory HTML as the primary lesson unit;
- a shared asset site by default;
- one learning-record file per session;
- runtime dependency on the upstream skill.

### Education Agent Skills

Reviewed: [GarethManning/education-agent-skills](https://github.com/GarethManning/education-agent-skills)

Selected student-facing patterns:

- retrieve-first with a warm-start path;
- progressive hints with reflection before escalation;
- confidence calibration used selectively;
- conceptual/procedural/strategic/representational error diagnosis;
- near/far transfer checks;
- unassisted evidence after AI-supported practice;
- visible, reversible scaffold fading;
- brief self-regulated-learning session framing.

Selected design patterns:

- complementary dual coding rather than decorative imagery;
- cognitive-load and expertise-reversal checks;
- worked-example → completion → independent problem progression;
- feedback targeted to error type.

The repository declares CC BY-SA 4.0 in its README and states that its prompts have not themselves been empirically validated as AI interventions. This skill therefore cites the project, independently phrases selected methods, avoids copying its long prompts or exact scaffold thresholds, and verifies important claims against primary or review literature before teaching.

## Representation gate

Create a visual only when it conveys structure inefficiently expressed in prose. Match:

- sequence/process → flow or cycle;
- hierarchy → tree or nested structure;
- causality → labeled arrows;
- topology/spatial relation → diagram;
- dynamic state or simulation → self-contained interactive HTML;
- implementation skill → runnable code.

Keep related labels adjacent, use color semantically, reveal complexity progressively, and provide a text summary. Do not invoke “learning styles”; multimodal design is about complementary representations and cognitive load.

## Guardrails

- Do not mark material learned because it was displayed, explained, or completed with support.
- Do not require a cold recall attempt from a true novice.
- Do not withhold a direct explanation indefinitely; escalate support when effort stops being productive.
- Do not treat confidence ratings, hint levels, or fixed session counts as validated mastery thresholds.
- Do not let AI-generated evaluation outrank trusted sources or demonstrated real-world results.
- Do not create visuals or HTML merely to make a lesson look polished.
