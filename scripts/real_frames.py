"""Photo-textured, lit frame mouldings (v2 look) for all Wall Art frames.

Wood grain comes from CC0 veneer textures from Poly Haven (polyhaven.com), put in ./tex:
  oak_veneer_01.jpg, ash_veneer.jpg, walnut_veneer_02.jpg
Each moulding has a real cross-section profile, lit from the top left with a finish-specific highlight,
mitred corners with a visible seam, and (where used) a paper-textured mat with a lit bevel.
Output matches make_frames.py: 2048x1152 RGBA, opaque frame + mat, see-through window that carries
only the inner shadow. Geometry is identical to make_frames.py, so frames.json does not change.
"""
import os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

W, H = 2048, 1152
HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
OUT = os.path.join(HERE, "out_v2")
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
LIGHT = np.array([-0.45, -0.65, 0.62], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)
INWARD = np.array([[0, 1], [0, -1], [1, 0], [-1, 0]], np.float32)   # top, bottom, left, right


# ------------------------------------------------------------------ helpers
def load_tex(name, grain="vertical"):
    t = np.asarray(Image.open(os.path.join(TEX, name)).convert("RGB"), np.float32)
    return np.ascontiguousarray(np.rot90(t)) if grain == "horizontal" else t


def sample(tex, rows, cols):
    h, w, _ = tex.shape
    return np.stack([map_coordinates(tex[..., k], [np.mod(rows, h - 1), np.mod(cols, w - 1)], order=1, mode="wrap")
                     for k in range(3)], -1)


def ring(outer, width):
    x0, y0, x1, y1 = outer
    stack = np.stack([YY - y0, (y1 - 1) - YY, XX - x0, (x1 - 1) - XX])
    inside = (stack >= 0).all(0)
    d, side = stack.min(0), stack.argmin(0)
    srt = np.sort(stack, axis=0)
    return inside & (d < width), d, side, srt[1] - srt[0]


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def bump(u, c, w):
    return np.clip(1 - ((u - c) / w) ** 2, 0, 1) ** 0.5


# ------------------------------------------------------------------ profiles: u = 0 outer .. 1 inner
def oak_profile(u):
    outer = np.clip(u / 0.10, 0, 1) ** 0.5 * 0.55
    crown = 0.55 + 0.45 * np.clip(np.sin(np.clip((u - 0.05) / 0.72, 0, 1) * np.pi), 0, 1) ** 0.8
    h = np.where(u < 0.10, outer, crown)
    step = 0.48 + 0.08 * np.cos(np.clip((u - 0.80) / 0.20, 0, 1) * np.pi)
    return np.where(u > 0.80, np.minimum(h, step), h)


def gallery_profile(u):
    """Slim flat-faced gallery moulding with eased edges and a small inner lip."""
    return 0.7 * smooth(0.0, 0.18, u) + 0.3 - 0.35 * smooth(0.82, 1.0, u)


def gold_profile(u):
    """Classic stepped gilt moulding: outer bead, cove, big torus, flat, inner bead."""
    h = 0.35 + 0.30 * bump(u, 0.09, 0.09)                     # outer bead
    h = np.where((u > 0.18) & (u < 0.34), 0.30 + 0.10 * (1 - bump(u, 0.26, 0.08)), h)  # cove
    h = np.where((u >= 0.34) & (u < 0.76), 0.40 + 0.60 * bump(u, 0.55, 0.21), h)       # torus
    h = np.where((u >= 0.76) & (u < 0.86), 0.42, h)                                     # flat
    h = np.where(u >= 0.86, 0.30 + 0.22 * bump(u, 0.92, 0.06), h)                       # inner bead
    return h


def floater_profile(u):
    """Floater: flat top with a rounded outer edge, then a vertical inner wall down to the gap."""
    return 0.8 * smooth(0.0, 0.2, u) + 0.2 - 0.95 * smooth(0.72, 0.98, u)


# ------------------------------------------------------------------ finishes
def lum_of(c):
    l = c @ np.array([0.299, 0.587, 0.114], np.float32)
    return l / (l[l > 0].mean() + 1e-6)          # normalise over the moulding only (rest of the canvas is 0)


def finish_natural(c, u, diff, spec, **_):
    return c * (0.42 + 0.78 * diff)[..., None] + (255 * 0.22 * spec)[..., None]


def finish_black(c, u, diff, spec, **_):
    grain = 1 + (lum_of(c) - 1) * 2.5                       # faint open grain under satin black paint
    base = np.array([20, 19, 21], np.float32) * grain.clip(0.5, 1.6)[..., None]
    base = base * (0.60 + 0.55 * diff)[..., None]
    return base + (255 * 0.13 * spec ** 0.7)[..., None] * np.array([0.95, 0.96, 1.0], np.float32)


def finish_walnut(c, u, diff, spec, **_):
    grain = 1 + (lum_of(c) - 1) * 3.0                       # oiled walnut: dark, strong figure
    rich = np.array([74, 46, 31], np.float32) * grain.clip(0.35, 1.9)[..., None]
    return rich * (0.50 + 0.70 * diff)[..., None] + (255 * 0.14 * spec ** 0.8)[..., None]


def finish_gold(c, u, diff, spec, along=None, **_):
    dark = np.array([96, 62, 22], np.float32)
    mid = np.array([190, 142, 58], np.float32)
    hi = np.array([255, 232, 160], np.float32)
    t = diff[..., None]
    col = dark * (1 - t) + mid * t
    col = col + hi * (spec ** 0.7)[..., None] * 0.85
    # gilding: fine burnish noise and slightly rubbed high points
    col *= (1 + c)[..., None]
    # bead decoration along the outer bead and inner bead
    if along is not None:
        beads = 0.5 + 0.5 * np.cos(along / 5.0 * np.pi)
        outer_bead = np.exp(-((u - 0.09) / 0.07) ** 2)
        inner_bead = np.exp(-((u - 0.92) / 0.05) ** 2)
        col *= (1 - 0.22 * beads * (outer_bead + inner_bead))[..., None]
    cove = np.exp(-((u - 0.26) / 0.06) ** 2)
    col *= (1 - 0.30 * cove)[..., None]
    return col


# ------------------------------------------------------------------ painting
def paint_moulding(img, width, profile, depth, finish, tex=None, finish_px=None):
    mask, d, side, mitre = ring((0, 0, W, H), width)
    u = np.clip(d / width, 0, 1)
    eps = 1.0 / width
    dh = (profile(np.clip(u + eps, 0, 1)) - profile(np.clip(u - eps, 0, 1))) / (2 * eps)
    slope = dh * depth / width
    g = INWARD[side] * slope[..., None]
    n = np.dstack([-g[..., 0], -g[..., 1], np.ones_like(slope)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    diff = np.clip((n * LIGHT).sum(-1), 0, 1)
    spec = np.clip((n * HALF).sum(-1), 0, 1) ** 60
    along = np.where(side < 2, XX, YY)

    if tex is not None:
        texr = np.rot90(tex)
        offs = [(137, 911), (1203, 305), (563, 1471), (1719, 77)]
        col = np.zeros((H, W, 3), np.float32)
        for s in range(4):
            m = mask & (side == s)
            ro, co = offs[s]
            col[m] = (sample(texr, d[m] + ro, XX[m] + co) if s < 2 else sample(tex, YY[m] + ro, d[m] + co))
        c = col
    else:   # untextured finish (gold): pass a fine burnish noise instead
        rng = np.random.default_rng(5)
        c = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), (0.8, 0.8)) * 0.05 \
            + gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), 12) * 0.08
    out = finish(c, u, diff, spec, along=along)
    out *= (1 - 0.18 * np.exp(-(u / 0.03) ** 2))[..., None]                 # darker outer edge
    out *= (1 - 0.35 * np.exp(-(mitre / 0.7) ** 2))[..., None]              # mitre seam
    img[mask] = out[mask]
    return img


def paper_mat(img, mat_box, win, color, bevel=7):
    x0, y0, x1, y1 = mat_box
    rng = np.random.default_rng(3)
    m = (XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)
    grain = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), 0.7) * 2.2
    fibre = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), (0.8, 6)) * 1.6
    blotch = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), 40) * 25
    paper = np.array(color, np.float32) + (grain + fibre + blotch)[..., None]
    img[m] = paper[m]
    dl, dt, dr, db = XX - x0, YY - y0, x1 - XX, y1 - YY
    sh = np.exp(-dt / 14) * 0.30 + np.exp(-dl / 14) * 0.22 + np.exp(-db / 6) * 0.08 + np.exp(-dr / 6) * 0.10
    img *= (1 - np.clip(sh, 0, 0.45) * m)[..., None]
    wx0, wy0, wx1, wy1 = win
    bm, bd, bs, bmitre = ring((wx0 - bevel, wy0 - bevel, wx1 + bevel, wy1 + bevel), bevel)
    face = {0: (0, -0.7), 1: (0, 0.7), 2: (-0.7, 0), 3: (0.7, 0)}
    lum = np.zeros((H, W), np.float32)
    for s, (fx, fy) in face.items():
        nv = np.array([fx, fy, 0.7], np.float32)
        nv /= np.linalg.norm(nv)
        lum[bs == s] = 0.72 + 0.34 * max(0.0, float(nv @ LIGHT))
    bcol = np.array([252, 250, 244], np.float32) * lum[..., None]
    bcol *= (1 - np.exp(-(bmitre / 0.6) ** 2) * 0.12)[..., None]
    bcol *= (1 - np.exp(-((bd - (bevel - 0.5)) / 0.6) ** 2) * 0.18)[..., None]
    img[bm] = bcol[bm]
    return img


def floater_gap(img, box, win):
    """Dark recess between a floater moulding and the photo."""
    x0, y0, x1, y1 = box
    m = (XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)
    img[m] = np.array([24, 20, 18], np.float32)
    return img


def inner_shadow(win, depth=26, strength=0.42):
    x0, y0, x1, y1 = win
    inside = ((XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)).astype(np.float32)
    dt, dl = np.clip(YY - y0, 0, None), np.clip(XX - x0, 0, None)
    db, dr = np.clip(y1 - YY, 0, None), np.clip(x1 - XX, 0, None)
    s = (np.exp(-dt / depth) + 0.75 * np.exp(-dl / depth)
         + 0.25 * np.exp(-db / (depth * 0.4)) + 0.3 * np.exp(-dr / (depth * 0.4)))
    return np.clip(s * strength, 0, 0.7) * inside


def build(name, mould, mat, gap, spec, path):
    img = np.zeros((H, W, 3), np.float32)
    img = paint_moulding(img, mould, spec["profile"], spec["depth"], spec["finish"], spec.get("tex"))
    b = mould + mat + gap
    win = (b, b, W - b, H - b)
    if mat:
        img = paper_mat(img, (mould, mould, W - mould, H - mould), win, spec["mat_color"])
        sh = inner_shadow(win)
    elif gap:
        img = floater_gap(img, (mould, mould, W - mould, H - mould), win)
        sh = inner_shadow(win, depth=8, strength=0.22)
    else:
        sh = inner_shadow(win, depth=16, strength=0.38)
    rgba = np.dstack([np.clip(img, 0, 255), np.full((H, W), 255, np.float32)])
    wm = (XX >= win[0]) & (XX < win[2]) & (YY >= win[1]) & (YY < win[3])
    rgba[wm] = 0
    rgba[..., 3][wm] = sh[wm] * 255
    Image.fromarray(np.nan_to_num(rgba).astype(np.uint8), "RGBA").save(path, optimize=True)
    return win


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    oak = load_tex("oak_veneer_01.jpg")
    ash = load_tex("ash_veneer.jpg", grain="horizontal")
    walnut = load_tex("walnut_veneer_02.jpg", grain="horizontal")
    SPECS = {
        "gallery-black":   dict(mould=30, mat=64, gap=0, profile=gallery_profile, depth=8, finish=finish_black,
                                tex=ash, mat_color=(244, 241, 234)),
        "natural-oak":     dict(mould=48, mat=60, gap=0, profile=oak_profile, depth=14, finish=finish_natural,
                                tex=oak, mat_color=(242, 238, 228)),
        "classic-gold":    dict(mould=60, mat=44, gap=0, profile=gold_profile, depth=18, finish=finish_gold,
                                tex=None, mat_color=(238, 232, 218)),
        "floating-walnut": dict(mould=26, mat=60, gap=6, profile=floater_profile, depth=10, finish=finish_walnut,
                                tex=walnut, mat_color=(242, 238, 228)),
    }
    for fid, s in SPECS.items():
        if fid == "floating-walnut":
            wins = [build(fid, s["mould"], 0, s["gap"], s, os.path.join(OUT, "floating-walnut.png")),
                    build(fid, s["mould"], s["mat"], 0, s, os.path.join(OUT, "floating-walnut-mat.png"))]
        else:
            wins = [build(fid, s["mould"], s["mat"], 0, s, os.path.join(OUT, fid + ".png")),
                    build(fid, s["mould"], 0, 0, s, os.path.join(OUT, fid + "-no-mat.png"))]
        print(fid, wins)
