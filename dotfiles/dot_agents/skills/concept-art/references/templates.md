# Type templates

Append the default composition to every prompt:

> Clean composition with generous white space. Plain flat background. Main elements centered or positioned by content. Color hex values are rendering guidance only — do not display hex codes or palette names as visible text.

Fill `STYLE` and `COLORS` from a preset in [presets.md](presets.md).

## Infographic (conceptual)

For concept-level visual summaries only. Data values, charts, and tables go to `storytelling-viz` or `visual-explainer`.

```text
[Title] — concept infographic

Layout: [grid | radial | top-to-bottom | left-to-right]

ZONES:
- Zone 1: [concept + keyword]
- Zone 2: [comparison or step]
- Zone 3: [takeaway]

LABELS: short terms and phrases only — no data values or tables
COLORS: [preset palette, with semantic roles — e.g. orange=warning, green=success]
STYLE: [flat-editorial | sketchnote | blueprint | docs-mono]
ASPECT: 16:9
```

## Flowchart

```text
[Title] — process flow

Layout: [left-to-right | top-down | circular]

STEPS:
1. [Name] — [one line]
2. [Name] — [one line]

CONNECTIONS: [arrow style, decision diamonds if any]
STYLE: [flat-editorial with bold arrows | sketchnote]
ASPECT: 16:9
```

## Comparison

```text
[Title] — comparison

LEFT — [Option A]: [2–3 bullets as short labels]
RIGHT — [Option B]: [2–3 bullets as short labels]
DIVIDER: [vertical rule | VS badge | color split]
STYLE: [flat vector split layout]
ASPECT: 16:9
```

## Framework

```text
[Title] — conceptual framework

STRUCTURE: [hub-and-spoke | layers | matrix | pyramid]

NODES: [concept — role] × 3–6
RELATIONSHIPS: [how nodes connect]
STYLE: [geometric nodes, thick connectors]
ASPECT: 16:9
```

## Scene / editorial concept

```text
[Title] — atmospheric concept (not a literal screenshot)

FOCAL POINT: [single symbolic subject]
ATMOSPHERE: [lighting, mood, environment]
SUBTLE REFERENCE: [embed the topic as visual DNA, not a literal logo or text]
MOOD: [one emotion]
STYLE: [warm-editorial | riso-duo | paper-cut | iso-line]
ASPECT: 16:9, or 3:4 for a poster
```

## Hero / OG

```text
Create a [blog hero | OG card] for "[topic]".

Layout: landscape; copy-safe zone on the [left|right] third for an optional headline overlay.
Subject: [one metaphor aligned to the article opening — read the source file first].
Style: [match sibling assets in assets/ or public/static/, else a preset].
Colors: [brand hex or the preset palette].
Text: [exact quoted headline OR "no text"].
Constraints: no stock-photo aesthetic, no clip art, no watermarks.
```

## Icon / mascot

```text
App icon / mascot for [product/concept].

Subject: [recognizable as a solid silhouette at 64×64].
Style: flat geometric vector — not 3D vinyl, not photoreal — or the clay-mascot preset.
Colors: [2–3 colors + background, from a preset].
Constraints: no text, no fine detail that breaks at small size.
ASPECT: 1:1
```

## Prompt files

For 2+ illustrations or article work, save each prompt to `prompts/NN-{type}-{slug}.md` before generating, then render each one:

```yaml
---
illustration_id: 01
type: flowchart
preset: sketchnote
source: path/to/article.md
---

[Type template body…]
```
