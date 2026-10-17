# Composition and rendering

## HyperFrames

HyperFrames (`heygen-com/hyperframes`, Apache-2.0) renders an HTML page driven by a seekable GSAP timeline to video, with headless Chrome and FFmpeg, on this machine. Pin it in `package.json` and install with `npm ci`; version 0.8.156 rendered a 3½-minute film at 1080p and 4K. GSAP is under its own standard licence; keep that line in the asset notices.

The contract the renderer expects:

- A root element `<div data-composition-id="<id>" data-start="0" data-duration="<seconds>" data-width="1920" data-height="1080">`.
- Each scene is a clip inside it with `data-start`, `data-duration` and `data-track-index`.
- One paused GSAP timeline, `gsap.timeline({ paused: true })`, registered as `window.__timelines['<id>']`. Everything moves on that timeline. CSS transitions, `setTimeout` and anything driven by the wall clock cannot be seeked, so they render wrong.

The build step generates the page from `script.json`: it fills each scene's start and duration, inlines local fonts (`@fontsource/*`), icons (`lucide-static`) and logos (`devicon`), and writes `asset-notices.txt` with each font and icon licence, the logo trademark line and the renderer and animation licences. It refuses to build when the scene ids in the script and the markup differ.

Commands, from the project folder, with `HYPERFRAMES_NO_TELEMETRY=1` and with `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `HEYGEN_API_KEY` removed from the environment:

```sh
hyperframes check <dir> --json            # lint, runtime errors, layout overflow, motion, WCAG AA contrast
hyperframes snapshot <dir> --at 9,30,76 --no-end --describe false --output frames/
hyperframes render <dir> --quality draft --fps 30 --workers 4 --output draft.mp4
hyperframes render <dir> --quality delivery --resolution 4k --fps 30 --workers 4 --output master-4k.mp4
```

- `check` exits non-zero on errors only (`--strict` adds warnings); read every warning anyway.
- `--quality` is `draft`, `looks` (the default, CRF 16) or `delivery`. Render the 4K master from the page itself: it renders at twice the pixel density, so text and vectors stay sharp instead of being upscaled.
- These films put no audio element in the page, so the render is silent and the soundtrack is muxed afterwards (`scripts/master_export.py`).
- Snapshots are stills. They can't show pacing, dropped frames or sync; watch the continuous cut too.

## Motion

- Calm: crossfades, one deliberate camera move where it earns it. No shakes, whips, flashes or punch zooms.
- Build two variants from one source, switched by a flag such as `window.__MOTION`: the motion build is the main file, and a fades-only build is the fallback if a screen share stutters.
- Pictures follow the words. Anchor each highlight to its caption's start time, or to a word timestamp when you have them, and hold a question or a decisive result until it can be read.
- Position highlight boxes from measurements (fractions of the still, or the element's own rectangle), never by eye.

## Real evidence

### Capturing a real run

- Record in a dedicated VS Code profile: Light theme; editor 18 px, terminal 16 px, chat 16 px; only the extensions and MCP servers the demo needs; no personal instructions, skills or hooks, so the run reads only the repository's own agent files; a window title without the profile name.
- Do Not Disturb on, chat and mail apps closed, one display, desktop hidden.
- No secrets on screen: no tokens in terminal history, environment dumps or CLI output.
- An agent never repeats a run exactly, so a rehearsal you captured can be the real run. Take screenshots at each beat as it happens.
- Sweep every frame for secrets and personal data before anything leaves the machine.

### Stills in the film

`scripts/crop_stills.py` crops each screenshot by a box given as fractions of the image, so a retina and a standard capture crop alike, and caps the width at 2000 px. A sprite (a mascot, a logo on a flat background) is cut out by clearing only the background connected to the image's edges, so dark details inside it survive.

Place each still as a card: a label chip, an optional scrim behind it so drawn text underneath doesn't show through, and an optional highlight rectangle on the line that proves the beat. Show it just after the drawn beat it backs, so the explanation stays and the still confirms it.

## Review pages

A review page beside the draft lets the owner jump to a named scene, read its narration and leave notes without replaying the film. It opens from disk with no server, and notes stay in the browser and export as text.
