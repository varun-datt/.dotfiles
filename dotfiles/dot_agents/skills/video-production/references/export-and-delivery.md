# Export, verification and delivery

## Presets

`scripts/master_export.py` masters the soundtrack, muxes it with the silent render and encodes one of two presets:

| Preset | Video | Audio | Use |
|---|---|---|---|
| `share` | `libx264 -preset slow -tune animation -crf 22 -profile:v high -pix_fmt yuv420p`, scaled to 1080 lines if the source is taller | AAC 160 kbps, 48 kHz, stereo | Review rounds, chat, mail: small, starts playing before the download ends |
| `4k` | `libx264 -preset slow -tune animation -crf 14 -maxrate 50M -bufsize 100M -profile:v high -level:v 5.1 -pix_fmt yuv420p`, BT.709 primaries, transfer and matrix, TV range | AAC 320 kbps, 48 kHz, stereo | The large screen. High@5.1 with BT.709 tags plays in PowerPoint and venue players, and the bitrate cap keeps a laptop's decoder smooth |

Both use `-movflags +faststart`. The `4k` preset requires a 3840×2160 render; it never upscales.

Next to the MP4 it writes a poster PNG (a frame at 9 s by default) and the audio master WAV. Keep `asset-notices.txt` with every copy that leaves the machine. For a review round, zip the MP4, the review page and the notices together.

## Verification

Assert the file; don't eyeball it. The script checks, and fails on:

- video codec H.264, `yuv420p`, the preset's exact dimensions;
- audio 48 kHz stereo;
- duration within 0.1 s of the render's;
- faststart: the `moov` box within the first 64 KB;
- the final file's integrated loudness and true peak, measured again.

Then, by hand:

- Decode the whole file once (`ffmpeg -v error -i film.mp4 -f null -`) to catch corruption.
- Look at frames from the 4K file at 100% crop: text edges, thin lines, the smallest labels.
- Watch the continuous cut once, start to finish, with sound.

## Delivery

- **PowerPoint:** an MP4 with H.264 video and AAC audio. Embed it, since linked media breaks when the deck moves. For a large meeting, set it to play On Click. Keep the standalone MP4 beside the deck.
- **Play test:** on the presenting laptop, from the deck in presentation mode, through the projector and the room's speakers. A file that plays on your machine has proved nothing about the venue.
- **Teams:** screen sharing favours sharpness over frame rate when the content is mostly still, and mostly still with bursts of motion is exactly an animated explainer. The presenter presses **Optimize** on the sharing toolbar and turns on **Include sound** before sharing. PowerPoint Live plays embedded video best, but a meeting recording doesn't capture video from a PowerPoint Live session. If the share still stutters, use the fades-only build.
- **Copy:** put the final MP4 in cloud storage (for OneDrive on macOS, under `~/Library/CloudStorage/OneDrive-*/`) and note where it went, since the export folder is the one that gets cleaned.
