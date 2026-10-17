# Audio: voice, music, master

## Recording the presenter

Generate `read-aloud.md` from the captions, never by hand: each line numbered and grouped by scene, with the seconds the screen gives it, plus a "how to say" table for names and acronyms. Hand the presenter this protocol with it:

1. A quiet room with soft furnishings, Do Not Disturb on.
2. QuickTime Player, File > New Audio Recording, quality Maximum (uncompressed AIFF-C). Microphone 15 to 20 cm from the mouth.
3. Three seconds of silence before the first line: the room's own sound to clean against.
4. Each line once, then a pause of about two seconds.
5. On a stumble: stop, pause, read the whole line again. The last complete reading is the one used.
6. A natural pace. If a line feels rushed, say so: the scene gets longer, the voice doesn't speed up.
7. Send the file untouched, without trimming or processing.

Record every line in one sitting, in one room, on one microphone; two sessions are audible side by side. Pickups use the same room and microphone.

## Cutting takes

`takes.json`, beside the recording:

```json
{"recording": "recording.aifc", "takes": [
  {"caption": "<exact caption text>", "from": 11.7, "to": 17.7},
  {"caption": "<another caption>", "from": 19.8, "to": 31.0, "spans": [[19.8, 24.1], [27.4, 31.0]]}
]}
```

- `spans` joins pieces of one reading to drop a long pause, with 0.22 s of silence between pieces. Use it only after listening: the earlier piece may be a false start.
- `scripts/align_takes.py` splits the recording into voiced islands and transcribes each island on its own, offline. It finds each caption's last complete reading (text similarity at least 0.78 over a sliding window of words), cuts at the island edges, and lists every take that spans more than one island, with each island's text, plus any line with a later, weaker reading. Listen to every listed take before accepting it.
- A take whose caption no longer exists must stop the build (re-record or re-map it), never drop silently.
- After placing the lines, transcribe each one again from the finished narration and diff it against its caption. That catches a clipped first or last word and a wrong take.

## The voice chain

ffmpeg filters, in this order, on the recording before cutting:

| Stage | Filter | Why |
|---|---|---|
| Low end | `highpass=f=90,highpass=f=90,lowshelf=f=220:g=-8` | A close microphone's proximity effect |
| Less boxy | `equalizer=f=320:t=q:w=1:g=-1.5` | |
| Presence | `equalizer=f=3500:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5` | Brighter; added with the tempo below when the owner asked for a more upbeat read |
| Tempo | `atempo=1.04` | Quicker without a pitch change; 4% doesn't sound sped up |

Then a 20 ms fade at each cut edge, and each line normalized to −20 LUFS (pyloudnorm) so lines match one another.

Placement: each line starts at its caption's start, or 0.15 s after the previous line ends if that is later. A line may outlast its caption's display window, never run into the next line. Report overruns and delays; fix them by lengthening the scene.

Stale-input guards: the narration records a digest of the captions, and the soundtrack records digests of the narration and of the scene timings. Muxing refuses stale inputs, so a caption edit forces the audio to be rebuilt instead of shipping the previous version's.

## Synthetic stand-in

Until the recording arrives, a local voice speaks the captions so the timing can be judged:

- Kokoro-82M (Apache-2.0) through `kokoro-onnx` (MIT), on the CPU, offline. Model files `kokoro-v1.0.onnx` and `voices-v1.0.bin` live in `~/.cache/kokoro-onnx`. Run it with `uv run --python 3.12 --with kokoro-onnx --with soundfile --with scipy --with pyloudnorm`.
- Voice `am_michael` (US male) was preferred. `hm_omega` and `hm_psi` were judged too heavy on the accent.
- Speed a line up only to fit its window, at most 1.2×.
- Keep a spoken-forms map apart from the captions: acronyms as letters ("M C P"), compound product names split ("Azure Dev Ops"), names as the presenter says them. The captions keep the written forms.
- Never use a person's recording as a reference voice.

## Music bed

`scripts/music_bed.py` generates the bed in code, with no samples: B-flat major at 112 BPM, Bb–F–Gm–Eb at one chord per bar, a bright plucked arpeggio, a bass bouncing in octaves, a pad pumping on the beat, and a soft kick with off-beat hats from the second bar. Stem levels can change per scene. It ramps in over 0.4 s and fades out over the last 4 s.

- Level: the bed's RMS sits 12 dB below the voice's RMS while it speaks (the owner's pick over 10 dB). It ducks by a further 55% under speech, with a 120 ms look-ahead, 270 ms hold, 80 ms attack and 600 ms release.
- The voice goes into the mix through `highpass=f=80,acompressor=threshold=-24dB:ratio=3:attack=12:release=180:makeup=1`.
- Read the music's level under the voice from the mix (`musicUnderVoiceDb` in its summary), not from the settings.
- When two films play at the same event, make the second bed audibly different (`--transpose`, a different tempo), or the audience hears the same piece twice.

## Master

`scripts/master_export.py` measures the mix with `loudnorm=I=-14:TP=-1:LRA=11:print_format=json` (analysis only), applies the gain through `alimiter` with its ceiling 0.5 dB under the true-peak target, measures again, and repeats until it is within 0.2 LU. It asserts the true peak and keeps the 24-bit, 48 kHz WAV as the audio master next to the film.

Listen before calling it done: on speakers and on headphones, the quietest sentence, every edit, the first and last seconds, and the music under the quietest line.
