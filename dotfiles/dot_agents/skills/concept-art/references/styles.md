# Styles, color, and references

## Style anchors

Name **one** style per prompt, not a stacked style list. Start from a preset in [presets.md](presets.md); each pairs a style sentence with a contrast-checked palette. Match sibling assets or brand tokens instead when the project has them.

Styles left out of the presets on purpose: duotone photo-collage (photoreal faces, stock-photo feel, stray logos) and soft watercolor (text bleeds, muddy colors).

## Anti-patterns

| Don't | Why |
|---|---|
| "8K, ultra detailed, masterpiece, trending on artstation" | Magic words; ignored or harmful |
| "professional, beautiful, premium, stunning" | Praise without spec — use observable details |
| Hex codes as visible labels | Models may paint "#A8D8EA" on the canvas |
| Literal metaphor (light bulb = "ideas") | Prefer structural visualization |
| Neon dashboard / purple gradient slop | Banned aesthetic |

## Color rules

- State 3–5 colors, with hex when possible, and give each a role (background, accent, emphasis). Outside a preset, check text contrast against its background (WCAG AA) and keep violet out.
- Add: *Color values are rendering guidance only — do not display hex codes or color names as visible text.*
- With human figures: *simplified stylized silhouettes, not photoreal faces.*
- With on-image text: *large, legible, short keywords; quote exact strings.*

## Reference images

| Usage | Action |
|---|---|
| Match composition | Pass in `reference_image_paths`; describe what to preserve |
| Palette only | Extract the colors into the prompt text; don't claim a file reference that doesn't exist |
| Style only | Describe the style in the prompt; reference image optional |

For edits and restyles: *Change ONLY [X]. Preserve the angle, palette, and all other elements.*
