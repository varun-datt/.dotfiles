#!/usr/bin/env python3
"""Generate an upbeat music bed in code, duck it under the narration, and mix the soundtrack.

Usage:
    uv run --python 3.12 --with numpy --with scipy --with soundfile python music_bed.py NARRATION_WAV --out DIR
        [--script script.json] [--levels levels.json] [--below-voice-db 12] [--bpm 112] [--transpose 0]

B-flat major (transposable), Bb-F-Gm-Eb at one chord per bar: a bright plucked arpeggio, a bass bouncing in
octaves, a pad pumping on the beat, and a soft kick with off-beat hats from the second bar. No samples.
--script supplies "scenes" ([{"id", "start", "end"}]) and "durationSeconds"; without it the bed runs the
narration's length at one level. --levels maps a scene id to [pad, pluck, bass, drums] gains (default
0.6, 0.65, 0.6, 0.6); every scene needs an entry.
Writes OUT/music.wav, OUT/soundtrack.wav (24-bit, 48 kHz) and OUT/soundtrack.json, whose musicUnderVoiceDb is the
level actually measured in the mix. Master the soundtrack afterwards with master_export.py.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

SR = 48000
PROG = [[58, 62, 65, 70], [53, 57, 60, 65], [55, 58, 62, 67], [51, 55, 58, 63]]
ROOTS = [46, 41, 43, 39]
DEFAULT_LEVELS = (0.6, 0.65, 0.6, 0.6)
DUCK_DEPTH = 0.55
INTRO, FADE_OUT = 0.4, 4.0
VOICE_CHAIN = 'highpass=f=80,acompressor=threshold=-24dB:ratio=3:attack=12:release=180:makeup=1,aresample=48000'


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69) / 12)


def digest(data):
    return hashlib.sha256(data).hexdigest()[:16]


def level_curves(scenes, levels, t, beat):
    if not scenes:
        return [np.full(t.size, v) for v in DEFAULT_LEVELS]
    missing = [s['id'] for s in scenes if s['id'] not in levels]
    assert not missing, f'no music levels for scenes {missing}'
    curves = []
    for k in range(4):
        knots_t, knots_v = [0.0], [levels[scenes[0]['id']][k]]
        for prev, scene in zip(scenes, scenes[1:]):
            knots_t += [scene['start'], scene['start'] + beat]
            knots_v += [levels[prev['id']][k], levels[scene['id']][k]]
        curves.append(np.interp(t, knots_t, knots_v))
    return curves


def place(out, start, seg):
    i = int(round(start * SR))
    if i < out.size:
        seg = seg[:out.size - i]
        out[i:i + seg.size] += seg


def pluck(f, dur):
    tt = np.arange(int(dur * SR)) / SR
    tone = sum(np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (4 + 6 * h)) / h for h in range(1, 7))
    return tone * np.minimum(1.0, tt / 0.002)


def bass_note(f, dur):
    tt = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)
    return tone * np.exp(-tt / 0.18) * np.minimum(1.0, tt / 0.004) * np.minimum(1.0, (dur - tt) / 0.01)


def kick():
    tt = np.arange(int(0.32 * SR)) / SR
    phase = 2 * np.pi * np.cumsum(48 + 72 * np.exp(-tt / 0.03)) / SR
    return np.sin(phase) * np.exp(-tt / 0.11) * np.minimum(1.0, tt / 0.001)


def hat(rng):
    tt = np.arange(int(0.05 * SR)) / SR
    return np.diff(rng.standard_normal(tt.size + 2), n=2) * np.exp(-tt / 0.01)


def synthesize(t, curves, beat, shift):
    pad_l, pluck_l, bass_l, drum_l = curves
    bar_len = 4 * beat
    prog = [[m + shift for m in chord] for chord in PROG]
    roots = [m + shift for m in ROOTS]
    n = t.size
    bar = np.floor(t / bar_len).astype(np.int64)
    ci = bar % 4
    xf = np.minimum(1.0, (t - bar * bar_len) / 0.25)
    pad = np.zeros(n)
    for c, chord in enumerate(prog):
        gain = np.where(ci == c, xf, 0.0) + np.where((ci + 3) % 4 == c, 1.0 - xf, 0.0)
        idx = np.nonzero(gain > 0)[0]
        tc = t[idx]
        voice = np.zeros_like(tc)
        for m in chord:
            f0 = float(mtof(m))
            for det in (-0.003, 0.003):
                for h in (1, 2, 3):
                    voice += np.sin(2 * np.pi * f0 * (1 + det) * h * tc + h * 0.21) / h ** 2
        pad[idx] += gain[idx] * voice
    pad *= 1 - 0.45 * np.exp(-np.mod(t, beat) / 0.13)

    plk, bass, kicks, hats = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    rng, thump = np.random.default_rng(7), kick()
    for b in range(int(np.ceil(n / SR / bar_len))):
        chord, t0 = prog[b % 4], b * bar_len
        line = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[3] + 12, chord[2] + 12, chord[1] + 12, chord[3] + 12, chord[1] + 12]
        for s, m in enumerate(line):
            place(plk, t0 + s * beat / 2, pluck(float(mtof(m)), 0.6) * (1.0 if s % 2 == 0 else 0.75))
            place(bass, t0 + s * beat / 2, bass_note(float(mtof(roots[b % 4] + (12 if s % 2 else 0))), beat / 2 * 0.9))
        if b >= 1:
            for q in range(4):
                place(kicks, t0 + q * beat, thump)
                place(hats, t0 + q * beat + beat / 2, hat(rng) * (1.0 if q % 2 else 0.8))

    rms = lambda x: np.sqrt(np.mean(x ** 2))
    ramp = np.clip(t / INTRO, 0, 1)
    pad = 0.7 * pad / rms(pad) * pad_l * ramp
    plk = 0.8 * plk / rms(plk) * pluck_l * ramp
    bass = 0.9 * bass / rms(bass) * bass_l * ramp
    drums = (0.6 * kicks / rms(kicks) + 0.22 * hats / rms(hats)) * drum_l

    send = pad * 0.4 + plk * 0.5
    rng = np.random.default_rng(12345)
    it = np.arange(int(1.6 * SR)) / SR
    wet = []
    for _ in range(2):
        ir = rng.standard_normal(it.size) * np.exp(-it / 0.22)
        ir /= np.sqrt(np.sum(ir ** 2))
        wet.append(fftconvolve(send, ir)[:n] * 0.35)
    return np.stack([pad + bass + drums + 1.1 * plk + wet[0], pad + bass + drums + 0.9 * plk + wet[1]])


def duck_curve(voice, n):
    hop = SR // 1000
    blocks = n // hop
    env = np.abs(voice[:blocks * hop]).reshape(blocks, hop).max(axis=1)
    loud = env > 0.02
    ahead = np.concatenate([loud[120:], np.zeros(120, dtype=bool)])
    held = np.convolve(ahead.astype(np.float64), np.ones(270))[:blocks] > 0
    attack, release = 1 - np.exp(-1 / 80), 1 - np.exp(-1 / 600)
    amount, out = 0.0, np.empty(blocks)
    for i, target in enumerate(held):
        amount += (target - amount) * (attack if target > amount else release)
        out[i] = amount
    duck = 1 - DUCK_DEPTH * out
    return np.interp(np.arange(n), np.arange(blocks) * hop, duck), held


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('narration', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--script', type=Path)
    parser.add_argument('--levels', type=Path)
    parser.add_argument('--below-voice-db', type=float, default=12.0)
    parser.add_argument('--bpm', type=float, default=112.0)
    parser.add_argument('--transpose', type=int, default=0, help='semitones')
    args = parser.parse_args()

    script = json.loads(args.script.read_text()) if args.script else {}
    scenes = script.get('scenes', [])
    levels = json.loads(args.levels.read_text()) if args.levels else {s['id']: DEFAULT_LEVELS for s in scenes}
    beat = 60 / args.bpm
    narration_bytes = args.narration.read_bytes()
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(args.narration), '-af', VOICE_CHAIN, '-ac', '1', '-f', 'f32le', '-'],
                         capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    voice = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    duration = script.get('durationSeconds', voice.size / SR)
    n = int(round(duration * SR))
    voice = np.pad(voice, (0, max(0, n - voice.size)))[:n]

    t = np.arange(n) / SR
    music = synthesize(t, level_curves(scenes, levels, t, beat), beat, args.transpose)
    music *= np.clip((duration - t) / FADE_OUT, 0, 1) ** 2

    duck, held = duck_curve(voice, n)
    speaking = np.repeat(held, SR // 1000)[:n]
    speaking = np.pad(speaking, (0, n - speaking.size))
    voice_rms = np.sqrt(np.mean(voice[speaking] ** 2))
    body = (t > INTRO) & (t < duration - FADE_OUT)
    music *= voice_rms * 10 ** (-args.below_voice_db / 20) / np.sqrt(np.mean(music[:, body] ** 2))
    mix = music * duck + voice
    mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))

    args.out.mkdir(parents=True, exist_ok=True)
    sf.write(args.out / 'music.wav', music.T, SR, subtype='PCM_24')
    sf.write(args.out / 'soundtrack.wav', mix.T, SR, subtype='PCM_24')
    under = 20 * np.log10(np.sqrt(np.mean((music[:, speaking] * duck[speaking]) ** 2)) / voice_rms)
    summary = {
        'sampleRate': SR, 'durationSeconds': duration, 'bpm': args.bpm, 'transpose': args.transpose,
        'narrationDigest': digest(narration_bytes),
        'scenesDigest': digest('\n'.join(f"{s['id']}|{s['start']:.2f}|{s['end']:.2f}" for s in scenes).encode()),
        'musicUnderVoiceDb': round(float(under), 1), 'bedBelowVoiceDb': args.below_voice_db,
    }
    (args.out / 'soundtrack.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
