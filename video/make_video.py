"""Builds explainer.mp4: Kokoro voiceover (offline) + portal screenshots with slow zoom and crossfades.

    .venv/bin/python make_video.py              # voice am_michael
    .venv/bin/python make_video.py am_fenrir    # try another male US voice
"""
import subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).parent
VOICE = sys.argv[1] if len(sys.argv) > 1 else 'am_michael'
SPEED = 1.0
FPS, W, H = 30, 1920, 1080
FADE = 0.5   # crossfade between scenes (s)
LEAD = 0.35  # silence before each line, so speech starts after the crossfade settles
TAIL = 0.45  # breathing room after each line

# (frame, narration)
SCENES = [
    ('intro.jpg', "Meet the new Insta Global Travel flight portal. The simplest way to find, and book, the lowest fare."),
    ('s2.jpg', "Just tell us where you're flying from, where you're going, and when."),
    ('s3.jpg', "In seconds, we compare real-time fares across airlines and travel sites, and show you the best, the cheapest, and the fastest flights, side by side."),
    ('s4.jpg', "Narrow it down by stops, departure time, airline, or price. Just like the big travel sites."),
    ('s5.jpg', "Open any flight to see every detail. Airports, aircraft, legroom, layovers, and even carbon emissions."),
    ('s8.jpg', "Ready to book? We show you every place selling that fare, from the airline itself to trusted travel sites. Tap Book, and you go straight there to pay securely."),
    ('s7.jpg', "Flying somewhere that needs a visa? We'll sort that too, with a guaranteed delivery date."),
    ('outro.jpg', "Insta Global Travel. Flights and visas, in one place."),
]


def main():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    draft = VOICE == '--draft'  # pipeline test with the built-in Mac voice, while the Kokoro model downloads
    if not draft:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro(str(HERE / 'models/kokoro-v1.0.int8.onnx'), str(HERE / 'models/voices-v1.0.bin'))

    clips, durs = [], []
    for i, (_, text) in enumerate(SCENES):
        if draft:
            subprocess.run(['say', '-v', 'Daniel', '-o', str(out / 'd.wav'), '--data-format=LEF32@24000', text], check=True)
            audio, sr = sf.read(out / 'd.wav', dtype='float32')
        else:
            audio, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang='en-us')
        audio = np.concatenate([np.zeros(int(LEAD * sr)), audio, np.zeros(int(TAIL * sr))]).astype(np.float32)
        clips.append(audio)
        durs.append(len(audio) / sr)
        print(f'scene {i}: {durs[-1]:.2f}s  {text[:50]}…')
    voice = out / f"voice_{'draft' if draft else VOICE}.wav"
    sf.write(voice, np.concatenate(clips), sr)
    total = sum(durs)
    print(f'total {total:.1f}s')

    # Video: each still gets a slow centre zoom; scene k lasts durs[k] (+FADE overlap except the last).
    inputs, chains = [], []
    for k, ((img, _), d) in enumerate(zip(SCENES, durs)):
        length = d + (FADE if k < len(SCENES) - 1 else 0)
        frames = int(round(length * FPS))
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{length:.3f}', '-i', str(HERE / 'frames' / img)]
        # cover 16:9, upscale 2x so the zoom is smooth, then zoom 1.00 -> 1.05 over the scene
        chains.append(f'[{k}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},'
                      f"zoompan=z='1+0.05*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
                      f'trim=duration={length:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{k}]')
    last, offset = 'v0', 0.0
    for k in range(1, len(SCENES)):
        offset += durs[k - 1]
        chains.append(f'[{last}][v{k}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[x{k}]')
        last = f'x{k}'
    chains.append(f'[{last}]fade=t=in:st=0:d=0.4,fade=t=out:st={total - 0.6:.3f}:d=0.6[vout]')
    n = len(SCENES)
    chains.append(f'[{n}:a]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={total - 0.6:.3f}:d=0.6[aout]')

    video = HERE / ('explainer_draft.mp4' if draft else 'explainer.mp4' if VOICE == 'am_michael' else f'explainer_{VOICE}.mp4')
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *inputs, '-i', str(voice),
           '-filter_complex', ';'.join(chains), '-map', '[vout]', '-map', '[aout]',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS),
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', f'{total:.3f}', str(video)]
    subprocess.run(cmd, check=True)
    print('wrote', video)


if __name__ == '__main__':
    main()
