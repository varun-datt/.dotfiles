---
name: video-production
description: "Manual-only. Make a short narrated explainer or demo film from code and finish it for a large screen: one timed script as the single source, an HTML/GSAP composition rendered with HyperFrames, real screenshots labelled beside drawn scenes, the presenter's own voice cut into per-line takes, a music bed generated in code and ducked under the voice, a loudness-matched master, verified 1080p and 4K exports, and an honest-claims review by another model family. Use only when the owner invokes it."
argument-hint: "<what the film is for, or the path to its project folder>"
disable-model-invocation: true
---

# Video production

A film here is code. One script file holds every scene's timing and every caption, an HTML page draws the scenes, and a renderer turns the page into frames. A change means editing the script or the page and re-running, never hand-editing a render or a mix.

## Defaults

The owner's, until a brief says otherwise.

- The presenter narrates in their own voice. Never clone or imitate a voice, theirs included; a local synthetic voice only stands in until the recording arrives.
- Captions say exactly what the recording says. When a take departs from the script, change the caption, not the audio.
- An upbeat music bed generated in code (no samples, nothing to license), 12 dB under the voice and ducked further while it speaks.
- Master to −14 LUFS integrated, −1 dBTP.
- For a large screen: 3840×2160, 30 fps, H.264 High. Keep a 1080p copy for sharing and review.
- The host deck's visual language when there is one, otherwise the Artifacts palette in `~/.agents/AGENTS.md`. Light stage. Fonts, icons and logos are local files.
- Real screenshots carry a label chip ("● Real session").
- Plain names before technical ones, one term per concept, and no count that will drift by the time it plays.

## Workflow

Each step ends at a gate. Don't polish past an open one.

1. **Brief.** Audience, slot length, where it plays (a deck slide, a projector, a Teams share), the one takeaway, what may appear on screen, who narrates. Keep the owner's rulings in one versioned list; each new ruling names what it supersedes.
2. **Single source.** `script.json` holds `version`, `durationSeconds`, `scenes` (`id`, `name`, `start`, `end`) and `captions` (`[start, end, text]`). The build derives every scene's timing from it and fails when scenes and markup disagree. Feedback names a scene id.
3. **Animatic before polish.** A silent timed draft first: review the story and the flow, then the motion. Snapshot single scenes for small changes; render the whole film before any release. See [composition.md](references/composition.md).
4. **Real evidence.** Screenshots of a real run, taken at the key beats, beat a screen recording: they are quicker to take, crop and re-time, and an agent run never repeats exactly. Show each one just after the drawn beat it proves. See [composition.md](references/composition.md#real-evidence).
5. **Voice.** Generate the read-aloud script from the captions, record every line in one sitting, cut each line from its last complete reading, process, and place each line at its caption without overlap. See [audio.md](references/audio.md).
6. **Music and master.** Generate the bed against the final narration, duck it, then master the mix. See [audio.md](references/audio.md#music-bed).
7. **Export and verify.** Encode, then assert the file instead of trusting the encoder. See [export-and-delivery.md](references/export-and-delivery.md).
8. **Review.** Frames and the timed script go to a reviewer from another model family. Grade each finding against the source before acting on it. The reviewer cannot hear the film: listen yourself, on speakers and on headphones. See [review.md](references/review.md).
9. **Deliver.** Embed it in the deck, play it on the presenting laptop through the room's output, and keep a standalone copy. See [export-and-delivery.md](references/export-and-delivery.md#delivery).

## Honesty rules

What a reviewer catches, and an audience does not forgive.

- Label what is real. A drawn screen that imitates a real tool, beside labelled screenshots, reads as captured: make it visibly schematic or label it as an illustration, and ask the owner which.
- Never present a deliberate check as an accident. If the run broke something on purpose to prove a test can fail, say so, or show a failure that really happened.
- A claim of enforcement ("the agent can't merge it") must be enforced by the system, not by an instruction. Check the setting first; for example, a branch policy that counts the pull request creator's own vote does not stop an agent that acts under its user's identity.
- Mark an expectation as an expectation, never as a measurement.
- End at the real state: "ready for review" never becomes "approved" or "merged" in a graphic.
- Keep counts consistent between drawn scenes and real stills; a drawn "3 files" beside a real "13 files" gets caught.
- Never manufacture a failure for drama, and never put an elapsed-time counter over edited footage.

## Gotchas

- **Transcribing a whole recording at once misleads.** Whisper drops a line read twice in a row, and it smears word times across a pause, so a false start and its restart read as one clean sentence and the false start ships. Transcribe each voiced island on its own, as `scripts/align_takes.py` does, and listen to every take it lists.
- **`hyperframes snapshot` sends frames to Gemini when `GEMINI_API_KEY` is set.** Pass `--describe false`, strip API keys from the renderer's environment, and set `HYPERFRAMES_NO_TELEMETRY=1`.
- **faster-whisper's own decoder can fail** on a PyAV version mismatch. Decode with ffmpeg to 16 kHz mono float32 and pass the array. Load models with `local_files_only=True` so nothing downloads mid-run.
- **The contrast check reports drawn text that a screenshot card covers.** Confirm the card is on top at that moment, then treat those warnings as false positives; never dismiss one you haven't looked at.
- **A still on screen for under 2 s can't be read.** Hold it, or drop it.
- **Teams screen share turns mostly-still animation choppy** unless the presenter presses Optimize; Include sound must be on before sharing.

## Files

| File | Use |
|---|---|
| [references/composition.md](references/composition.md) | HyperFrames contract and commands, real stills, capturing a real run, checks |
| [references/audio.md](references/audio.md) | Recording the presenter, takes, the voice chain, the synthetic stand-in, the music bed, the master |
| [references/export-and-delivery.md](references/export-and-delivery.md) | Encode presets, assertions, the deck, Teams, the play test |
| [references/review.md](references/review.md) | Review packet, reviewer prompt, grading findings |
| [scripts/align_takes.py](scripts/align_takes.py) | Find each line's last complete reading in a recording; list takes to listen to |
| [scripts/crop_stills.py](scripts/crop_stills.py) | Crop screenshots by fractions; cut a sprite out of its background |
| [scripts/music_bed.py](scripts/music_bed.py) | Generate the bed, duck it under the narration, mix |
| [scripts/master_export.py](scripts/master_export.py) | Loudness master, mux, encode a preset, assert the result |
| [scripts/review_packet.py](scripts/review_packet.py) | Frames and timed script for an outside reviewer |
