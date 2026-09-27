#!/usr/bin/env python3
"""CineVault product #2 — real animated Film Grain + Light Leak overlays.
16 seamless MP4 loops (1080x1920, 24fps, 3s), built frame-by-frame with numpy."""
import os, subprocess
import numpy as np
from PIL import Image

W, H, FPS, SEC = 1080, 1920, 24, 3
N = FPS * SEC
OUT = os.path.expanduser("~/workspace/gamerod/products/gamerod-film-grain-light-leaks")
GDIR, LDIR, TDIR = (os.path.join(OUT, d) for d in ("Grain", "Leaks", "thumbs"))
for d in (GDIR, LDIR, TDIR): os.makedirs(d, exist_ok=True)
rng = np.random.default_rng(7)

def encode(frames_iter, path):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "veryfast", "-movflags", "+faststart", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames_iter:
        p.stdin.write(np.ascontiguousarray(f, dtype=np.uint8).tobytes())
    p.stdin.close(); p.wait()
    assert p.returncode == 0, path

def thumb(frame, name):
    Image.fromarray(frame).save(os.path.join(TDIR, name + ".jpg"), quality=85)

# ---------------- GRAIN ----------------
def grain_clip(name, intensity, coarse=1, dust=0, scratches=0, flicker=0, chroma=False):
    def gen():
        for i in range(N):
            if coarse > 1:
                n = rng.standard_normal((H // coarse, W // coarse)).astype(np.float32)
                n = np.repeat(np.repeat(n, coarse, 0), coarse, 1)[:H, :W]
            else:
                n = rng.standard_normal((H, W)).astype(np.float32)
            g = 128 + n * intensity
            if chroma:
                rgb = np.stack([128 + rng.standard_normal((H, W)).astype(np.float32) * intensity * 0.7] * 3, -1)
                rgb[..., 0] += n * intensity * 0.5
                frame = np.clip(rgb, 0, 255)
            else:
                frame = np.stack([g] * 3, -1)
            if dust:
                ys = rng.integers(0, H, dust); xs = rng.integers(0, W, dust)
                frame[ys, xs] = rng.choice([0, 255], dust)[:, None]
            if scratches:
                for s in range(scratches):
                    x = int(W * (0.2 + 0.6 * s / max(scratches, 1)) + 8 * np.sin(i * 0.3 + s))
                    frame[:, max(0, x - 1):x + 2] = np.clip(frame[:, max(0, x - 1):x + 2] + 40, 0, 255)
            if flicker:
                frame = frame * (1 + flicker * np.sin(i * 0.9))
            fr = np.clip(frame, 0, 255).astype(np.uint8)
            if i == N // 2: thumb(fr, name)
            yield fr
    path = os.path.join(GDIR, name + ".mp4")
    encode(gen(), path); print("grain:", name)

grain_clip("Grain_Fine_35mm", 9)
grain_clip("Grain_Medium_35mm", 16)
grain_clip("Grain_Heavy_16mm", 22, coarse=2)
grain_clip("Grain_Extra_Heavy", 30, coarse=3)
grain_clip("Grain_Dust_Specks", 14, dust=260)
grain_clip("Grain_Vertical_Scratches", 12, scratches=3)
grain_clip("Grain_Flicker", 15, flicker=0.06)
grain_clip("Grain_Chroma_Noise", 12, chroma=True)

# ---------------- LIGHT LEAKS ----------------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
nx, ny = xx / W, yy / H

def blob(cx, cy, r, color, sharp=2.2):
    d = np.sqrt((nx - cx) ** 2 + (ny - cy) ** 2)
    m = np.clip(1 - d / r, 0, 1) ** sharp
    return m[..., None] * np.array(color, np.float32)

def leak_clip(name, fn):
    def gen():
        t = np.linspace(0, 2 * np.pi, N, endpoint=False)
        for i in range(N):
            frame = fn(t[i], i)
            fr = np.clip(frame, 0, 255).astype(np.uint8)
            if i == N // 2: thumb(fr, name)
            yield fr
    path = os.path.join(LDIR, name + ".mp4")
    encode(gen(), path); print("leak:", name)

leak_clip("Leak_Amber_Sweep", lambda t, i:
    blob(0.5 + 0.55 * np.sin(t), 0.45, 0.55, (255, 150, 60)) * (0.75 + 0.25 * np.sin(3 * t)))
leak_clip("Leak_Teal_Wash", lambda t, i:
    blob(0.5 + 0.2 * np.sin(t), -0.05 + 0.1 * np.sin(2 * t), 0.7, (40, 200, 220)))
leak_clip("Leak_Magenta_Bloom", lambda t, i:
    blob(0.85, 0.12, 0.4 + 0.08 * np.sin(2 * t), (255, 60, 180)))
leak_clip("Leak_Sunset_Streak", lambda t, i:
    np.clip(1 - np.abs((nx - ny) - 0.25 * np.sin(t)) / 0.16, 0, 1)[..., None] ** 2 * np.array((255, 130, 40), np.float32))
leak_clip("Leak_Rainbow_Edge", lambda t, i:
    blob(0.02, 0.5 + 0.3 * np.sin(t), 0.45, (255, 80, 80)) + blob(0.02, 0.5 + 0.3 * np.sin(t + 2), 0.45, (80, 255, 150)) * 0.7 + blob(0.02, 0.5 + 0.3 * np.sin(t + 4), 0.45, (90, 120, 255)) * 0.7)
leak_clip("Leak_Golden_Corner", lambda t, i:
    blob(0.08, 0.94, 0.5, (255, 190, 90)) * (0.7 + 0.3 * np.sin(2 * t)))
leak_clip("Leak_Cool_Flare", lambda t, i:
    np.clip(1 - np.abs(ny - (0.42 + 0.06 * np.sin(t))) / 0.05, 0, 1)[..., None] ** 3 * np.array((150, 200, 255), np.float32) * 0.9)
leak_clip("Leak_Neon_Drift", lambda t, i:
    blob(0.3 + 0.25 * np.sin(t), 0.6, 0.35, (255, 70, 160)) + blob(0.7 + 0.25 * np.sin(t + 3.1), 0.35, 0.35, (60, 220, 255)))

open(os.path.join(OUT, "README.md"), "w").write(
    "# CineVault — Film Grain + Light Leaks\n\n16 animated overlay loops (1080x1920, 24fps, 3s seamless).\n"
    "8 film grains + 8 light leaks, MP4 H.264.\n\n## How to use\n"
    "1. Place the overlay on a video track ABOVE your footage.\n"
    "2. Set its blend mode to **Screen** (grain also works on Overlay at low opacity).\n"
    "3. Dial opacity: grain 30–60%, leaks 40–80%. Loop as needed.\n"
    "Works in CapCut, VN, Premiere Pro, DaVinci Resolve, Final Cut.\n\nCommercial license included — unlimited client & monetized use. Do not resell the files.\n")
open(os.path.join(OUT, "LICENSE.txt"), "w").write(
    "CINEVAULT COMMERCIAL LICENSE\n===========================\nYour purchase includes a lifetime commercial license: use these overlays in unlimited\n"
    "personal and client projects, including monetized content.\nYou may NOT redistribute, resell, share, or upload the files themselves.\n(c) CineVault. All rights reserved.\n")
print("done grain+leaks")
