---
name: concept-art
description: "Generate raster concept illustrations with an image tool (Cursor GenerateImage, an image extension or MCP server) when the user explicitly asks for an image: concept art, metaphors, hero or OG images, blog graphics, app icons, mascots, posters. With no image tool, say so and fall back to HTML or SVG. Not for charts or data visuals. Never install an image tool or call an image API from the shell."
metadata:
  cursor-surfaces: [ide]
---

# Concept Art

Generate shareable concept art with an image tool the agent already has. The prompts, presets, and verification steps work with any modern image model.

## Prerequisites

- **Detect the image tool first.** Look in your tool list for one that generates images:
  - Cursor: `GenerateImage` (Cursor 2.4+, Agent mode, a folder open — it fails in a quick chat with no project loaded).
  - GitHub Copilot and others: none built in. Use an image extension (for example ImageGen's `#generateImage`) or an image MCP server (`generate_image`) only if the user has already set one up.
- **No tool:** say so, and offer `visual-explainer` (HTML), `baoyu-diagram` (SVG), or `mermaid-diagrams`, carrying over the chosen preset's palette and its text pairings (which color text may sit on which fill). Never substitute SVG or HTML without saying so, and never install a tool, add an API key, or call an image API through the shell yourself.
- **Third-party tools send the prompt to an outside API** (Google, OpenAI, or another provider) on the user's own key. Before sending internal architecture or product names that way, confirm the user is allowed to.

## Workflow

0. **Route the request** with the [recipe router](#recipe-router), then start from the matching template in [references/templates.md](references/templates.md). Don't write a prompt from scratch when a template fits.
1. **Gather context** — see [Context gathering](#context-gathering).
2. **Settle the brief** — illustration type, one [preset](references/presets.md) (style + palette), aspect ratio, filename. There is no default preset. If the user didn't fix these, propose 2–3 combinations (type × preset × aspect) and wait for a pick. Skip this when the brief is complete or the user asks to generate directly, and state the assumed choices.
3. **Optional philosophy** — for poster, editorial, or concept art, write 2–4 sentences of visual philosophy (form, color, rhythm) before the prompt.
4. **Build the prompt** with [Prompt structure](#prompt-structure) and the type template. Style anchors, color rules, and anti-patterns are in [references/styles.md](references/styles.md).
5. **Save a prompt file** for article work or batches of 2+ images — see [prompt files](references/templates.md#prompt-files).
6. **Call the tool** — use a kebab-case name (`concept-<topic>`, `hero-<slug>`, `og-<slug>`, `icon-<name>`, or the project's existing naming) and pass reference images when the tool takes them.
   - Cursor `GenerateImage`: set `aspect_ratio` explicitly, pass a bare `filename` with no directory, and put reference images in `reference_image_paths`.
   - Other tools: map the aspect ratio to the tool's size or ratio options, with the closest match when it offers only fixed sizes. If the tool rewrites prompts, turn that off when it allows, so the preset wording reaches the model unchanged.
7. **Move the file** from the path the tool returns into `assets/` or the project's image folder, creating it if missing. Tools save in their own places and formats: Cursor saves under `~/.cursor/projects/<workspace>/assets/` and may write a JPEG whatever extension you asked for, and others write WebP or into a hidden folder. Convert (`sips -s format png` on macOS) when the destination needs a specific format. If a file with that name already exists, use a new name (`-v2`) instead of overwriting.
8. **Self-verify** — read the image and check it against [Verification](#verification) before claiming success.
9. **Wire up** — if the image is for a blog, README, or component, update its frontmatter, imports, or metadata; don't just drop a file.
10. **Iterate** — change one dimension per regeneration ([references/iteration.md](references/iteration.md)).

## Recipe router

| User intent | Route to | Aspect |
|---|---|---|
| Blog hero / OG / social card | Hero template | 16:9 |
| Abstract idea / metaphor | Scene or editorial template | 16:9 |
| Process / steps (concept level) | Flowchart template | 16:9 |
| Before/after, A vs B | Comparison template | 16:9 |
| Concept map / system parts | Framework template | 16:9 |
| Architecture overview (≤8 components, short labels) | Framework template + `soft-3d` or `iso-line` | 16:9 |
| Conceptual infographic (few labels, no data values) | Infographic template | 16:9 |
| App icon / mascot | Icon template | 1:1 |
| Poster / editorial art object | Philosophy + scene template, minimal text | 3:4 or 1:1 |
| Charts, plots, tables, data values | **Stop** — `storytelling-viz` (Plotly) or `visual-explainer` | — |
| Dense architecture or reference doc | **Stop** — `visual-explainer` (HTML) | — |

Cursor GenerateImage accepts only `1:1`, `4:3`, `3:4`, `16:9`, and `9:16`. Use `9:16` for mobile or social portrait.

## Prompt structure

Compose with these labeled sections, then merge them into flowing prose for the tool call. Lead with subject and layout in the first ~50 words; don't open the tool string with a label like "INTENT:".

```text
INTENT: one line — blog hero, concept infographic, app icon, editorial poster…
LAYOUT: zones, flow direction, negative space (layout first)
SUBJECT: concrete metaphor; avoid literal clip-art of the topic name
DETAILS: icons, relationships, 2–4 key labels if text is requested
TEXT (optional): exact quoted strings with size and position, or "no text"
STYLE: one preset's style sentence
COLORS: the preset's 3–5 hex codes with roles
LIGHTING: one direction and temperature, if relevant
CONSTRAINTS: explicit negatives — no watermarks, no extra labels, no hex codes as text
```

Replace praise with spec: not "cute mascot" but "kind expression, head tilted 5° left, readable as a silhouette at 64×64".

## Context gathering

Unless the user gave a full spec:

1. **Sibling assets** — read 1–2 existing images in `assets/`, `public/`, or `static/`; match their style, palette, and aspect.
2. **Destination** — read the MDX, README, or component the image accompanies; take the metaphor from its content, not the filename.
3. **Brand tokens** — CSS variables or `tailwind.config`; with none, use a preset palette.

## Rules

- **Sensitive data** — never render credentials, tokens, internal hostnames, or customer or patient identifiers as on-image text; use placeholders.
- **Vendor logos** — image models redraw logos approximately (AWS, Kubernetes, Spring, and so on). Use generic icons; when exact logos matter, build it in `visual-explainer` with the official SVGs instead.
- **Long names** — model text garbles past a word or two; keep labels short, and shorten long service names (`data-service`) rather than quoting them whole.
- **No text patching** — never fix rendered text with Pillow, ImageMagick, SVG, or HTML overlays. Regenerate from a corrected prompt under a new filename and keep the flawed candidate for comparison. Post-processing is limited to crop, resize, compression, or format conversion.
- **Honest results** — if the image misses the brief, say so, suggest one fix, and offer to regenerate.

## Verification

After every generation, read the image and check that:

- the subject matches the metaphor, not a generic stock scene;
- text is spelled exactly as quoted, with no extra characters;
- no hex codes or palette names are painted on the canvas;
- the composition matches the requested layout and aspect;
- there are no obvious artifacts (warped type, extra limbs, cluttered background).

## Failure handling

| Symptom | Action |
|---|---|
| No workspace open (Cursor) | Ask the user to open a folder, then retry |
| Timeout / 429 | Wait briefly, retry once with a simpler prompt |
| Wrong but close | One-dimension iteration |
| Still failing | Offer `visual-explainer` (HTML) or a diagram skill |

## Pairing

| Need | Skill |
|---|---|
| HTML instead of PNG | `visual-explainer` + `frontend-design` |
| Editable vector diagram | `baoyu-diagram`, `mermaid-diagrams` |
| Data chart | `storytelling-viz` |

Where these patterns come from: [references/lineage.md](references/lineage.md).
