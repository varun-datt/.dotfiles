#!/usr/bin/env python3
"""Master a soundtrack to a loudness target, mux it with a silent render, encode a preset, and verify the file.

Usage:
    python3 master_export.py --video RENDER.mp4 --audio SOUNDTRACK.wav --out DIR --name NAME [--preset share|4k]
        [--lufs -14] [--true-peak -1] [--poster-at 9]

share: H.264 High CRF 22, at most 1080 lines, AAC 160 kbps. 4k: H.264 High@5.1 CRF 14 capped at 50 Mbps,
BT.709 tags, AAC 320 kbps; needs a 3840x2160 render. Both 48 kHz stereo with faststart.
Writes OUT/NAME.mp4, OUT/NAME-poster.png and OUT/NAME-audio-master.wav, asserts codec, size, pixel format,
audio format, duration, faststart and loudness, and prints a JSON summary. Needs ffmpeg and ffprobe.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PRESETS = {
    'share': {
        'video': ['-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation', '-crf', '22', '-profile:v', 'high', '-pix_fmt', 'yuv420p'],
        'audio': ['-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2'],
        'max_height': 1080,
    },
    '4k': {
        'video': ['-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation', '-crf', '14', '-maxrate', '50M', '-bufsize', '100M',
                  '-profile:v', 'high', '-level:v', '5.1', '-pix_fmt', 'yuv420p',
                  '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv'],
        'audio': ['-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-ac', '2'],
        'size': (3840, 2160),
    },
}


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        sys.exit(f'{args[0]} failed: {result.stderr[-1500:]}')
    return result


def loudness(path, lufs, tp):
    err = run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-af',
               f'loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json', '-f', 'null', '-']).stderr
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    return float(m['input_i']), float(m['input_tp'])


def master(audio, out, lufs, tp):
    ceiling = 10 ** ((tp - 0.5) / 20)
    gain = lufs - loudness(audio, lufs, tp)[0]
    for _ in range(4):
        run(['ffmpeg', '-y', '-v', 'error', '-i', str(audio), '-af',
             f'volume={gain:.2f}dB,alimiter=limit={ceiling:.4f}:attack=5:release=80:level=false',
             '-ar', '48000', '-c:a', 'pcm_s24le', str(out)])
        measured, peak = loudness(out, lufs, tp)
        if abs(measured - lufs) <= 0.2:
            assert peak <= tp + 0.5, f'master true peak {peak} dBTP'
            return
        gain += lufs - measured
    sys.exit('master did not reach the loudness target')


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_entries',
                           'format=duration,size,bit_rate:stream=codec_type,codec_name,profile,level,pix_fmt,width,height,'
                           'r_frame_rate,sample_rate,channels,bit_rate', '-of', 'json', str(path)]).stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--preset', choices=PRESETS, default='4k')
    parser.add_argument('--lufs', type=float, default=-14.0)
    parser.add_argument('--true-peak', type=float, default=-1.0)
    parser.add_argument('--poster-at', type=float, default=9.0)
    args = parser.parse_args()

    preset = PRESETS[args.preset]
    source = next(s for s in probe(args.video)['streams'] if s['codec_type'] == 'video')
    filters = []
    if 'size' in preset:
        assert (source['width'], source['height']) == preset['size'], \
            f"render is {source['width']}x{source['height']}; render at {preset['size'][0]}x{preset['size'][1]}, never upscale"
    elif source['height'] > preset['max_height']:
        filters = ['-vf', f"scale=-2:{preset['max_height']}:flags=lanczos"]

    args.out.mkdir(parents=True, exist_ok=True)
    wav = args.out / f'{args.name}-audio-master.wav'
    mp4 = args.out / f'{args.name}.mp4'
    master(args.audio, wav, args.lufs, args.true_peak)
    run(['ffmpeg', '-y', '-v', 'error', '-i', str(args.video), '-i', str(wav), '-map', '0:v', '-map', '1:a', *filters,
         *preset['video'], *preset['audio'], '-movflags', '+faststart', str(mp4)])
    run(['ffmpeg', '-y', '-v', 'error', '-ss', str(args.poster_at), '-i', str(args.video), '-frames:v', '1', *filters,
         str(args.out / f'{args.name}-poster.png')])

    info = probe(mp4)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    expected = preset.get('size') or (round(source['width'] * min(1, preset['max_height'] / source['height']) / 2) * 2,
                                      min(source['height'], preset['max_height']))
    assert video['codec_name'] == 'h264' and video['pix_fmt'] == 'yuv420p', (video['codec_name'], video['pix_fmt'])
    assert (video['width'], video['height']) == tuple(expected), (video['width'], video['height'], expected)
    assert audio['sample_rate'] == '48000' and audio['channels'] == 2, 'audio is not 48 kHz stereo'
    source_seconds = float(probe(args.video)['format']['duration'])
    assert abs(float(info['format']['duration']) - source_seconds) < 0.1, 'duration differs from the render'
    assert b'moov' in mp4.read_bytes()[:65536], 'not faststart'
    measured, peak = loudness(mp4, args.lufs, args.true_peak)
    assert abs(measured - args.lufs) <= 0.5, f'final loudness {measured} LUFS'
    print(json.dumps({
        'video': str(mp4), 'size': f"{video['width']}x{video['height']}", 'fps': video['r_frame_rate'],
        'codec': f"{video['codec_name']} {video['profile']} L{video['level'] / 10}",
        'videoMbps': round(float(info['format']['bit_rate']) / 1e6, 1),
        'audio': f"{audio['codec_name']} {round(int(audio['bit_rate']) / 1000)} kbps {audio['sample_rate']} Hz {audio['channels']}ch",
        'loudness': {'I': measured, 'TP': peak}, 'megabytes': round(int(info['format']['size']) / 1e6, 1),
        'seconds': float(info['format']['duration']),
    }, indent=1))


if __name__ == '__main__':
    main()
