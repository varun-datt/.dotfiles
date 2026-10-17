#!/usr/bin/env python3
"""Build a review packet for a finished cut: frames from the film, the timed script, the brief and the facts.

Usage:
    python3 review_packet.py VIDEO SCRIPT_JSON --out DIR [--brief BRIEF.md] [--facts FACTS.md]

SCRIPT_JSON holds "scenes" ([{"id", "name", "start", "end"}]), "captions" ([[start, end, text]]) and
"durationSeconds". Takes two frames from each scene of 12 s or more (at 45% and 88%) and one from shorter
scenes (at 75%), scaled to 1600 px wide. Writes OUT/packet.md and OUT/frame-*.jpg, replacing older frames.
Needs ffmpeg.
"""
import argparse
import json
import subprocess
from pathlib import Path

LONG_SCENE = 12.0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('video', type=Path)
    parser.add_argument('script', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--brief', type=Path)
    parser.add_argument('--facts', type=Path)
    args = parser.parse_args()

    script = json.loads(args.script.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob('frame-*.jpg'):
        old.unlink()

    frames = []
    for scene in script['scenes']:
        span = scene['end'] - scene['start']
        for share in ([0.45, 0.88] if span >= LONG_SCENE else [0.75]):
            t = round(scene['start'] + span * share, 1)
            name = f"frame-{len(frames) + 1:02d}-{scene['id']}-{t:06.1f}s.jpg"
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(args.video), '-frames:v', '1',
                            '-vf', 'scale=1600:-2', '-q:v', '3', str(args.out / name)], check=True, stdin=subprocess.DEVNULL)
            frames.append((name, t, scene['id'], scene.get('name', '')))

    seconds = script['durationSeconds']
    lines = [
        f"# Review packet: {script.get('title', args.video.stem)}",
        '',
        f'A finished cut, {int(seconds // 60)}:{int(seconds % 60):02d} long. Judge it as the audience will see it: once, on a large screen.',
        '',
    ]
    for heading, path in (('The brief', args.brief), ('Facts about this cut', args.facts)):
        if path:
            lines += [f'## {heading}', '', path.read_text().strip(), '']
    lines += [
        '## Scenes',
        '',
        '| Scene | Name | Start | End |',
        '|---|---|---|---|',
        *[f"| {s['id']} | {s.get('name', '')} | {s['start']:.1f} | {s['end']:.1f} |" for s in script['scenes']],
        '',
        '## Narration, as captioned (start, end, text)',
        '',
        *[f'- {a:6.1f}-{b:6.1f}  {text}' for a, b, text in script['captions']],
        '',
        '## Frames (in this folder)',
        '',
        *[f'- `{n}`: {t:.1f} s, scene {sid} ({name})' for n, t, sid, name in frames],
    ]
    (args.out / 'packet.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'packet': str(args.out / 'packet.md'), 'frames': len(frames)}))


if __name__ == '__main__':
    main()
