#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# FMini-1: the sound samples of the site (the Sound section). Renders the first ten factory presets (000-009) through the
# real firmware (docs/emu/felucca.wasm, via tools/preset_lab.mjs), each with a short line that shows its timbre, and
# writes docs/sounds/NN-name.mp3 plus docs/sounds/samples.json (the waveform of each, 120 bars, for the players).
#   python3 tools/fmini_samples.py [--wasm docs/emu/felucca.wasm] [--out docs/sounds]   (needs numpy, scipy, node, ffmpeg)
import argparse, json, pathlib, shutil, subprocess, sys, tempfile
import numpy as np
from scipy.io import wavfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import gen_fmini_presets as G  # noqa: E402
import fmini_bank  # noqa: E402

DUR = 10.0
FS = 44100
BARS = 120


def mono(notes, start, step, length=None, legato=True):
    """a mono line: each note starts at start + i*step; legato: the note ends when the next one starts (after it)"""
    ev = []
    for i, n in enumerate(notes):
        t = start + i * step
        ev.append([t, "on", n, 100])
        if legato and i + 1 < len(notes):
            ev.append([t + step, "off", n])
        else:
            ev.append([t + (length or step * 0.7), "off", n])
    return ev


def chords(seq, start, hold, gap=0.0, vel=100):
    """poly chords, one after another; each held `hold` seconds"""
    ev, t = [], start
    for ch in seq:
        for n in ch:
            ev.append([t, "on", n, vel])
        for n in ch:
            ev.append([t + hold, "off", n])
        t += hold + gap
    return ev


def overlap(seq, start, step, hold, vel=100):
    """poly chords, each new one before the last is let go (a pad's breath)"""
    ev = []
    for k, ch in enumerate(seq):
        t = start + k * step
        for n in ch:
            ev.append([t, "on", n, vel])
        end = t + step + 0.2 if k + 1 < len(seq) else start + len(seq) * step + hold
        for n in ch:
            ev.append([min(end, DUR - 0.2), "off", n])
    return ev


def melody_lead():
    # MINI LEAD: a mono phrase in A minor, legato, so the glide slides between the notes
    notes = [69, 72, 74, 76, 74, 72, 69, 67, 65, 67, 69, 72]
    return mono(notes, 0.3, 0.7) + [[9.0, "on", 69, 100], [9.6, "off", 69]]


def bass_line():
    # MOOG BASS: a short bass pattern, notes apart, A1 and its fifth, fourth and octave
    notes = [33, 33, 40, 33, 36, 33, 38, 40] * 2
    return mono(notes, 0.2, 0.6, length=0.42, legato=False)


def arp_chords():
    # PLUCK ARP: two held chords, the arpeggiator (on in this preset) plays them in order
    ev = []
    for n in (60, 63, 67, 70):
        ev.append([0.1, "on", n, 100])
        ev.append([4.8, "off", n])
    for n in (53, 56, 60, 63):
        ev.append([4.9, "on", n, 100])
        ev.append([9.6, "off", n])
    return ev


def pad_swell():
    # PAD SWELL: four overlapping chords, slow in and out
    return overlap([(48, 55, 64), (45, 52, 60), (41, 48, 57), (43, 50, 59)], 0.2, 2.4, 2.4)


def sine_solo():
    # SINE SOLO: a sung melody, long notes
    seq = [(67, 2.0), (69, 1.0), (72, 2.0), (71, 1.0), (69, 1.5), (67, 1.5)]
    ev, t = [], 0.3
    for n, d in seq:
        ev += [[t, "on", n, 100], [t + d - 0.08, "off", n]]
        t += d
    return ev


def space_drone():
    # SPACE DRONE: two low chords that move slowly
    ev = []
    for n in (36, 43, 48):
        ev += [[0.1, "on", n, 90], [5.0, "off", n]]
    for n in (34, 41, 46):
        ev += [[5.1, "on", n, 90], [9.6, "off", n]]
    return ev


def cs80_brass():
    # CS-80 BRASS: punchy chords, eight stabs
    stabs = [(48, 55, 60), (44, 51, 56), (46, 53, 58), (43, 50, 55)] * 2
    ev = []
    for k, ch in enumerate(stabs):
        t = 0.2 + k * 1.2
        for n in ch:
            ev += [[t, "on", n, 115], [t + 0.9, "off", n]]
    return ev


def lush_strings():
    # LUSH STRINGS: a slow progression, the voices kept together
    return overlap([(50, 57, 60, 65), (46, 53, 57, 65), (43, 50, 58, 62), (45, 52, 55, 61)], 0.2, 2.4, 2.4, vel=90)


def aura_atmos():
    # AURA ATMOS: one cluster that turns into another
    ev = []
    for n in (57, 60, 64, 67, 71, 74):
        ev += [[0.2, "on", n, 90], [5.2, "off", n]]
    for n in (55, 60, 62, 66, 69, 72):
        ev += [[5.0, "on", n, 90], [9.6, "off", n]]
    return ev


def ufo_sweep():
    # UFO: mono sweeps up and down, legato, with the preset's delay and reverb
    up = list(range(36, 85, 4))
    line = (up + up[-2::-1]) * 2
    return mono(line, 0.2, 0.14) + [[7.6, "on", 60, 100], [9.6, "off", 60]]


SAMPLES = [
    ("000", "mini-lead", melody_lead),
    ("001", "moog-bass", bass_line),
    ("002", "pluck-arp", arp_chords),
    ("003", "pad-swell", pad_swell),
    ("004", "sine-solo", sine_solo),
    ("005", "space-drone", space_drone),
    ("006", "cs80-brass", cs80_brass),
    ("007", "lush-strings", lush_strings),
    ("008", "aura-atmos", aura_atmos),
    ("009", "ufo", ufo_sweep),
]


def peaks(x):
    n = len(x) // BARS
    b = np.abs(x[: n * BARS]).reshape(BARS, n).max(axis=1)
    return [round(float(v), 3) for v in b]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wasm", default=str(ROOT / "docs/emu/felucca.wasm"))
    ap.add_argument("--out", default=str(ROOT / "docs/sounds"))
    a = ap.parse_args()
    bank = fmini_bank.build(G.Bank())
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fmini_samples_"))
    scen = []
    for i, (num, slug, fn) in enumerate(SAMPLES):
        scen.append(dict(id=num, preset=i, dur=DUR, events=fn()))
        assert bank.p[i]["name"] is not None
    (tmp / "scen.json").write_text(json.dumps(scen))
    subprocess.run(["node", str(HERE / "preset_lab.mjs"), a.wasm, str(tmp / "scen.json"), str(tmp / "wav")], check=True)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for (num, slug, _), i in zip(SAMPLES, range(len(SAMPLES))):
        sr, d = wavfile.read(tmp / "wav" / (num + ".wav"))
        d = d.astype(np.float64)
        if d.ndim == 1:
            d = np.stack([d, d], 1)
        fade = int(0.12 * sr)
        d[-fade:] *= np.linspace(1, 0, fade)[:, None]
        pk = np.abs(d).max()
        d *= 10 ** (-1.0 / 20) / pk                       # peak at -1 dBFS: each sample at the same level on the page
        norm = tmp / (num + ".norm.wav")
        wavfile.write(norm, sr, d.astype(np.float32))
        mp3 = out / (num + "-" + slug + ".mp3")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(norm), "-codec:a", "libmp3lame",
                        "-b:a", "112k", "-ac", "2", str(mp3)], check=True)
        index.append(dict(id=num, preset=i, name=bank.p[i]["name"], file="sounds/" + mp3.name,
                          seconds=DUR, peaks=peaks(d.mean(axis=1))))
        print(num, bank.p[i]["name"], mp3.name, "%.0f KB" % (mp3.stat().st_size / 1024))
    (out / "samples.json").write_text(json.dumps(dict(samples=index), ensure_ascii=False, separators=(",", ":")))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
