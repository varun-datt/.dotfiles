# Style + palette presets

Pick one preset per image; there is no default. When the brief doesn't name one, offer 2–3 that fit the "Best for" column. Paste the style sentence into STYLE and the palette roles into COLORS.

Every preset's ink-on-background pair is at least 7:1 (WCAG AAA). Text uses only the ink color or the listed reverse pairs. Colors marked **fill only** are below 3:1 against the background: use them as fills with an ink outline or ink text on top, never as lines or text.

Append to every preset prompt:

> Flat solid fills, no gradients. Color values are rendering guidance only — do not display hex codes or color names as text. Render only the quoted words, in [type style]; no other text.

If renders drift from the hex values, name each color in words next to its hex ("deep blueprint blue `#054980`"), or pass a palette swatch image in `reference_image_paths`.

## Overview

| Preset | Best for | Avoid for | Text on image | Aspect |
|---|---|---|---|---|
| `iso-line` | Cloud and Kubernetes topology, architecture heroes | Dense labeled diagrams, people | Good, on flat front-facing tags | 16:9, 4:3 |
| `iso-block` | Friendly platform overviews, README banners | Text-heavy slides | Short labels only | 16:9, 1:1 |
| `blueprint` | System internals, design docs, "how it works" | Playful posts | Title + ≤6 short labels | 16:9, 4:3 |
| `flat-editorial` | Blog heroes, OG cards, slide illustrations | Pastel or personal posts | Very good | 16:9, 1:1 |
| `sketchnote` | Talk summaries, concept explainers, onboarding | Formal or regulatory docs | ≤5 quoted labels | 4:3, 16:9 |
| `riso-duo` | Editorial posters, essay covers, event art | Anything needing several labels | One headline | 3:4, 1:1 |
| `docs-mono` | Docs, READMEs, wikis, medical-device docs (survives grayscale print) | Marketing heroes | Very good | 16:9, 4:3 |
| `docs-dark` | Dark-mode docs, terminal and dev-tool posts | Print, light pages | Good | 16:9, 4:3 |
| `warm-editorial` | Long-form essays, newsletters, personal-brand heroes | Bright SaaS launches | Good | 16:9, 3:4 |
| `paper-cut` | Layer, stack, and depth metaphors | Labeled diagrams | Keep off, or one flat label | 16:9, 1:1 |
| `clay-mascot` | App icons, mascots, agent characters | Anything with text, serious medical topics | None | 1:1 |
| `swiss-grid` | Title slides, typographic posters, quote cards | Soft topics, clinical-alarm-adjacent content | Very good | 16:9, 3:4, 9:16 |
| `soft-3d` | Architecture overviews and platform slides with a few components | Dense diagrams, exact vendor logos | Good for short labels on cards | 16:9, 4:3 |

For text-heavy images prefer `swiss-grid`, `flat-editorial`, or `docs-mono`. Textured styles (`riso-duo`, `paper-cut`, `clay-mascot`) misspell more; keep text off them.

## Presets

### `iso-line`

- **Style:** "A flat isometric line illustration at a true 30° axonometric angle, single uniform dark line weight, flat solid fills, no shading or perspective, with labels on small front-facing tags."
- **Colors:** background `#f7f5f0` warm off-white · primary `#054980` blueprint blue · accent `#e69f00` orange (fill only) · accent2 `#009e73` bluish green · ink `#1b2430`.
- **Text:** ink on background; white on blueprint blue; ink on orange tags.
- **Drift:** bare "isometric" pulls toward glossy 3D miniatures — keep "flat" and "no shading" in the prompt.

### `iso-block`

- **Style:** "Isometric flat-shaded blocks with three flat tones per face (top lightest), crisp edges, matte solid colors, on a plain light background, with labels on small flat tags beside the blocks."
- **Colors (Catppuccin Latte):** background `#eff1f5` · primary `#1e66f5` blue · accent `#fe640b` peach · accent2 `#179299` teal · ink `#4c4f69`.
- **Text:** ink on background; white on blue; ink, not white, on teal.
- **Drift:** glossy or glassmorphism surfaces; labels painted skewed onto block faces.

### `blueprint`

- **Style:** "A technical blueprint drawing: thin pale blue-white lines (not cyan) on a solid deep blueprint-blue ground, faint square grid, precise orthographic geometry, one warm gold highlight on the key component."
- **Colors:** background `#054980` blueprint blue · lines `#dbe7f3` pale blue-white · accent `#f2b049` light gold · ink `#ffffff`.
- **Text:** white or gold on the blue ground.
- **Drift:** "blueprint" alone defaults to cyan on navy; the model also invents dimension numbers and gibberish annotations — say "no dimension numbers".

### `flat-editorial`

- **Style:** "A flat editorial vector illustration in the style of modern tech-company marketing art: geometric shapes, solid fills, generous white space, one bold focal object."
- **Colors (IBM Carbon + Okabe-Ito):** background `#ffffff` · primary `#0f62fe` blue · accent `#007d79` teal · accent2 `#e69f00` orange (fill only) · ink `#161616`.
- **Text:** ink on background; white on blue or teal; ink on orange.
- **Drift:** without the named palette the model falls back to violet SaaS gradients; generic "corporate Memphis" people.

### `sketchnote`

- **Style:** "A hand-drawn sketchnote on warm paper: black fineliner outlines, neat hand-lettered capitals, simple icons, arrows and boxes, flat marker fills in three accent colors."
- **Colors (Okabe-Ito, colorblind-safe):** background `#fbf7ee` warm paper · primary `#0072b2` blue · accent `#d55e00` vermillion (fill only) · accent2 `#009e73` bluish green (fill only) · ink `#222222`.
- **Text:** ink on background; blue for a heading; white on blue.
- **Drift:** misspelled pseudo-handwriting; too much text; random doodles.

### `riso-duo`

- **Style:** "A two-ink risograph print on cream paper: flat shapes in deep teal and red-orange only, controlled halftone in shadows, subtle 1 mm misregistration, overlap printing a dark third tone."
- **Colors:** background `#f3ede1` cream · ink 1 and text `#0b5563` deep teal · ink 2 `#e4572e` red-orange.
- **Text:** teal on cream; cream knocked out of teal. Never put text over the red-orange.
- **Drift:** looks like a filter; heavy misregistration; extra inks.

### `docs-mono`

- **Style:** "A clean monoline diagram illustration: one uniform medium stroke weight, rounded line caps, near-black on white, gray secondary elements, one blue accent for the single most important element."
- **Colors (IBM Carbon):** background `#ffffff` · secondary lines `#525252` gray · accent `#0f62fe` blue · ink `#161616`.
- **Text:** ink or gray on white; blue for one emphasized label.
- **Drift:** lines too thin to survive downscaling; gray-on-gray low contrast.

### `docs-dark`

- **Style:** "A clean monoline diagram on a near-black neutral background: one uniform stroke weight in light gray, pastel blue and peach highlights, matte and calm."
- **Colors:** background `#161616` · primary `#89b4fa` pastel blue · accent `#fab387` peach · accent2 `#a6e3a1` green · ink `#f4f4f4`.
- **Text:** ink on background; `#161616` on the pastel chips.
- **Drift:** neon glow — keep cyans and teals out, and say "matte, no glow".

### `warm-editorial`

- **Style:** "A warm editorial illustration like a print magazine feature: confident flat shapes, subtle paper grain, deep blueprint-blue forms with a single gold highlight, lots of cream negative space."
- **Colors (brand):** background `#f6f1e7` cream · primary `#054980` blueprint blue · accent `#ce7616` editorial gold (fill only) · accent2 `#8c3b2a` brick · ink `#1f1a14`.
- **Text:** ink on cream; cream on blueprint blue; ink on gold; brick for a kicker line.
- **Drift:** paper grain overdone into a dirty texture.

### `paper-cut`

- **Style:** "A layered paper-cut illustration: stacked matte cardstock layers in tonal teals with one amber layer, clean cut edges and soft short drop shadows, viewed straight on, flat even lighting."
- **Colors:** background `#f2efe9` · primary `#007d79` teal · accent `#df8e1d` amber (fill only) · accent2 `#9ef0f0` pale aqua (fill only) · ink `#081a1c`.
- **Text:** avoid; if needed, ink on pale aqua or white on teal.
- **Drift:** turns into a blurry craft photo; heavy shadows; misspelled cut-out letters.

### `clay-mascot`

- **Style:** "A soft clay-style 3D render of a single character: rounded matte forms, subtle fingerprint texture, gentle soft studio light, plain light background, centered with margin."
- **Colors:** background `#eff1f5` · body `#fab387` peach (fill only) · accent `#179299` teal · accent2 `#f9e2af` pale yellow (fill only) · ink `#4c4f69` for features and contour.
- **Text:** none; put the name in the layout instead.
- **Drift:** chibi or blind-box toy; glossy plastic. The light body needs a teal or ink contour to separate from the background.

### `swiss-grid`

- **Style:** "A Swiss International Style poster: strict modular grid, bold grotesque sans-serif headline set flush-left, primary geometric shapes in red, blue and yellow on off-white, ample white space."
- **Colors:** background `#f4f1ea` off-white · primary `#d20f39` red · accent `#002d9c` deep blue · accent2 `#f5c710` amber (fill only) · ink `#111111`.
- **Text:** ink or red on background; white on red or blue; ink on amber.
- **Drift:** invented filler text — say "no other text"; random extra shapes.

### `soft-3d`

- **Style:** "A soft 3D product-diagram illustration: rounded white cards and frosted translucent panels with soft drop shadows, small glossy isometric 3D icons, thin connector arrows, clean sans-serif labels on the cards, bright and airy."
- **Colors:** background `#f4f6fa` cool off-white · panels `#e4ecf7` frosted pale blue (fill only) · primary `#3567b5` soft blue · accent `#f4a261` peach (fill only) · accent2 `#2a9d8f` teal (fill only) · ink `#1b2a3d`.
- **Text:** ink on the background, cards, or panels; white on soft blue; ink on peach. No text on teal.
- **Exception:** soft shading on the icons and translucency on the panels are part of the look; replace the shared suffix's "Flat solid fills, no gradients" with "No color gradients or gradient backgrounds".
- **Drift:** lavender or periwinkle creeps in — say "no purple or lavender tints"; vendor logos get redrawn approximately — ask for generic icons.
