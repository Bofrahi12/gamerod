#!/usr/bin/env python3
"""CineVault — generate 50 real cinematic .cube LUTs + previews + package.
Each LUT is a genuine 32^3 3D LUT built with real color math (no placeholders)."""
import os, math, zipfile
import numpy as np
from PIL import Image, ImageDraw

SIZE = 32
OUT = os.path.expanduser("~/workspace/gamerod/products/cinevault-50-cinematic-luts")
LUTDIR = os.path.join(OUT, "LUTs")
os.makedirs(LUTDIR, exist_ok=True)

# ---------- color ops ----------
def luma(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722

def grade(a, p):
    x = a.copy()
    x = x * (2.0 ** p.get("ev", 0.0))                                  # exposure
    x[..., 0] *= p.get("wr", 1.0); x[..., 1] *= p.get("wg", 1.0); x[..., 2] *= p.get("wb", 1.0)  # WB
    c = p.get("contrast", 0.0)                                          # smooth S-curve
    x = x + c * (x - 0.5) * (1.0 - (2 * x - 1) ** 2)
    to = p.get("tealorange", 0.0)                                       # teal shadows / orange highlights
    if to:
        lum = luma(x)[..., None]
        sh = (1 - lum) ** 2; hi = lum ** 2
        x = x + to * (sh * np.array([-0.055, 0.028, 0.048]) + hi * np.array([0.075, 0.028, -0.048]))
    s = p.get("sat", 1.0)                                              # saturation
    if s != 1.0:
        l = luma(x)[..., None]; x = l + s * (x - l)
    vib = p.get("vib", 0.0)                                            # vibrance (protects saturated)
    if vib:
        l = luma(x)[..., None]; sat = np.abs(x - l).mean(-1, keepdims=True)
        x = l + (1 + vib * (1 - np.clip(sat * 3, 0, 1))) * (x - l)
    st = p.get("splittone")                                            # (shadow_rgb, hi_rgb, amt)
    if st:
        (sr, sg, sb), (hr, hg, hb), amt = st
        lum = luma(x)[..., None]
        tint = (1 - lum) * np.array([sr, sg, sb]) + lum * np.array([hr, hg, hb])
        x = x * (1 - amt) + (x * 0.82 + tint * 0.35) * amt
    f = p.get("fade", 0.0)                                             # lifted film blacks
    if f:
        lum = luma(x)[..., None]
        x = x * (1 - f * 0.22) + f * (0.055 + 0.045 * (1 - lum))
    if p.get("bw"):                                                    # black & white + tint
        l = luma(x)[..., None]
        tint = np.array(p.get("bw_tint", [1.0, 1.0, 1.0]))
        x = np.clip(l * tint * p.get("bw_gain", 1.0), 0, 1)
        x = x + p.get("contrast", 0.0) * 0.4 * (x - 0.5) * (1.0 - (2 * x - 1) ** 2)
    if p.get("skin", 0.0):                                             # skin-tone protection
        r, g, b = x[..., 0], x[..., 1], x[..., 2]
        mask = ((r > g) & (g > b) & (r > 0.30) & ((r - g) < 0.38) & ((g - b) < 0.30)).astype(float)[..., None]
        x = a * (mask * p["skin"]) + x * (1 - mask * p["skin"])
    return np.clip(x, 0, 1)

# ---------- 50 recipes: 10 families x 5 variants ----------
F = []
def fam(name, base, variants):
    for vname, over in variants:
        p = dict(base); p.update(over)
        F.append((f"{name} {vname}", p))

V = lambda *o: o
fam("Teal Orange", dict(tealorange=1.0, contrast=0.55, sat=1.12, skin=0.55),
    [("Standard", {}), ("Soft", dict(tealorange=0.6, contrast=0.35)),
     ("Intense", dict(tealorange=1.5, contrast=0.8, sat=1.25)),
     ("Warm Skin", dict(tealorange=0.8, skin=0.85, wr=1.04)),
     ("Deep Night", dict(tealorange=1.2, ev=-0.25, contrast=0.7))])
fam("Golden Travel", dict(wr=1.07, wb=0.93, contrast=0.4, sat=1.15, fade=0.25, skin=0.5),
    [("Standard", {}), ("Soft", dict(fade=0.45, contrast=0.25)),
     ("Intense", dict(wr=1.12, wb=0.88, sat=1.3, contrast=0.55)),
     ("Desert Sun", dict(wr=1.12, wg=1.02, wb=0.86, ev=0.15)),
     ("Amber Glow", dict(splittone=((0.30,0.16,0.05),(0.55,0.38,0.18),0.5), fade=0.3))])
fam("Moody", dict(sat=0.82, contrast=0.5, tealorange=0.5, fade=0.35, wb=1.04, skin=0.6),
    [("Standard", {}), ("Soft", dict(fade=0.55, contrast=0.3)),
     ("Intense", dict(sat=0.7, contrast=0.7, ev=-0.15)),
     ("Forest", dict(wg=1.05, wb=1.02, tealorange=0.8)),
     ("Rainy Day", dict(wb=1.08, wr=0.96, sat=0.75, ev=-0.1))])
fam("Noir", dict(bw=True, contrast=0.6, skin=0.4),
    [("Standard", {}), ("Soft", dict(contrast=0.35, fade=0.3)),
     ("High Contrast", dict(contrast=1.0, ev=-0.1)),
     ("Warm Tint", dict(bw_tint=[1.06,0.98,0.88], fade=0.25)),
     ("Cold Tint", dict(bw_tint=[0.92,0.98,1.08], contrast=0.7))])
fam("Vintage Film", dict(fade=0.6, wr=1.05, wb=0.95, sat=0.9, contrast=0.3, skin=0.5),
    [("Standard", {}), ("70s Warm", dict(wr=1.1, wb=0.9, sat=0.85)),
     ("Faded Cool", dict(wb=1.05, wr=0.97, fade=0.8)),
     ("Cross Process", dict(wg=1.06, wb=0.94, contrast=0.5, sat=1.05)),
     ("Sepia Light", dict(sat=0.55, wr=1.08, wb=0.9, fade=0.5))])
fam("Clean Natural", dict(contrast=0.3, sat=1.06, vib=0.25, skin=0.7),
    [("Standard", {}), ("Bright Airy", dict(ev=0.2, fade=0.25, sat=1.0)),
     ("Punchy", dict(contrast=0.5, sat=1.18, vib=0.35)),
     ("Soft Portrait", dict(contrast=0.18, skin=0.9, wr=1.03)),
     ("Vivid Pop", dict(sat=1.3, vib=0.4, contrast=0.42))])
fam("Neon Night", dict(tealorange=0.7, sat=1.35, contrast=0.65, ev=-0.1, vib=0.3, skin=0.5),
    [("Standard", {}), ("Cyberpunk", dict(splittone=((0.05,0.25,0.35),(0.45,0.10,0.35),0.55), sat=1.5)),
     ("Sodium Street", dict(wr=1.1, wb=0.9, splittone=((0.35,0.18,0.02),(0.5,0.3,0.1),0.4))),
     ("Midnight Blue", dict(wb=1.12, wr=0.94, ev=-0.2, contrast=0.75)),
     ("Club Energy", dict(sat=1.5, contrast=0.7, tealorange=1.0))])
fam("Airy Wedding", dict(ev=0.25, fade=0.5, wr=1.05, wb=0.97, sat=0.95, contrast=0.2, skin=0.8),
    [("Standard", {}), ("Blush", dict(splittone=((0.4,0.25,0.25),(0.55,0.45,0.4),0.35))),
     ("Golden Hour", dict(wr=1.1, wb=0.92, ev=0.3)),
     ("Classic White", dict(sat=0.9, fade=0.6, contrast=0.15)),
     ("Romantic Soft", dict(fade=0.7, sat=0.88, vib=0.2))])
fam("Desert Earth", dict(wr=1.08, wg=1.0, wb=0.9, contrast=0.45, sat=1.12, tealorange=0.3, skin=0.55),
    [("Standard", {}), ("Dune", dict(wr=1.12, wb=0.86, fade=0.3)),
     ("Clay", dict(splittone=((0.35,0.2,0.1),(0.55,0.38,0.2),0.4))),
     ("Oasis", dict(wg=1.06, tealorange=0.6, sat=1.2)),
     ("Sunset", dict(wr=1.14, wb=0.88, ev=0.1, sat=1.25))])
fam("Ocean", dict(wb=1.08, wr=0.95, tealorange=0.9, sat=1.18, contrast=0.45, skin=0.55),
    [("Standard", {}), ("Deep Dive", dict(wb=1.15, wr=0.9, ev=-0.12, contrast=0.6)),
     ("Tropical", dict(wg=1.07, wb=1.1, sat=1.3, ev=0.12)),
     ("Aqua Clean", dict(sat=1.1, fade=0.25, contrast=0.3)),
     ("Storm Sea", dict(sat=0.9, contrast=0.6, wb=1.1, fade=0.2))])

assert len(F) == 50, len(F)

# ---------- build lattice & write .cube ----------
lin = np.linspace(0, 1, SIZE)
bb, gg, rr = np.meshgrid(lin, lin, lin, indexing="ij")   # [B,G,R], R fastest -> correct .cube order
base = np.stack([rr, gg, bb], axis=-1)

luts = {}
for i, (name, p) in enumerate(F, 1):
    out = grade(base, p)
    luts[f"CineVault_{i:02d}_{name.replace(' ','_')}"] = out
    lines = [f'TITLE "{name}"', "LUT_3D_SIZE 32", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    flat = out.reshape(-1, 3)
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in flat]
    fn = f"CineVault_{i:02d}_{name.replace(' ','_')}.cube"
    with open(os.path.join(LUTDIR, fn), "w") as fh:
        fh.write("\n".join(lines))
print(f"Wrote {len(luts)} .cube files")

# validate: read one back
with open(os.path.join(LUTDIR, os.listdir(LUTDIR)[0])) as fh:
    txt = fh.read().splitlines()
data = [l for l in txt if l and not l.startswith(("TITLE", "LUT_3D", "DOMAIN"))]
assert len(data) == SIZE ** 3, f"bad lattice: {len(data)}"
vals = np.array([[float(v) for v in l.split()] for l in data])
assert vals.min() >= 0 and vals.max() <= 1 and not np.isnan(vals).any()
print("Validation OK: 32768 entries, range [0,1], no NaN")

# ---------- test chart + trilinear apply + contact sheet ----------
W, H = 480, 270
chart = np.zeros((H, W, 3))
xs = np.linspace(0, 1, W)
chart += xs[None, :, None] * np.array([1, 1, 1]) * 0.0
# gradient bands
for b in range(6):
    y0, y1 = b * H // 6, (b + 1) * H // 6
    hue = np.array([[1, 0.15, 0.1], [1, 0.6, 0.1], [0.15, 0.75, 0.2],
                    [0.15, 0.6, 1], [0.6, 0.2, 1], [0.5, 0.5, 0.5]][b])
    chart[y0:y1] = xs[None, :, None] * hue + (1 - xs[None, :, None]) * 0.08
# skin-tone patches
skin = np.array([[0.85, 0.62, 0.48], [0.72, 0.5, 0.38], [0.55, 0.36, 0.26], [0.38, 0.24, 0.17]])
for k, c in enumerate(skin):
    chart[8:58, 8 + k * 56:58 + k * 56] = c

def apply_lut(img, lut):
    S = lut.shape[0]
    x = np.clip(img[..., 0] * (S - 1), 0, S - 1)
    y = np.clip(img[..., 1] * (S - 1), 0, S - 1)
    z = np.clip(img[..., 2] * (S - 1), 0, S - 1)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); z0 = np.floor(z).astype(int)
    x1 = np.clip(x0 + 1, 0, S - 1); y1 = np.clip(y0 + 1, 0, S - 1); z1 = np.clip(z0 + 1, 0, S - 1)
    fx, fy, fz = x - x0, y - y0, z - z0
    def g(ix, iy, iz): return lut[iz, iy, ix]
    c000, c100 = g(x0, y0, z0), g(x1, y0, z0); c010, c110 = g(x0, y1, z0), g(x1, y1, z0)
    c001, c101 = g(x0, y0, z1), g(x1, y0, z1); c011, c111 = g(x0, y1, z1), g(x1, y1, z1)
    fx, fy, fz = fx[..., None], fy[..., None], fz[..., None]
    c00 = c000 * (1 - fx) + c100 * fx; c01 = c001 * (1 - fx) + c101 * fx
    c10 = c010 * (1 - fx) + c110 * fx; c11 = c011 * (1 - fx) + c111 * fx
    c0 = c00 * (1 - fy) + c10 * fy; c1 = c01 * (1 - fy) + c11 * fy
    return np.clip(c0 * (1 - fz) + c1 * fz, 0, 1)

thumbs = []
for key, lut in luts.items():
    t = apply_lut(chart, lut)
    thumbs.append((key, (t * 255).astype(np.uint8)))
# contact sheet 5 cols
cols, tw, th = 5, 240, 150
rows = math.ceil(len(thumbs) / cols)
sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (10, 12, 18))
dr = ImageDraw.Draw(sheet)
for i, (key, arr) in enumerate(thumbs):
    im = Image.fromarray(arr).resize((tw, th))
    sheet.paste(im, ((i % cols) * tw, (i // cols) * (th + 22)))
    dr.text(((i % cols) * tw + 6, (i // cols) * (th + 22) + th + 4), key.replace("CineVault_", "").replace("_", " ")[:28], fill=(200, 205, 220))
sheet.save(os.path.join(OUT, "preview-contact-sheet.jpg"), quality=88)
print("Contact sheet saved")

# ---------- docs ----------
open(os.path.join(OUT, "LICENSE.txt"), "w").write(
    "CINEVAULT COMMERCIAL LICENSE\n===========================\n"
    "Your purchase includes a lifetime commercial license: use these LUTs in unlimited\n"
    "personal and client projects, including monetized content (YouTube, TikTok, ads).\n"
    "You may NOT redistribute, resell, share, or upload the .cube files themselves.\n(c) CineVault. All rights reserved.\n")
open(os.path.join(OUT, "INSTALL_GUIDE.md"), "w").write(
    "# Install Guide — CineVault 50 Cinematic LUTs\n\n"
    "All files are standard `.cube` LUTs — they work anywhere LUTs are supported.\n\n"
    "## CapCut (mobile & desktop)\n1. Import your clip → Adjust → LUT (mobile) / Filters → LUT (desktop)\n"
    "2. Tap import / + and choose a `.cube` file. Done.\n\n"
    "## VN (mobile)\n1. Filter → Custom → Import → choose the `.cube` file.\n\n"
    "## Premiere Pro\n1. Effects → Lumetri Color → Creative → Browse → pick the `.cube`.\n"
    "2. Or: Lumetri → Basic Correction → Input LUT.\n\n"
    "## DaVinci Resolve\n1. Project Settings → Color Management → Lookup Tables → Open LUT Folder.\n"
    "2. Copy the `.cube` files there → Update Lists → apply from the LUTs panel.\n\n"
    "## Final Cut Pro\nUse the free mLUT loader (or any LUT utility) → load `.cube`.\n\n"
    "## Tips\n- LUTs are a starting point: adjust Intensity/opacity to taste (70–90% often looks best).\n"
    "- Every camera exposes differently — nudge exposure before the LUT, not after.\n"
    "- Skin tones are protected in these grades, but check faces on every new scene.\n")

# ---------- zip ----------
zpath = os.path.expanduser("~/workspace/gamerod/products/cinevault-50-cinematic-luts.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, _, fns in os.walk(OUT):
        for fn in sorted(fns):
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, os.path.dirname(OUT)))
print("ZIP:", zpath, f"{os.path.getsize(zpath)/1e6:.1f} MB")
