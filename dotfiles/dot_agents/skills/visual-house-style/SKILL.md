---
name: visual-house-style
description: "House rules for anything visual someone will look at: decks, HTML pages and reports, infographics, diagrams, images and video. Audience approach (plain or metaphor-led), slide versus notes, numbers and baselines, honest charts, one meaning per encoding, neutral option comparisons, checking the render. Use when creating, restructuring or reviewing any of these, alongside the format skill."
---

# Visual house style

These rules hold for every format. The format skill (`pptx`, `visual-explainer`, `storytelling-viz`,
`concept-art`, `video-production`) says how to build the thing.

## Approach for the audience

- Offer the user two approaches and let them choose either or both:
  1. **Plain:** the audience's plain words, one term per concept, no metaphors for system parts.
  2. **Metaphor-led:** a metaphor carries the mechanism, with one mapping fixed in a legend and used
     on every panel, and the plain system diagram beneath each picture. Prose still names system
     parts plainly.
- For a mixed audience (non-technical people and architects), give each panel two layers: the
  picture with a one-line takeaway, then a small "For architects" strip of boxes and arrows.
- Prefer a metaphor the field already uses; a vendor drawing the same picture is evidence it
  carries. Catalogue: [references/metaphors.md](references/metaphors.md).

## Slide versus notes

- The slide carries the message and its evidence. Method, data sources, formulas, unit conversions, pricing basis, internal names, and control or comparison groups go in the speaker notes.
- One headline number per claim; at most one money figure per slide.
- Every headline number states what it measures, its unit and its baseline. When numbers on one slide use different baselines, put each baseline in its label.

## Order and placement

- Problem-first or answer-first are both fine; the one-line answer must be reachable from the first slide, in its title or its notes.
- A supporting metric goes on the slide whose claim it supports, never wherever there is space.

## Encodings

- One visual variable, one meaning, across the whole piece. If size means "batched" on one panel,
  nothing else is large anywhere: big trucks drawn as ordinary traffic read as batches.
- Draw separate things separately and the shared thing as what they stand on: two databases on one
  server are two roads on one bridge. Contention is strain through the shared structure, never
  traffic crossing from one road to the other.

## Comparing options for a decision

- Neutral unless asked to recommend: equal size and weight, the same rows for every option, status as
  an outline chip with a word rather than a red or green verdict, no ranking, no "recommended" badge.
- Split the durable from the disposable: the mechanism goes in a generic explainer that outlives the
  decision; the options and their status go in a proposals piece that expires once it is decided.

## Numbers on non-technical visuals

- Ask before putting numbers on a picture for a non-technical audience. Without them, show direction
  with unlabelled bars, such as a long bar against a short one for "time each write takes".
- Label an example number as illustrative and check it before drawing it. "100 at once at 150 ms,
  10 at once at 10 ms" is also a throughput claim: about 667 against 1,000 a second.

## Accuracy

- Draw only mechanisms that are verified. An unconfirmed detail stays off the picture and goes in
  the notes.
- A reassurance in a picture is a claim like any other. "Waiting in the queue, nothing lost" needed
  the queue's retention checked, and was wrong for a compacted topic.

## Honest charts

- Never raise a bar axis above zero to make a small share visible; use a separate panel with its own scale, a tighter top, or value labels.
- When one outlier would dominate a small chart: cap the axis at the normal range, draw break marks on the clipped bar, print its true value, explain it in the notes.
- When the point is a step change, draw each period's median as a labelled dashed line.
- A proxy is not the measure: a count of sampled intervals in which something happened is not how long it lasted. Use the measure the claim is about, or name the proxy.

## Before calling it done

- [ ] Rendered and looked at: a full-page screenshot, then a crop of each panel at the target size
      ([references/render-check.md](references/render-check.md)). No text clipped at a figure's edge.
- [ ] Every legend mapping holds on every panel; no visual variable means two things.
- [ ] Every slide fits without scrolling at the smallest target screen, and in dark mode if the host has one.
- [ ] Every number traces to a source named in the notes.
- [ ] Nothing on a slide needs the notes to be understood.
