# Palettes the user likes

The polished and modern mood: dashboards and status views the user watches. Calm pieces
(documents, reports, screens worked in) keep the blueprint-ink palette in `~/.agents/AGENTS.md`.

The user's taste, in their words (2026-11-12, choosing a theme for the AMC plan view):

- On calm, editorial and Swiss themes: "all of them are boring and not engaging".
- The mood wanted: "not boring like calm / confident; not playful. More polished and modern".
- Picked from eleven directions: "I like the Aurora Indigo, Metal dark, and Frost light".

Source of the tokens, the products each follows and their contrast ratios:
agent-mission-control `research/2026-11-12-themes-round-2.md`; working CSS in
`scripts/plan-view/page.css` there.

Rules that hold for all three:

- One colour marks what needs the user and is used for nothing else.
- The effect (glow, mesh, glass, gradient text) goes on the background, the hero and the selected
  item; charts, tables and body text stay solid and plain.
- Check text contrast (WCAG AA) over the brightest point of any gradient or glass behind it.

## Aurora Indigo (dark, the default for this mood)

Near-black page with an indigo-violet glow at the top, gradient-bordered cards, and a hero number in
a violet-to-cyan gradient. Follows Linear, Stripe and Radix's indigo and violet scales.

| Role | Value |
| --- | --- |
| Page | `#0b0c14` |
| Surface | `#141726` |
| Text, muted | `#edeef0`, `#a3a9c7` |
| Line, track | `#262b45`, `#1d2140` |
| Progress, soft | `#9eb1ff`, `#3a4f97` |
| Needs you (amber) | mark `#ffc53d`, text `#ffca16`, on `#302008` |
| Hero gradient | `#c4b5fd` → `#9eb1ff` → `#7dd3fc` |

Glow: radial gradients of `oklch(0.55 0.22 285 / 0.55)`, `oklch(0.60 0.17 255 / 0.45)` and
`oklch(0.72 0.12 215 / 0.22)` across the top, over a faint grain. Card border: a 160° gradient from
`oklch(0.72 0.15 285 / 0.55)` to `oklch(0.5 0.05 265 / 0.15)`.

## Metal (dark)

Black and graphite surfaces lit from the top, one iridescent serif number. Follows Resend's 2025
rebrand and Vercel Ship 2025.

| Role | Value |
| --- | --- |
| Page | `#000000` |
| Surface | `#141516` → `#0b0b0c` gradient, 1 px `#262a2d` ring, white inner top edge at 8% |
| Text, muted | `#f1efe9`, `#a1a4a5` |
| Progress | `#c9ccd1`; a second series in pale blue `#c8d6ff` so two lines never share a grey |
| Needs you (orange) | mark `#ff7a45`, text `#ff8f61`, on `rgb(255 122 69 / 0.14)` |
| Hero | serif (New York), gradient `#f1efe9` → `#c8d6ff` → `#f6c8ff` → `#fff1c8` → `#f1efe9` |

## Frost (light)

White frosted panes over a violet, cyan, pink and mint wallpaper. Follows Arc and Apple's glass.

| Role | Value |
| --- | --- |
| Page | `#f4eefc` under the wallpaper |
| Pane | `rgb(255 255 255 / 0.72)`, blur 24 px, saturate 180%, 1 px white border at 40% |
| Text, muted | `#1a1a1f`, `#54545a` |
| Progress, soft | `#6a3fe6`, `#d9ccff` |
| Needs you (red) | mark `#d93a3f`, text `#b42323`, on `#ffe2df` |
| Hero gradient | `#4b23c8` → `#1b6fd1` |
| Wallpaper glows | violet `#7f5af0` top left, cyan `#0db4f7` top right, pink `rgb(232 67 147 / 0.55)` bottom right, mint `#16f2b3` bottom left |

Keep pink and magenta away from whatever sits next to the needs-you red; in the plan view the pink
glow moved to the bottom corner for that reason.
