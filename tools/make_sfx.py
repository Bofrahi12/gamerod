#!/usr/bin/env python3
"""CineVault product #3 — real synthesized SFX pack. 16 WAVs, 44.1kHz 16-bit mono."""
import os, wave
import numpy as np

SR = 44100
OUT = os.path.expanduser("~/workspace/gamerod/products/gamerod-sfx-pack/SFX")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)

def env_ad(n, a=0.01, d=0.4):
    a_n, d_n = int(n * a), int(n * d)
    e = np.ones(n)
    e[:a_n] = np.linspace(0, 1, a_n)
    e[a_n:a_n + d_n] = np.linspace(1, 0, d_n) ** 1.6
    e[a_n + d_n:] = 0
    return e

def lowpass(x, cutoff_hz):
    # moving-average lowpass, same length as input
    w = max(1, int(SR / cutoff_hz))
    c = np.cumsum(np.concatenate([[0], x]))
    y = (c[w:] - c[:-w]) / w
    return np.concatenate([np.full(w - 1, y[0]), y])

def highpass(x, cutoff_hz):
    return x - lowpass(x, cutoff_hz)

def norm(x, peak=0.89):
    x = x / (np.abs(x).max() + 1e-9)
    return (x * peak)

def write(name, x):
    x = norm(np.asarray(x, dtype=np.float64))
    pcm = (x * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("sfx:", name, f"{len(x)/SR:.2f}s")

def noise(n): return rng.standard_normal(n)

def sweep_tone(dur, f0, f1, shape="exp"):
    n = int(SR * dur); t = np.arange(n) / SR
    k = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** k if shape == "exp" else f0 + (f1 - f0) * k
    return np.sin(2 * np.pi * np.cumsum(f) / SR)

# --- whooshes: band-swept noise ---
def whoosh(dur, bright=1.0):
    n = int(SR * dur); x = noise(n)
    k = np.linspace(0, 1, n)
    swell = np.sin(np.pi * k) ** 1.5
    def pad(a): return np.concatenate([a, np.zeros(n - len(a))])
    body = pad(lowpass(x, 1100))
    air = pad(highpass(x, 2600))
    return (body + air * bright * swell) * swell

write("Whoosh_Soft", whoosh(0.9, 0.7))
write("Whoosh_Hard", whoosh(0.6, 1.4))
write("Whoosh_Long", whoosh(1.6, 1.0))

# --- risers ---
def riser(dur, name):
    n = int(SR * dur); k = np.linspace(0, 1, n)
    tone = sweep_tone(dur, 180, 3200)
    nz = highpass(noise(n), 900)
    return (tone * 0.5 + nz * 0.4) * (k ** 2) * env_ad(n, 0.02, 0.98) + (tone * 0.5 + nz * 0.4) * 0
write("Riser_Short", riser(1.0, ""))
write("Riser_Long", riser(2.6, ""))

# --- impacts ---
def boom(dur=1.3):
    n = int(SR * dur)
    tone = sweep_tone(dur, 120, 32) * np.exp(-np.arange(n) / (SR * 0.35))
    nz = lowpass(noise(n), 220) * np.exp(-np.arange(n) / (SR * 0.22)) * 0.8
    return tone + nz
write("Deep_Boom", boom())
def punch():
    n = int(SR * 0.45)
    tone = sweep_tone(0.45, 300, 60) * np.exp(-np.arange(n) / (SR * 0.09))
    nz = lowpass(noise(n), 900) * np.exp(-np.arange(n) / (SR * 0.05))
    return tone + nz * 0.7
write("Punch_Hit", punch())

# --- clicks / pops / shutter ---
def click(dur=0.09, f=2500):
    n = int(SR * dur)
    x = np.sin(2 * np.pi * f * np.arange(n) / SR) * np.exp(-np.arange(n) / (SR * 0.012))
    return x
write("UI_Click", click(0.07, 2800))
write("Pop", click(0.16, 900))
def shutter():
    n = int(SR * 0.5); x = np.zeros(n)
    c1 = click(0.09, 3200); x[:len(c1)] += c1
    c2 = click(0.09, 2400); x[int(SR * 0.16):int(SR * 0.16) + len(c2)] += c2 * 0.9
    return x
write("Camera_Shutter", shutter())

# --- sub drop ---
write("Sub_Drop", sweep_tone(1.1, 220, 38) * np.linspace(1, 0.25, int(SR * 1.1)) ** 0.7)

# --- tape stop ---
def tape_stop():
    dur = 0.8; n = int(SR * dur)
    x = sweep_tone(dur, 700, 70) * 0.6 + lowpass(noise(n), 2500) * 0.25
    return x * np.linspace(1, 0.1, n)
write("Tape_Stop", tape_stop())

# --- shimmer ---
def shimmer():
    dur = 1.6; n = int(SR * dur)
    xs = sum(np.sin(2 * np.pi * f * np.arange(n) / SR + rng.random() * 6) / (i + 1)
             for i, f in enumerate([4200, 6300, 8400, 11200]))
    return xs * env_ad(n, 0.02, 0.9)
write("Shimmer", shimmer())

# --- vinyl crackle loop (seamless-ish) ---
def vinyl():
    dur = 4.0; n = int(SR * dur)
    x = noise(n) * 0.04
    pops = rng.random(n) < 0.0006
    x[pops] += (rng.random(pops.sum()) - 0.3) * 0.5
    x = highpass(x, 1200) + lowpass(noise(n), 500) * 0.02
    return x
write("Vinyl_Crackle_Loop", vinyl())

# --- reverse swell ---
def rev_swell():
    dur = 1.3; n = int(SR * dur)
    x = lowpass(noise(n), 3000)
    return (x * np.linspace(0, 1, n) ** 2)[::-1] * 0.9 + (x * np.linspace(0, 1, n) ** 2) * 0.1
write("Reverse_Swell", rev_swell())

base = os.path.dirname(OUT)
open(os.path.join(base, "README.md"), "w").write(
    "# CineVault — SFX Pack\n\n16 royalty-free sound effects, WAV 44.1kHz 16-bit mono:\n"
    "Whoosh Soft/Hard/Long, Riser Short/Long, Deep Boom, Punch Hit, UI Click, Pop,\n"
    "Camera Shutter, Sub Drop, Tape Stop, Shimmer, Vinyl Crackle Loop, Reverse Swell.\n\n"
    "Drop straight onto your timeline in CapCut, VN, Premiere, DaVinci or any editor.\n\n"
    "Commercial license included — unlimited client & monetized use. Do not resell the files.\n")
open(os.path.join(base, "LICENSE.txt"), "w").write(
    "CINEVAULT COMMERCIAL LICENSE\n===========================\nYour purchase includes a lifetime commercial license: use these SFX in unlimited\n"
    "personal and client projects, including monetized content.\nYou may NOT redistribute, resell, share, or upload the files themselves.\n(c) CineVault. All rights reserved.\n")
print("done sfx")
