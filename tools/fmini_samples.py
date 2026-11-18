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


# The pitch each patch sounds for a key: a test note sent at MIDI 60 is heard at this many semitones away (measured on
# the emulator with a single held note). The patch's own footages (a 16' oscillator sounds an octave low) decide it,
# not the OCTAVE field alone, so a line is sent at (wanted - offset) and comes out where it is written.
HEARD_OFFSET = {0: -12, 1: -24, 2: 0, 3: -12, 4: 0, 5: -12, 6: -12, 7: 0, 8: -12, 9: 0}


def score(bpm, items, offset, legato=0.92):
    """items: (beat, dur, sounding midi note, velocity) in beats; offset: the patch's HEARD_OFFSET"""
    shift = -offset
    s = 60.0 / bpm
    ev = []
    for b, d, n, v in items:
        t0 = START + b * s
        t1 = t0 + d * s * legato
        ev.append([round(t0, 4), "on", n + shift, v])
        ev.append([round(min(t1, DUR - 0.25), 4), "off", n + shift])
    return ev


def N(b, d, n, v=100):
    return (b, d, n, v)


def C(b, d, ns, v=100):
    return [(b, d, n, v) for n in ns]


START = 0.4


def bend_path(points, step=0.02):
    """pitch bend events along breakpoints (t seconds, semitones); the range is +-2 (the factory's PITCH BEND 0),
    so a semitone is 4096 steps around the centre 8192. Linear between the points, one event every `step` s."""
    ev = []
    for (t0, s0), (t1, s1) in zip(points, points[1:]):
        n = max(1, int(round((t1 - t0) / step)))
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            v = s0 + (s1 - s0) * i / n
            ev.append([round(t, 4), "bend", max(0, min(16383, round(8192 + v * 4096)))])
    return ev


# ---- the ten arrangements: a keyboardist's line for each patch, in the register it sounds in ----

def mini_lead(off):
    # 000 MINI LEAD: a mono line in A minor, syncopated, with a sixteenth run and a long landing
    it = [N(0.5, .5, 69), N(1, .5, 72), N(1.5, 1, 76), N(2.5, .5, 74), N(3, .5, 72), N(3.5, .5, 71), N(4, 1, 69),
          N(5.5, .5, 67), N(6, .5, 69), N(6.5, 1.5, 72), N(8, .5, 74), N(8.5, .25, 76), N(8.75, .25, 74),
          N(9, .5, 72), N(9.5, .5, 71), N(10, 1.5, 69),
          N(12, .25, 67), N(12.25, .25, 69), N(12.5, .25, 71), N(12.75, .25, 72), N(13, 1, 76), N(14, .5, 74),
          N(14.5, .5, 71), N(15, 1, 69), N(16.5, 2.5, 69, 110)]
    T = lambda b: START + b * 0.5   # 120 bpm: a beat is half a second
    bends = [(0.0, 0.0), (T(1.5), -2.0), (T(1.5) + 0.2, 0.0),                    # scoop up into the E5
             (T(7.0), 0.0), (T(7.9), -2.0), (T(8.0), 0.0),                     # fall off the C5 before the D5
             (T(16.5) + 0.2, 0.0), (T(16.5) + 0.7, 1.0), (T(16.5) + 1.2, 0.0)]  # the last note bends up and back
    return score(120, it, off, legato=0.95) + bend_path(bends)


def moog_bass(off):
    # 001 MOOG BASS: a sixteenth-note bass riff in E minor, octave jumps, two cycles and a held octave, an octave down
    c1 = [N(0, .5, 40), N(.75, .25, 52), N(1, .25, 40), N(1.5, .25, 43), N(1.75, .25, 40), N(2, .5, 45),
          N(2.5, .25, 47), N(2.75, .25, 45), N(3, .25, 43), N(3.5, .5, 40), N(4, .25, 40), N(4.25, .25, 40),
          N(4.5, .5, 52), N(5, .25, 50), N(5.25, .25, 47), N(5.5, .25, 43), N(5.75, .25, 45), N(6, .5, 47),
          N(6.5, .25, 40), N(6.75, .25, 52), N(7, .25, 43), N(7.25, .25, 45), N(7.5, .25, 47), N(7.75, .25, 50)]
    c2 = [(b + 8, d, n, v + (10 if i % 4 == 0 else 0)) for i, (b, d, n, v) in enumerate(c1)]
    c2 += [N(15.5, .25, 52, 120), N(15.75, 1.0, 52, 110)]
    # one octave lower than the first version: the same riff with the key sent one octave higher
    return score(110, c1 + c2, off + 12, legato=0.85)


def pluck_arp(off):
    # 002 PLUCK ARP: an Am9 - Fmaj7 - C6 - G7sus4 loop, struck twice per chord; the arpeggiator fills the gaps
    prog = [(57, 60, 64, 67, 71), (53, 57, 60, 64), (60, 64, 67, 69), (55, 60, 62, 65)]
    it = []
    for k in range(4):
        for rep in range(2):
            b = k * 2 + rep * 8
            it += C(b, 1.5, prog[k], 100)
            it += C(b + 1.75, .5, prog[k], 90)
    return score(108, it, off, legato=0.9)


def pad_swell(off):
    # 003 PAD SWELL: Dm9 - Bbmaj7 - Gm7 - A7sus4, voices moving together, each chord breathing into the next
    prog = [(50, 57, 60, 64), (46, 53, 57, 62), (55, 58, 62, 65), (57, 62, 64, 67)]
    it = []
    for k, ch in enumerate(prog):
        it += C(k * 3, 3.6, ch, 92)
    return score(96, it, off, legato=1.0)


def sine_solo(off):
    # 004 SINE SOLO: a sung melody in D major, with grace notes, a rubato held note and a turn at the end
    it = [N(0, 1.5, 74, 100), N(1.5, .5, 76), N(2, 1.0, 78), N(3, .5, 76), N(3.5, .5, 74), N(4, 1.0, 71),
          N(5, .125, 73), N(5.125, .125, 74), N(5.25, .25, 71), N(5.5, 1.5, 74, 110),
          N(7, .5, 78), N(7.5, .5, 76), N(8, .5, 74), N(8.5, .5, 71), N(9, 1.0, 69),
          N(10, .25, 71), N(10.25, .25, 73), N(10.5, .25, 74), N(10.75, .25, 73), N(11, 1.0, 74, 110)]
    return score(84, it, off, legato=0.96)


def space_drone(off):
    # 005 SPACE DRONE: a C pedal under Cm - Ab - Bb - Cm add9, a bell melody on top every few beats
    it = []
    for b, ch in ((0, (48, 55, 63)), (3, (44, 51, 60)), (6, (46, 53, 62)), (9, (48, 55, 62, 74))):
        it += C(b, 3.6, ch, 90)
    it += C(0, 12, (36,), 80)   # the pedal tone, an octave below (C2)
    for b, n in ((1.5, 79), (4.5, 75), (7.5, 72), (10.5, 67)):
        it += [N(b, 2.5, n, 96)]
    return score(80, it, off, legato=1.0)


def cs80_brass(off):
    # 006 CS-80 BRASS: a syncopated horn riff over Bb - Gm - Eb - F7, short stabs with an offbeat, a held Bb at the end
    prog = [(58, 62, 65), (55, 58, 62), (51, 55, 58), (53, 57, 60, 63)]
    it = []
    for k, ch in enumerate(prog):
        b = k * 4
        it += C(b, .4, ch, 115)
        it += C(b + 1.5, .3, ch, 100)
        it += C(b + 2.0, .3, ch, 105)
        it += C(b + 3.5, .4, ch, 115)
    it += C(16, 1.5, (58, 62, 65), 110)
    return score(120, it, off, legato=0.9)


def lush_strings(off):
    # 007 LUSH STRINGS: Dm7 - Gm7 - C - A7 with a violin line on top, the voices kept together
    prog = [(50, 57, 60, 65), (55, 58, 62, 65), (48, 55, 60, 64), (57, 61, 64, 67)]
    it = []
    for k, ch in enumerate(prog):
        it += C(k * 3, 3.0, ch, 92)
    top = [N(0, 1.5, 74), N(1.5, 1.5, 77), N(3, 1, 79), N(4, .5, 77), N(4.5, 1.5, 74), N(6, 1.5, 72),
           N(7.5, 1.5, 76), N(9, 1.5, 79), N(10.5, 1.5, 81)]
    return score(84, it + top, off, legato=1.0)


def aura_atmos(off):
    # 008 AURA ATMOS: two notes an octave apart, sustained the whole sample, in the middle-lower register (C3 and C4)
    it = C(0, 9.2, (48,), 100) + C(0, 9.2, (60,), 100)
    return score(60, it, off, legato=1.0)


def ufo_sweep(off):
    # 009 UFO: a mono theremin-like line, long glides up and down, legato joins where the next note starts first
    it = [N(0, 1.6, 76), N(1.4, 1.2, 71), N(2.5, 1.0, 79), N(3.4, 1.2, 74), N(4.5, 2.0, 83),
          N(6.5, .5, 81), N(7.0, .5, 76), N(7.5, 1.6, 64), N(9.0, .5, 69)]
    return score(72, it, off, legato=1.06)


SAMPLES = [
    ("000", "mini-lead", mini_lead),
    ("001", "moog-bass", moog_bass),
    ("002", "pluck-arp", pluck_arp),
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
        scen.append(dict(id=num, preset=i, dur=DUR, events=fn(HEARD_OFFSET[i])))
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
