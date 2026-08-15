---
name: concept-art
description: >-
  Generate PNG concept illustrations using Cursor's built-in GenerateImage tool.
  Use when the user asks to illustrate, visualize, mock up, or draw a concept,
  metaphor, hero image, blog graphic, OG image, infographic PNG, flowchart image,
  or diagram-style raster. Triggers on: "illustrate", "concept art", "generate
  an image", "visualize this idea", "make a picture of", "hero image", "blog
  graphic", "infographic". Do NOT call external image APIs, MCP image servers,
  or shell scripts unless GenerateImage fails and the user explicitly opts in.
metadata:
  cursor-surfaces: [ide]
---

# Concept Art (Cursor GenerateImage)

Generate shareable PNG concept art with **Cursor's native `GenerateImage` tool** (Nano Banana Pro). No OpenAI, Replicate, or infsh credentials.

Patterns below are adapted from popular community skills — **pixeltamer**, **baoyu-article-illustrator**, **baoyu-infographic**, **anthropics/canvas-design**, **awesome-cursor-skills/generating-images**, **visual-explainer** — remapped for Cursor's built-in renderer.

## Prerequisites

- Cursor **2.4+**, Agent mode
- A **folder/workspace open** — GenerateImage fails in quick chat with no project loaded
- Create `assets/` (or match the project's existing image folder) before saving

## Workflow

0. **Route the request** — pick the closest recipe (below). Do not write prompts from scratch when a template fits.
1. **Gather context** — read sibling images, destination surface (MDX, README, landing component), and brand tokens before prompting (see [Context gathering](#context-gathering)).
2. **Clarify dimensions** — illustration **type**, **style anchor**, optional **palette**, aspect ratio, filename.
3. **Optional philosophy** — for poster/editorial/concept art, write 2–4 sentences of visual philosophy (form, color, rhythm) before the image prompt — inspired by **canvas-design**.
4. **Build the prompt** — use [Prompt structure](#prompt-structure) and the matching [Type template](#type-templates).
5. **Save prompt file** (recommended for articles or batches) — `prompts/NN-{type}-{slug}.md` with YAML frontmatter; never skip file save for multi-image article work (**baoyu** pattern).
6. **Call `GenerateImage`** — save under `assets/` with kebab-case name; pass reference images when available.
7. **Visual self-verify** — read the output PNG; judge against the prompt before claiming success (**pixeltamer** rule).
8. **Wire up** — if the image is for a blog, README, or component, update frontmatter/imports/metadata — do not only drop a file (**generating-images** rule).
9. **Iterate** — if wrong, change **one** dimension and regenerate; do not stack three new clauses (**pixeltamer** rule).

## Recipe router

| User intent | Route to | Default aspect |
|---|---|---|
| Blog hero / OG / social card | Hero concept template | landscape 16:9 |
| Abstract idea / metaphor | Scene or editorial-cover style | landscape |
| Process / steps / workflow | Flowchart template | landscape |
| Before/after, A vs B | Comparison template | landscape |
| Concept map / system parts | Framework template | landscape |
| Data + labels in one PNG | Infographic template | 16:9 |
| App icon / mascot | Icon template (flat vector) | square |
| Magazine/poster art object | Philosophy + minimal text | portrait or square |
| Dense table / architecture doc | **Stop** — use `visual-explainer` (HTML) instead | — |

## Prompt structure

Use labeled sections in this order (adapted from **pixeltamer** + **baoyu**):

```text
INTENT: [one line — blog hero, concept infographic, app icon, editorial poster…]

LAYOUT: [zones, flow direction, negative space — layout first, per baoyu]

SUBJECT: [concrete metaphor; avoid literal clip-art of the topic name]

DETAILS: [icons, relationships, 2–4 key labels if text requested]

TEXT (optional): [exact quoted strings only; specify size/position; or "no text"]

STYLE: [one named anchor — flat vector à la Stripe, isometric line art, sketchnote, screen-print…]

COLORS: [3–5 hex codes or palette name; see color rules]

LIGHTING: [single direction + temperature, if relevant]

CONSTRAINTS: [explicit negatives — no watermarks, no extra labels, no neon slop…]

ASPECT: [16:9 | 1:1 | 9:16 | 5:3]
```

**Opening weight:** lead with **subject + layout** in the first ~50 words. Do not open with meta labels like "INTENT:" in the string passed to `GenerateImage` — use them while composing, then merge into flowing prose for the tool call.

### Anti-patterns (drop these)

| Don't | Why |
|---|---|
| "8K, ultra detailed, masterpiece, trending on artstation" | Magic words; ignored or harmful (**pixeltamer**) |
| "professional, beautiful, premium, stunning" | Praise without spec — use observable details |
| Hex codes as visible labels | Models may paint "#A8D8EA" on canvas (**baoyu**) |
| Literal metaphor (light bulb = "ideas") | Prefer structural visualization (**baoyu**) |
| Neon dashboard / purple gradient slop | Banned aesthetic (**visual-explainer**) |

Replace praise with spec: not "cute mascot" → "kind expression, head tilt 5° left, readable at 64×64 silhouette."

## Type templates

Append **default composition** to every prompt (**baoyu**):

> Clean composition with generous white space. Simple or subtle gradient background only. Main elements centered or positioned by content. Color hex values are rendering guidance only — do not display hex codes or palette names as visible text.

### Infographic (PNG)

```text
[Title] — data or concept infographic

Layout: [grid | radial | top-to-bottom | left-to-right]

ZONES:
- Zone 1: [concept + optional metric/keyword]
- Zone 2: [comparison or step]
- Zone 3: [takeaway]

LABELS: [article-specific terms, numbers, short phrases only]
COLORS: [semantic mapping — coral=warning, mint=success]
STYLE: [flat vector | hand-drawn sketchnote | technical-schematic]
ASPECT: 16:9
```

**Sketchnote preset** (pastel article graphics): warm cream background, black hand-drawn lines with slight wobble, soft macaron fills (blue/mint/lavender/peach), rounded info boxes, hand-lettered keywords, generous margins.

### Flowchart

```text
[Title] — process flow

Layout: [left-to-right | top-down | circular]

STEPS:
1. [Name] — [one line]
2. [Name] — [one line]

CONNECTIONS: [arrow style, decision diamonds if any]
STYLE: [flat vector with bold arrows | ink sketchnote]
ASPECT: 16:9
```

### Comparison

```text
[Title] — comparison

LEFT — [Option A]: [2–3 bullets as short labels]
RIGHT — [Option B]: [2–3 bullets as short labels]
DIVIDER: [vertical rule | VS badge | color split]
STYLE: [flat vector split layout]
ASPECT: 16:9
```

### Framework

```text
[Title] — conceptual framework

STRUCTURE: [hub-and-spoke | layers | matrix | pyramid]

NODES: [concept — role] × 3–6
RELATIONSHIPS: [how nodes connect]
STYLE: [geometric nodes, thick connectors]
ASPECT: 16:9
```

### Scene / editorial concept

```text
[Title] — atmospheric concept (not literal screenshot)

FOCAL POINT: [single symbolic subject]
ATMOSPHERE: [lighting, mood, environment]
SUBTLE REFERENCE: [embed topic as sophisticated visual DNA, not literal logo/text — canvas-design]
MOOD: [one emotion]
STYLE: [editorial collage | screen-print | isometric]
ASPECT: 16:9 or 2:3
```

**Screen-print override:** flat color blocks, 2–5 colors max, halftone texture, silhouettes not photoreal faces, bold negative space.

### Hero / OG

```text
Create a [blog hero | OG card] for "[topic]".

Layout: landscape; copy-safe zone on [left|right] third for optional headline overlay.
Subject: [one metaphor aligned to article opening — read source file first].
Style: [match sibling assets in assets/ or public/static/].
Colors: [brand hex or Catppuccin pastels from theme-factory].
Text: [exact quoted headline OR "no text"].
Constraints: no stock-photo aesthetic, no clip art, no watermarks.
```

### Icon / mascot

```text
App icon / mascot for [product/concept].

Subject: [recognizable in solid silhouette at 64×64].
Style: flat geometric vector — not 3D vinyl, not photoreal (**pixeltamer** context matrix).
Colors: [2–3 colors + background].
Constraints: no text, no fine detail that breaks at small size.
ASPECT: 1:1
```

## Style anchors (pick one)

| Context | Reach for | Avoid |
|---|---|---|
| SaaS / tech blog | Flat editorial (Stripe, Linear, Notion marketing) | chibi, photoreal |
| Pastel / personal brand | Macaron sketchnote, Catppuccin soft blocks | neon cyberpunk |
| Architecture concept | Isometric line art, blueprint schematic | busy 3D renders |
| Editorial poster | Screen-print, Saul Bass, risograph two-color | generic stock cover |
| Children's / friendly | Soft watercolor, simple shapes | corporate flat only |

Name **one** reference per prompt — not a stacked style list.

## Context gathering

Before generating (unless the user gave full spec):

1. **Sibling assets** — read 1–2 existing images in `assets/`, `public/static/`, etc.; match style, palette, aspect ratio.
2. **Destination surface** — read the blog MDX, README, or component the image will accompany; pull metaphors from content, not filename alone.
3. **Brand tokens** — check CSS variables, `tailwind.config`, chezmoi Catppuccin palette, or invoke **`theme-factory`** for hex values.
4. **Infer first** — only ask when two equally valid styles exist in the project.

## Color rules

- State **3–5 colors** with hex when possible; semantic roles (background, accent, emphasis).
- Add: *Color values are rendering guidance only — do not display hex codes or color names as visible text.*
- With human figures: *simplified stylized silhouettes, not photoreal faces* (**baoyu**).
- With on-image text: *large, legible, short keywords; quote exact strings* (**pixeltamer**).

## Reference images

When the user attaches files or `assets/` has references:

| Usage | Action |
|---|---|
| Match composition | Pass as reference to `GenerateImage`; describe what to preserve |
| Palette only | Extract colors in prompt text; do not claim a file reference that does not exist |
| Style only | Describe style in prompt; optional reference image |

For edits/restyles: *Change ONLY [X]. Preserve angle, palette, and all other elements.*

## Prompt files (articles & batches)

For 2+ illustrations or article work:

```yaml
---
illustration_id: 01
type: flowchart
style: sketchnote
palette: macaron
source: path/to/article.md
---

[Type template body…]
```

Save to `prompts/NN-{type}-{slug}.md`, then render each via `GenerateImage`. Pair with **`baoyu-article-illustrator`** / **`baoyu-infographic`** for placement analysis; use **this skill** for the render step.

## Visual self-verification

After every generation, **read the PNG** and check:

- Subject matches the metaphor (not generic stock scene)
- Text spelled exactly as quoted (if any)
- No accidental hex/palette labels painted on canvas
- Composition matches requested layout and aspect
- No obvious artifacts (warped type, extra limbs, cluttered background)

If wrong: report honestly, suggest **one** fix, offer to regenerate — do not claim success when the image misses the brief.

## Iteration (change one dimension)

| If the result is… | Change only… |
|---|---|
| Wrong vibe | Style anchor |
| Too generic | Composition / camera / layout |
| Cluttered | Remove elements; add negative space |
| Off-brand color | Hex palette |
| Wrong text | Re-quote exact string + "no extra characters" |
| Too literal | Shift to structural/symbolic template |

## Aspect ratio guide

| Use case | Shape |
|---|---|
| Blog hero / OG / landscape concept | wide landscape (~16:9 or 5:3) |
| Social portrait / mobile | tall portrait (~9:16) |
| Icon / avatar | square (1:1) |
| Slide background | 16:9 landscape |
| Editorial poster | 2:3 portrait |

## Filename conventions

- `assets/concept-<topic>.png` — general concept art
- `assets/hero-<slug>.png` — blog or landing hero
- `assets/og-<slug>.png` — social preview
- `assets/infographic-<slug>.png` — full-page infographic PNG
- Match existing `assets/` naming if present

## Failure handling

| Symptom | Action |
|---|---|
| No workspace open | Ask user to open a folder, then retry |
| Tool timeout / 429 | Wait briefly, retry once with a simpler prompt |
| Wrong but close | One-dimension iteration |
| Still failing | Offer `visual-explainer` (HTML) or diagram skills; external APIs only if user opts in |

## Copilot / non-Cursor agents

`GenerateImage` is **Cursor-only**. On GitHub Copilot, use `mermaid-diagrams`, `visual-explainer`, or `frontend-design` instead.

## Pairing

| Need | Skill |
|---|---|
| Article placement + outline | `baoyu-article-illustrator`, `baoyu-infographic` |
| Render baoyu prompt files | **this skill** (`GenerateImage`) |
| HTML instead of PNG | `visual-explainer` + `frontend-design` |
| Themed HTML/CSS | `theme-factory` + `frontend-design` |
| Editable vector diagram | `baoyu-diagram`, `mermaid-diagrams` |

## References & lineage

Community skills this workflow borrows from (install separately if needed):

| Skill | Repo | What we adapted |
|---|---|---|
| pixeltamer | `gabelul/pixeltamer-gpt-image-skill` | Prompt structure, anti-patterns, self-verify, iteration, style/context matrix |
| baoyu-article-illustrator | `jimliu/baoyu-skills` | Type × Style × Palette, zone templates, prompt files, color/text rules |
| baoyu-infographic | `jimliu/baoyu-skills` | Layout × style thinking for PNG infographics |
| canvas-design | `anthropics/skills` | Visual philosophy, subtle reference, minimal text as design |
| generating-images | `spencerpauly/awesome-cursor-skills` | Context gathering, sibling matching, wire-up after save |
| visual-explainer | `nicobailon/visual-explainer` | When to prefer HTML over raster; anti-slop aesthetics |
