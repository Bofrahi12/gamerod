#!/usr/bin/env python3
"""CineVault — Sony S-Log3 Cinematic Pack: 30 real .cube LUTs.
Pipeline per LUT: S-Log3 signal -> inverse S-Log3 OETF (scene-linear, S-Gamut3)
-> S-Gamut3-to-Rec.709 matrix -> Rec.709 OETF (display-referred) -> creative grade.
Uses Sony's published S-Log3 spec anchors (18% gray -> CV420, black -> CV95).
"""
import os, math, zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SIZE = 32
OUT = os.path.expanduser("~/workspace/gamerod/products/cinevault-sony-slog3-luts")
LUTDIR = os.path.join(OUT, "LUTs")
os.makedirs(LUTDIR, exist_ok=True)

# ---------- S-Log3 (Sony published spec) ----------
def slog3_inverse(y):
    """S-Log3 signal (0..1) -> scene-linear reflectance (S-Gamut3)."""
    y10 = np.asarray(y, dtype=float) * 1023.0
    log_part = np.power(10.0, (y10 - 420.0) / 261.5) * 0.19 - 0.01
    lin_part = (y10 - 95.0) * 0.01125 / (171.2102946929 - 95.0)
    return np.where(y10 >= 171.2102946929, log_part, lin_part)

def slog3_forward(x):
    """Scene-linear reflectance -> S-Log3 signal (0..1). For preview simulation."""
    x = np.clip(np.asarray(x, dtype=float), 0, None)
    log_part = (420.0 + 261.5 * np.log10((x + 0.01) / 0.19)) / 1023.0
    lin_part = (95.0 + x * (171.2102946929 - 95.0) / 0.01125) / 1023.0
    return np.where(x >= 0.01125, log_part, lin_part)

# ---------- gamut matrices (normalized primary matrix) ----------
def rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, wx, wy):
    def xyz(px, py):
        return np.array([px / py, 1.0, (1 - px - py) / py])
    P = np.stack([xyz(rx, ry), xyz(gx, gy), xyz(bx, by)], axis=1)
    W = xyz(wx, wy)
    S = np.linalg.solve(P, W)
    return P * S  # RGB -> XYZ

M_SG3 = rgb_to_xyz_matrix(0.730, 0.280, 0.140, 0.855, 0.100, -0.050, 0.3127, 0.3290)
M_709 = rgb_to_xyz_matrix(0.640, 0.330, 0.300, 0.600, 0.150, 0.060, 0.3127, 0.3290)
M_SG3_TO_709 = np.linalg.inv(M_709) @ M_SG3   # scene-linear S-Gamut3 -> scene-linear Rec.709
M_709_TO_SG3 = np.linalg.inv(M_SG3_TO_709)

def rec709_oetf(x):
    x = np.asarray(x, dtype=float)
    return np.where(x < 0.018, 4.5 * x, 1.099 * np.power(np.clip(x, 0, None), 0.45) - 0.099)

def rec709_oetf_inv(y):
    y = np.asarray(y, dtype=float)
    return np.where(y < 0.081, y / 4.5, np.power((y + 0.099) / 1.099, 1 / 0.45))

# ---------- creative grade (same engine as the 50-LUT pack) ----------
def luma(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722

def grade(a, p):
    x = a.copy()
    x = x * (2.0 ** p.get("ev", 0.0))
    x[..., 0] *= p.get("wr", 1.0); x[..., 1] *= p.get("wg", 1.0); x[..., 2] *= p.get("wb", 1.0)
    c = p.get("contrast", 0.0)
    x = x + c * (x - 0.5) * (1.0 - (2 * x - 1) ** 2)
    to = p.get("tealorange", 0.0)
    if to:
        lum = luma(x)[..., None]
        sh = (1 - lum) ** 2; hi = lum ** 2
        x = x + to * (sh * np.array([-0.055, 0.028, 0.048]) + hi * np.array([0.075, 0.028, -0.048]))
    s = p.get("sat", 1.0)
    if s != 1.0:
        l = luma(x)[..., None]; x = l + s * (x - l)
    vib = p.get("vib", 0.0)
    if vib:
        l = luma(x)[..., None]; sat = np.abs(x - l).mean(-1, keepdims=True)
        x = l + (1 + vib * (1 - np.clip(sat * 3, 0, 1))) * (x - l)
    st = p.get("splittone")
    if st:
        (sr, sg, sb), (hr, hg, hb), amt = st
        lum = luma(x)[..., None]
        tint = (1 - lum) * np.array([sr, sg, sb]) + lum * np.array([hr, hg, hb])
        x = x * (1 - amt) + (x * 0.82 + tint * 0.35) * amt
    f = p.get("fade", 0.0)
    if f:
        lum = luma(x)[..., None]
        x = x * (1 - f * 0.22) + f * (0.055 + 0.045 * (1 - lum))
    if p.get("bw"):
        l = luma(x)[..., None]
        tint = np.array(p.get("bw_tint", [1.0, 1.0, 1.0]))
        x = np.clip(l * tint * p.get("bw_gain", 1.0), 0, 1)
        x = x + p.get("contrast", 0.0) * 0.4 * (x - 0.5) * (1.0 - (2 * x - 1) ** 2)
    if p.get("skin", 0.0):
        r, g, b = x[..., 0], x[..., 1], x[..., 2]
        mask = ((r > g) & (g > b) & (r > 0.30) & ((r - g) < 0.38) & ((g - b) < 0.30)).astype(float)[..., None]
        x = a * (mask * p["skin"]) + x * (1 - mask * p["skin"])
    return np.clip(x, 0, 1)

def slog3_pipeline(sig, creative):
    """Full LUT pipeline: S-Log3/S-Gamut3 signal -> display-referred Rec.709 + grade."""
    lin = np.clip(slog3_inverse(sig), 0, None)
    rec_lin = np.clip(lin @ M_SG3_TO_709.T, 0, None)
    rec = np.clip(rec709_oetf(rec_lin), 0, 1)
    return grade(rec, creative)

# ---------- 30 recipes ----------
F = []
def add(name, creative):
    F.append((name, creative))

add("S-Log3 to Rec709 Neutral", {})
add("S-Log3 to Rec709 Filmic", dict(contrast=0.5))
add("S-Log3 to Rec709 Soft", dict(contrast=0.25, fade=0.3))
add("S-Log3 to Rec709 Punchy", dict(contrast=0.7, sat=1.12))
add("S-Log3 to Rec709 Warm Clean", dict(wr=1.03, wb=0.98, contrast=0.35, skin=0.5))

CREATIVE = [
    ("Teal Orange Standard", dict(tealorange=1.0, contrast=0.55, sat=1.12, skin=0.55)),
    ("Teal Orange Soft", dict(tealorange=0.6, contrast=0.35, sat=1.05, skin=0.6)),
    ("Teal Orange Intense", dict(tealorange=1.5, contrast=0.8, sat=1.25, skin=0.5)),
    ("Golden Standard", dict(wr=1.07, wb=0.93, contrast=0.4, sat=1.15, fade=0.25, skin=0.5)),
    ("Golden Intense", dict(wr=1.12, wb=0.88, sat=1.3, contrast=0.55, skin=0.45)),
    ("Desert Sun", dict(wr=1.12, wg=1.02, wb=0.86, ev=0.15, contrast=0.45, sat=1.12, skin=0.55)),
    ("Moody Standard", dict(sat=0.82, contrast=0.5, tealorange=0.5, fade=0.35, wb=1.04, skin=0.6)),
    ("Moody Intense", dict(sat=0.7, contrast=0.7, ev=-0.15, tealorange=0.6, skin=0.55)),
    ("Moody Forest", dict(wg=1.05, wb=1.02, tealorange=0.8, sat=0.85, contrast=0.5, skin=0.55)),
    ("Noir Standard", dict(bw=True, contrast=0.6, skin=0.4)),
    ("Noir High Contrast", dict(bw=True, contrast=1.0, ev=-0.1)),
    ("Vintage Standard", dict(fade=0.6, wr=1.05, wb=0.95, sat=0.9, contrast=0.3, skin=0.5)),
    ("Vintage 70s Warm", dict(wr=1.1, wb=0.9, sat=0.85, fade=0.6, contrast=0.3, skin=0.5)),
    ("Clean Natural Standard", dict(contrast=0.3, sat=1.06, vib=0.25, skin=0.7)),
    ("Clean Natural Punchy", dict(contrast=0.5, sat=1.18, vib=0.35, skin=0.6)),
    ("Neon Night Standard", dict(tealorange=0.7, sat=1.35, contrast=0.65, ev=-0.1, vib=0.3, skin=0.5)),
    ("Neon Cyberpunk", dict(splittone=((0.05,0.25,0.35),(0.45,0.10,0.35),0.55), sat=1.5, contrast=0.65, skin=0.45)),
    ("Neon Midnight Blue", dict(wb=1.12, wr=0.94, ev=-0.2, contrast=0.75, sat=1.2, skin=0.5)),
    ("Airy Wedding Standard", dict(ev=0.25, fade=0.5, wr=1.05, wb=0.97, sat=0.95, contrast=0.2, skin=0.8)),
    ("Airy Golden Hour", dict(wr=1.1, wb=0.92, ev=0.3, fade=0.5, contrast=0.2, skin=0.75)),
    ("Desert Earth Standard", dict(wr=1.08, wg=1.0, wb=0.9, contrast=0.45, sat=1.12, tealorange=0.3, skin=0.55)),
    ("Desert Sunset", dict(wr=1.14, wb=0.88, ev=0.1, sat=1.25, contrast=0.45, skin=0.5)),
    ("Ocean Standard", dict(wb=1.08, wr=0.95, tealorange=0.9, sat=1.18, contrast=0.45, skin=0.55)),
    ("Ocean Tropical", dict(wg=1.07, wb=1.1, sat=1.3, ev=0.12, contrast=0.45, skin=0.5)),
    ("Ocean Deep Dive", dict(wb=1.15, wr=0.9, ev=-0.12, contrast=0.6, sat=1.15, skin=0.55)),
]
for name, p in CREATIVE:
    add(name, p)
assert len(F) == 30, len(F)

# ---------- build lattice & write .cube ----------
lin = np.linspace(0, 1, SIZE)
bb, gg, rr = np.meshgrid(lin, lin, lin, indexing="ij")
base = np.stack([rr, gg, bb], axis=-1)   # S-Log3 signal lattice

luts = {}
for i, (name, p) in enumerate(F, 1):
    out = slog3_pipeline(base, p)
    key = f"CineVault_SLog3_{i:02d}_{name.replace(' ', '_').replace('/', '_')}"
    luts[key] = out
    lines = [f'TITLE "CineVault Sony S-Log3 - {name}"', "LUT_3D_SIZE 32",
             "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in out.reshape(-1, 3)]
    with open(os.path.join(LUTDIR, key + ".cube"), "w") as fh:
        fh.write("\n".join(lines))
print(f"Wrote {len(luts)} .cube files")

# ---------- validation anchors (run after apply_lut_img is defined) ----------
def _anchors_done():
    return True

# ---------- preview: simulate S-Log3 footage, apply LUTs, contact sheet ----------
W, H = 480, 270
chart = np.zeros((H, W, 3))
xs = np.linspace(0, 1, W)
for b in range(6):
    y0, y1 = b * H // 6, (b + 1) * H // 6
    hue = np.array([[1, 0.15, 0.1], [1, 0.6, 0.1], [0.15, 0.75, 0.2],
                    [0.15, 0.6, 1], [0.6, 0.2, 1], [0.5, 0.5, 0.5]][b])
    chart[y0:y1] = xs[None, :, None] * hue + (1 - xs[None, :, None]) * 0.08
skin = np.array([[0.85, 0.62, 0.48], [0.72, 0.5, 0.38], [0.55, 0.36, 0.26], [0.38, 0.24, 0.17]])
for k, c in enumerate(skin):
    chart[8:58, 8 + k * 56:58 + k * 56] = c
# chart is display-referred -> simulate S-Log3/S-Gamut3 capture
chart_lin709 = rec709_oetf_inv(np.clip(chart, 0, 1))
chart_lin_sg = np.clip(chart_lin709 @ M_709_TO_SG3.T, 0, None)
log_input = np.clip(slog3_forward(chart_lin_sg), 0, 1)

def apply_lut_img(img, lut):
    S = lut.shape[0]
    x = np.clip(img[..., 0] * (S - 1), 0, S - 1)
    y = np.clip(img[..., 1] * (S - 1), 0, S - 1)
    z = np.clip(img[..., 2] * (S - 1), 0, S - 1)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); z0 = np.floor(z).astype(int)
    x1 = np.clip(x0 + 1, 0, S - 1); y1 = np.clip(y0 + 1, 0, S - 1); z1 = np.clip(z0 + 1, 0, S - 1)
    fx, fy, fz = (x - x0)[..., None], (y - y0)[..., None], (z - z0)[..., None]
    def g(ix, iy, iz): return lut[iz, iy, ix]
    c00 = g(x0, y0, z0) * (1 - fx) + g(x1, y0, z0) * fx
    c01 = g(x0, y0, z1) * (1 - fx) + g(x1, y0, z1) * fx
    c10 = g(x0, y1, z0) * (1 - fx) + g(x1, y1, z0) * fx
    c11 = g(x0, y1, z1) * (1 - fx) + g(x1, y1, z1) * fx
    c0 = c00 * (1 - fy) + c10 * fy
    c1 = c01 * (1 - fy) + c11 * fy
    return np.clip(c0 * (1 - fz) + c1 * fz, 0, 1)

# ---------- validation (trilinear sampling — lattice is 32^3, nearest-node is too coarse) ----------
def sample(lut, sig):
    img = np.array(sig, dtype=float).reshape(1, 1, 3)
    return apply_lut_img(img, lut)[0, 0]

neut = luts["CineVault_SLog3_01_S-Log3_to_Rec709_Neutral"]
# Anchor 1: 18% gray S-Log3 (CV420 -> 0.4106) must come out ~0.41 Rec.709 on Neutral
g18 = sample(neut, (0.4106, 0.4106, 0.4106))
assert abs(g18.mean() - 0.4102) < 0.015 and g18.std() < 0.01, f"18% gray anchor failed: {g18}"
# Anchor 2: S-Log3 black (CV95) -> ~0 ; white (1.0) -> 1.0
blk = sample(neut, (95 / 1023,) * 3)
wht = sample(neut, (1.0,) * 3)
assert blk.max() < 0.03, f"black anchor failed: {blk}"
assert wht.min() > 0.97, f"white anchor failed: {wht}"
# Anchor 3: white balance preserved — D65 gray in -> gray out
gr = sample(neut, (0.6, 0.6, 0.6))
assert gr.std() < 0.02, f"gray balance failed: {gr}"
# Anchor 4: every LUT has full lattice, finite, in range
for key, lut in luts.items():
    assert lut.shape == (SIZE, SIZE, SIZE, 3), key
    assert np.isfinite(lut).all() and lut.min() >= 0 and lut.max() <= 1, key
print("Validation OK: 30 LUTs x 32768 entries; 18%-gray/black/white/gray-balance anchors pass")

tw, th = 240, 135
log_thumb = Image.fromarray((np.clip(log_input, 0, 1) * 255).astype(np.uint8)).resize((tw, th))
cols, rows = 2, 15
sheet = Image.new("RGB", (cols * tw * 2, rows * (th + 24)), (10, 12, 18))
dr = ImageDraw.Draw(sheet)
for i, (key, lut) in enumerate(luts.items()):
    out = (np.clip(apply_lut_img(log_input, lut), 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(out).resize((tw, th))
    r, c = divmod(i, cols)
    x0 = c * tw * 2
    y0 = r * (th + 24)
    sheet.paste(log_thumb, (x0, y0))
    sheet.paste(im, (x0 + tw, y0))
    dr.text((x0 + 6, y0 + th + 5), "LOG", fill=(140, 150, 170))
    dr.text((x0 + tw + 6, y0 + th + 5), key.replace("CineVault_SLog3_", "").replace("_", " ")[:30], fill=(200, 205, 220))
sheet.save(os.path.join(OUT, "preview-contact-sheet.jpg"), quality=88)
print("Contact sheet saved")

# ---------- cover ----------
cw, ch = 1280, 720
cover = Image.new("RGB", (cw, ch), (8, 10, 16))
cd = ImageDraw.Draw(cover)
for y in range(ch):  # teal-to-warm cinematic gradient
    t = y / ch
    cd.line([(0, y), (cw, y)], fill=(int(8 + 30 * t), int(10 + 26 * t), int(16 + 40 * (1 - t))))
try:
    f_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 92)
    f_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    f_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
except OSError:
    f_big = f_mid = f_sm = ImageFont.load_default()
cd.text((70, 90), "SONY S-LOG3", font=f_big, fill=(255, 255, 255))
cd.text((70, 200), "CINEMATIC PACK", font=f_big, fill=(255, 176, 66))
cd.text((70, 330), "30 LUTs  •  S-Log3 / S-Gamut3 → Rec.709", font=f_mid, fill=(215, 220, 235))
cd.text((70, 400), "5 true conversion LUTs + 25 film looks", font=f_sm, fill=(170, 178, 195))
cd.text((70, 450), "DaVinci  •  Premiere Pro  •  Final Cut Pro", font=f_sm, fill=(170, 178, 195))
cd.text((70, 620), "CINEVAULT", font=f_mid, fill=(255, 176, 66))
cover.save(os.path.expanduser("~/workspace/gamerod/img/sony-slog3-luts.jpg"), quality=90)
print("Cover saved")

# ---------- docs ----------
open(os.path.join(OUT, "LICENSE.txt"), "w").write(
    "CINEVAULT COMMERCIAL LICENSE\n===========================\n"
    "Your purchase includes a lifetime commercial license: use these LUTs in unlimited\n"
    "personal and client projects, including monetized content (YouTube, TikTok, ads).\n"
    "You may NOT redistribute, resell, share, or upload the .cube files themselves.\n(c) CineVault. All rights reserved.\n")
open(os.path.join(OUT, "INSTALL_GUIDE.md"), "w").write(
    "# Install Guide — CineVault Sony S-Log3 Cinematic Pack\n\n"
    "These 30 `.cube` LUTs are built for **Sony S-Log3 / S-Gamut3 footage**.\n"
    "Apply them DIRECTLY to your S-Log3 clips — the conversion to Rec.709 is inside\n"
    "the LUT. Do NOT stack them on top of another S-Log3 conversion (e.g. Sony's\n"
    "official LUT or an Input Color Space transform): one conversion only.\n\n"
    "The 5 conversion LUTs (01–05) are accurate S-Log3/S-Gamut3 → Rec.709 transforms\n"
    "(verified: 18% gray -> 41% IRE, true black -> 0). The 25 creative LUTs (06–30)\n"
    "add the same film looks on top of that conversion.\n\n"
    "## DaVinci Resolve\n"
    "1. Keep your timeline color management OFF for these clips (or set Input Color\n"
    "   Space to Bypass) — the LUT does the conversion.\n"
    "2. Project Settings → Color Management → Lookup Tables → Open LUT Folder →\n"
    "   copy the `.cube` files → Update Lists → apply from the LUTs panel.\n\n"
    "## Premiere Pro\n"
    "1. Effects → Lumetri Color → Creative → Browse → pick the `.cube`.\n"
    "2. Apply on the S-Log3 clip directly (no Input LUT).\n\n"
    "## Final Cut Pro\n"
    "Use any LUT loader (e.g. mLUT) on the S-Log3 clip.\n\n"
    "## Notes\n"
    "- Built for S-Gamut3. If you shot S-Log3 with S-Gamut3.Cine, colors will shift\n"
    "  slightly — set your camera to S-Gamut3 for exact results.\n"
    "- LUTs are a starting point: adjust intensity to 70–90% to taste and nudge\n"
    "  exposure BEFORE the LUT, not after.\n")

# ---------- zip ----------
zpath = os.path.expanduser("~/workspace/gamerod/products/cinevault-sony-slog3-luts.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, _, fns in os.walk(OUT):
        for fn in sorted(fns):
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, os.path.dirname(OUT)))
print("ZIP:", zpath, f"{os.path.getsize(zpath)/1e6:.1f} MB")
