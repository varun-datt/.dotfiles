#!/usr/bin/env python3
"""Cut each narration line from its last complete reading in one recording, and list the takes to listen to.

Usage:
    uv run --python 3.12 --with faster-whisper python align_takes.py RECORDING SCRIPT_JSON [-o takes.json]
        [--model small.en] [--say say.json] [--min-match 0.78] [--gate-db 15]

SCRIPT_JSON holds "captions": [[start, end, text], ...], or is a JSON list of line strings.
--say is a JSON object mapping a written word to how it was spoken, e.g. {"mcp": "m c p"}; it is applied
to both the captions and the transcript. Digits become words on both sides.
The model loads from the local cache only: fetch it once with network, then this runs offline.

The recording is split into voiced islands (speech louder than the loud-speech level minus --gate-db,
separated by at least 0.6 s of quiet) and each island is transcribed on its own. Transcribing the whole file
at once drops a line read twice in a row, and smears word times across a pause, so a false start and its
restart read as one clean sentence.
Writes takes.json ({"recording", "takes": [{"caption", "from", "to"}]}), then prints the weakest matches,
every take spanning more than one island (each island's own transcript) and every line with a later reading
that matched less well. Listen to those before accepting them.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

RATE = 16000
FRAME = 0.01
LEAD, RELEASE = 0.10, 0.20
ISLAND_GAP = 0.6
MIN_ISLAND = 0.15
ONES = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
        'seventeen eighteen nineteen').split()
TENS = 'twenty thirty forty fifty sixty seventy eighty ninety'.split()


def number_words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10 - 2] + ('' if n % 10 == 0 else ' ' + ONES[n % 10])
    return ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + number_words(n % 100))


def normalizer(say):
    def norm(text):
        text = text.lower().replace('\u2019', "'").replace('-', ' ').replace('\u2013', ' ').replace('%', ' percent')
        text = re.sub(r"[^a-z0-9' ]", ' ', text)
        text = re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])', ' ', text)
        words = []
        for word in text.split():
            word = say.get(word, word)
            words.append(number_words(int(word)) if word.isdigit() and int(word) < 1000 else word)
        return ' '.join(words)
    return norm


def decode(path):
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(RATE), '-f', 'f32le', '-'],
                         capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(pcm, dtype=np.float32)


def voiced_islands(audio, gate_db):
    hop = int(RATE * FRAME)
    n = len(audio) // hop
    rms = np.sqrt((audio[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-9)
    voiced = np.nonzero(db > np.percentile(db, 90) - gate_db)[0]
    found = []
    for i in voiced:
        if found and (i - found[-1][1]) * FRAME < ISLAND_GAP:
            found[-1][1] = i
        else:
            found.append([i, i])
    return [(a * FRAME, (b + 1) * FRAME) for a, b in found if (b + 1 - a) * FRAME >= MIN_ISLAND]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('recording', type=Path)
    parser.add_argument('script', type=Path)
    parser.add_argument('-o', '--out', type=Path, help='default: takes.json next to the recording')
    parser.add_argument('--model', default='small.en')
    parser.add_argument('--say', type=Path)
    parser.add_argument('--min-match', type=float, default=0.78)
    parser.add_argument('--gate-db', type=float, default=15.0, help='speech threshold below the loud-speech level')
    args = parser.parse_args()

    spec = json.loads(args.script.read_text())
    captions = [c[2] for c in spec['captions']] if isinstance(spec, dict) else list(spec)
    norm = normalizer(json.loads(args.say.read_text()) if args.say else {})
    out = args.out or args.recording.with_name('takes.json')

    audio = decode(args.recording)
    model = WhisperModel(args.model, device='cpu', compute_type='int8', local_files_only=True)
    islands, words = [], []
    for start, end in voiced_islands(audio, args.gate_db):
        clip = audio[int(start * RATE):int(end * RATE)]
        segments, _ = model.transcribe(clip, word_timestamps=True, vad_filter=False, beam_size=5,
                                       condition_on_previous_text=False)
        heard = [(w.word, w.start, w.end) for s in segments for w in s.words]
        islands.append({'start': start, 'end': end, 'text': ''.join(w for w, _, _ in heard).strip()})
        words += [(norm(w), len(islands) - 1, start + a, start + b) for w, a, b in heard if norm(w)]
    print(f'islands={len(islands)} words={len(words)}')

    takes, missing, later = [], [], []
    for caption in captions:
        target = norm(caption)
        n = len(target.split())
        best, found = 0.0, []
        for i in range(len(words)):
            for k in range(max(1, n - 4), n + 5):
                if i + k > len(words):
                    break
                window = ' '.join(w[0] for w in words[i:i + k])
                ratio = difflib.SequenceMatcher(None, target, window, autojunk=False).ratio()
                best = max(best, ratio)
                if ratio >= args.min_match:
                    found.append((ratio, i, i + k))
        if not found:
            missing.append((caption, round(best, 2)))
            continue
        top = max(r for r, _, _ in found)
        readings = []
        for f in sorted((f for f in found if f[0] >= top - 0.06), key=lambda f: f[1]):
            if readings and f[1] < max(g[2] for g in readings[-1]):
                readings[-1].append(f)
            else:
                readings.append([f])
        ratio, i, j = max(readings[-1])
        first, last = words[i], words[j - 1]
        starts_island = i == 0 or words[i - 1][1] != first[1]
        ends_island = j == len(words) or words[j][1] != last[1]
        take = {'caption': caption, 'match': round(ratio, 3),
                'from': round(max(0.0, (islands[first[1]]['start'] if starts_island else first[2]) - LEAD), 2),
                'to': round((islands[last[1]]['end'] if ends_island else last[3]) + RELEASE, 2),
                'islands': list(range(first[1], last[1] + 1))}
        takes.append(take)
        after = [f for f in found if f[1] >= j]
        if after:
            r, a, _ = max(after)
            later.append((take, round(r, 3), round(words[a][2], 2)))

    if missing:
        for caption, ratio in missing:
            print(f'NOT FOUND (best {ratio}): {caption}')
        sys.exit(1)
    ordered = sorted(takes, key=lambda t: t['from'])
    for a, b in zip(ordered, ordered[1:]):
        if a['to'] > b['from']:
            a['to'] = round(b['from'] - 0.02, 2)

    recording = os.path.relpath(args.recording.resolve(), out.resolve().parent)
    out.write_text(json.dumps({'recording': recording, 'recorded': date.today().isoformat(),
                               'takes': [{k: t[k] for k in ('caption', 'from', 'to')} for t in takes]}, indent=1) + '\n')
    print(f'takes={len(takes)} of {len(captions)} -> {out}')
    print('weakest matches:')
    for t in sorted(takes, key=lambda t: t['match'])[:5]:
        print(f"  {t['match']}  {t['from']:8.2f}-{t['to']:8.2f}  {t['caption'][:70]}")
    spanning = [t for t in takes if len(t['islands']) > 1]
    for t in spanning:
        print(f"LISTEN {t['from']:8.2f}-{t['to']:8.2f}  {t['caption'][:70]}")
        for k in t['islands']:
            print(f"    {islands[k]['start']:8.2f}-{islands[k]['end']:8.2f}  {islands[k]['text']}")
    for t, r, at in later:
        print(f"LATER READING at {at:8.2f} matched {r} (chosen {t['match']} at {t['from']:.2f}): {t['caption'][:60]}")
    print(f'takes to listen to={len(spanning) + len(later)}')


if __name__ == '__main__':
    main()
