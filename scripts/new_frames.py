"""Two more Wall Art frames: Rustic Antique and Baroque Black.

Rustic Antique: CC0 worn cabinet wood from Poly Haven (tex/wood_cabinet_worn_long.jpg), stepped profile,
grime in the hollows, rubbed-through edges, dents and scratches, a thin antique-gilt fillet by the picture.

Baroque Black: a full 2-D height map (profile + carved ornament: corner cartouches with acanthus leaves,
C-scrolls and a rosette, shell cartouches at the middle of each rail, an egg-and-dart band and a pearl row),
lit as black lacquer: dark body, sharp highlights, a soft sheen and a hint of room reflection.
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, distance_transform_edt, zoom
import real_frames as rf
from real_frames import W, H, XX, YY, LIGHT, HALF, INWARD, ring, smooth, bump, sample, load_tex

OUT = rf.OUT


# ============================================================== Rustic Antique
def rustic_profile(u):
    h = 0.55 * smooth(0.0, 0.08, u) + 0.25                      # rounded outer edge
    h = h + 0.10 * bump(u, 0.20, 0.10)                          # raised outer band
    h = np.where((u > 0.30) & (u < 0.58), 0.45 - 0.22 * bump(u, 0.44, 0.14), h)   # wide scoop
    h = np.where((u >= 0.58) & (u < 0.80), 0.40 + 0.45 * bump(u, 0.69, 0.11), h)  # rounded ridge
    h = np.where((u >= 0.80) & (u < 0.90), 0.38, h)                               # inner flat
    h = np.where(u >= 0.90, 0.30 + 0.12 * bump(u, 0.95, 0.05), h)                 # fillet bead
    return h


def paint_rustic(img, width, tex, depth=16.0):
    mask, d, side, mitre = ring((0, 0, W, H), width)
    u = np.clip(d / width, 0, 1)
    eps = 1.0 / width
    prof = rustic_profile(u)
    dh = (rustic_profile(np.clip(u + eps, 0, 1)) - rustic_profile(np.clip(u - eps, 0, 1))) / (2 * eps)
    d2 = (rustic_profile(np.clip(u + eps, 0, 1)) - 2 * prof + rustic_profile(np.clip(u - eps, 0, 1))) / eps ** 2
    g = INWARD[side] * (dh * depth / width)[..., None]
    n = np.dstack([-g[..., 0], -g[..., 1], np.ones_like(u)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    diff = np.clip((n * LIGHT).sum(-1), 0, 1)
    spec = np.clip((n * HALF).sum(-1), 0, 1) ** 40

    texr = np.rot90(tex)
    col = np.zeros((H, W, 3), np.float32)
    offs = [(211, 640), (1350, 90), (700, 1330), (1560, 400)]
    for s in range(4):
        m = mask & (side == s)
        ro, co = offs[s]
        col[m] = sample(texr, d[m] * 0.8 + ro, XX[m] * 0.8 + co) if s < 2 else sample(tex, YY[m] * 0.8 + ro, d[m] * 0.8 + co)
    col = col * np.array([0.92, 0.86, 0.80], np.float32)          # slightly deeper, warmer stain

    rng = np.random.default_rng(21)
    along = np.where(side < 2, XX, YY)
    # rubbed-through wear on convex high points and the outer edge, broken up by noise
    wear_noise = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), 3) * 2.2
    convex = np.clip(-d2 / 60, 0, 1)
    wear = np.clip(convex * 0.9 + np.exp(-(u / 0.04) ** 2) * 0.8 + wear_noise * 0.35 - 0.35, 0, 1)
    light_wood = np.array([176, 128, 82], np.float32)
    col = col * (1 - 0.55 * wear[..., None]) + light_wood * 0.55 * wear[..., None]
    # grime settles in the hollows
    concave = np.clip(d2 / 60, 0, 1)
    col *= (1 - 0.45 * concave)[..., None]
    # dents and scratches
    dents = np.zeros((H, W), np.float32)
    ys, xs = rng.integers(0, H, 700), rng.integers(0, W, 700)
    dents[ys, xs] = 1
    dents = gaussian_filter(dents, 1.4) * 14
    seeds = (rng.random((H, W)) > 0.9994).astype(np.float32)
    scr_h = gaussian_filter(seeds, (0.6, 9)) * 40        # streaks along the top/bottom rails
    scr_v = gaussian_filter(seeds, (9, 0.6)) * 40        # streaks along the side rails
    scratches = np.where(side < 2, scr_h, scr_v)
    col *= (1 - np.clip(dents + scratches * 0.5, 0, 0.5))[..., None]

    out = col * (0.40 + 0.85 * diff)[..., None] + (255 * 0.10 * spec)[..., None]
    # thin antique-gilt fillet next to the picture/mat
    fil = (u > 0.905) & (u < 0.985)
    gilt = np.array([150, 112, 56], np.float32) * (0.55 + 0.7 * diff)[..., None] + (255 * 0.35 * spec)[..., None]
    gilt *= (1 - 0.25 * np.clip(wear_noise * 0.5 + 0.3, 0, 1))[..., None]
    out = np.where(fil[..., None], gilt, out)
    out *= (1 - 0.40 * np.exp(-(mitre / 0.8) ** 2))[..., None]
    img[mask] = out[mask]
    return img


# ============================================================== Baroque Black
def tube(canvas_bin, radius):
    """Rounded ridge of the given radius along drawn centre-lines."""
    dist = distance_transform_edt(~canvas_bin)
    return np.sqrt(np.clip(radius ** 2 - dist ** 2, 0, None))


def dome(canvas_bin, height, softness=1.0):
    """Filled shapes become cushions: height grows with distance from their edge."""
    inside = distance_transform_edt(canvas_bin)
    return height * (1 - np.exp(-inside / (6 * softness)))


def corner_patch(S, mould, sc=2):
    """Top-left corner ornament height map, S x S px (drawn at 2x then reduced)."""
    N = S * sc
    lines = Image.new("L", (N, N), 0)
    fills = Image.new("L", (N, N), 0)
    grooves = Image.new("L", (N, N), 0)
    dl, df, dg = ImageDraw.Draw(lines), ImageDraw.Draw(fills), ImageDraw.Draw(grooves)
    c = mould * 0.52 * sc                       # centre of the corner square, on the moulding
    # rosette: central boss + 8 petals
    df.ellipse([c - 17 * sc, c - 17 * sc, c + 17 * sc, c + 17 * sc], fill=255)
    for k in range(8):
        a = k * np.pi / 4 + np.pi / 8
        px, py = c + np.cos(a) * 29 * sc, c + np.sin(a) * 29 * sc
        pts = []
        for t in np.linspace(0, 2 * np.pi, 24):
            ex, ey = np.cos(t) * 13 * sc, np.sin(t) * 6 * sc
            pts.append((px + ex * np.cos(a) - ey * np.sin(a), py + ex * np.sin(a) + ey * np.cos(a)))
        df.polygon(pts, fill=255)
        dg.line([(c + np.cos(a) * 19 * sc, c + np.sin(a) * 19 * sc), (px + np.cos(a) * 10 * sc, py + np.sin(a) * 10 * sc)], fill=255, width=2 * sc)
    dl.ellipse([c - 44 * sc, c - 44 * sc, c + 44 * sc, c + 44 * sc], outline=255, width=2 * sc)
    # acanthus leaves + C-scrolls running out along both rails (drawn for the top rail, mirrored on the diagonal)
    for mirror in (False, True):
        def P(x, y):
            return (y, x) if mirror else (x, y)
        yc = c
        # leaf fan
        for k, (len_, ang, off) in enumerate([(70, -0.35, -8), (84, 0.0, 0), (70, 0.35, 8)]):
            x0, y0 = c + 38 * sc, yc + off * sc
            pts = []
            for t in np.linspace(0, 1, 30):
                w_ = np.sin(t * np.pi) * 11 * sc * (1 - 0.3 * t)
                x = x0 + t * len_ * sc
                y = y0 + np.sin(ang) * t * len_ * sc
                pts.append((x, y - w_))
            for t in np.linspace(1, 0, 30):
                w_ = np.sin(t * np.pi) * 11 * sc * (1 - 0.3 * t)
                x = x0 + t * len_ * sc
                y = y0 + np.sin(ang) * t * len_ * sc
                pts.append((x, y + w_))
            df.polygon([P(*p) for p in pts], fill=255)
            vein = [P(x0 + t * len_ * sc, y0 + np.sin(ang) * t * len_ * sc) for t in np.linspace(0.05, 0.9, 12)]
            dg.line(vein, fill=255, width=2 * sc)
        # C-scroll: S-curve ending in spirals
        xs = np.linspace(c + 110 * sc, S * sc - 12 * sc, 60)
        span = xs[-1] - xs[0]
        ys = yc + np.sin((xs - xs[0]) / span * 2 * np.pi) * 16 * sc
        dl.line([P(x, y) for x, y in zip(xs, ys)], fill=255, width=3 * sc)
        for (sx, sy, rot) in [(xs[0], ys[0], 1), (xs[-1], ys[-1], -1)]:
            th = np.linspace(0, 3.2 * np.pi, 80)
            r = (14 - 11 * th / th[-1]) * sc
            spx = sx + rot * r * np.cos(th + np.pi / 2)
            spy = sy - 14 * sc + r * np.sin(th + np.pi / 2)
            dl.line([P(a, b) for a, b in zip(spx, spy)], fill=255, width=3 * sc)
    L = np.asarray(lines) > 0
    F = np.asarray(fills) > 0
    G = np.asarray(grooves) > 0
    h = np.maximum(tube(L, 5.5 * sc), dome(F, 9 * sc))
    h -= tube(G, 1.8 * sc) * 0.8
    h = zoom(gaussian_filter(h, 0.8 * sc), 1 / sc, order=1) / sc
    return h[:S, :S]


def center_patch(Wc, mould, sc=2):
    """Shell cartouche for the middle of the top rail; Wc wide, mould tall."""
    N, M = Wc * sc, mould * sc
    lines = Image.new("L", (N, M), 0)
    fills = Image.new("L", (N, M), 0)
    grooves = Image.new("L", (N, M), 0)
    dl, df, dg = ImageDraw.Draw(lines), ImageDraw.Draw(fills), ImageDraw.Draw(grooves)
    cx, cy = N / 2, M * 0.62
    R = mould * 0.40 * sc
    df.pieslice([cx - R, cy - R, cx + R, cy + R], 180, 360, fill=255)          # shell fan
    for k in range(1, 11):
        a = np.pi + k * np.pi / 11
        dg.line([(cx, cy), (cx + np.cos(a) * R * 0.96, cy + np.sin(a) * R * 0.96)], fill=255, width=2 * sc)
    df.ellipse([cx - 9 * sc, cy - 7 * sc, cx + 9 * sc, cy + 9 * sc], fill=255)  # hinge boss
    for side_ in (-1, 1):                                                       # flanking scrolls + leaves
        th = np.linspace(0, 3 * np.pi, 90)
        r = (18 - 14 * th / th[-1]) * sc
        sx, sy = cx + side_ * (R + 26 * sc), cy - 4 * sc
        dl.line([(sx + side_ * r_ * np.cos(t), sy + r_ * np.sin(t)) for r_, t in zip(r, th)], fill=255, width=3 * sc)
        dl.line([(cx + side_ * R * 0.95, cy), (sx, sy + 18 * sc)], fill=255, width=3 * sc)
        pts = []
        for t in np.linspace(0, 1, 25):
            pts.append((sx + side_ * (22 + 60 * t) * sc, sy + 6 * sc - np.sin(t * np.pi) * 10 * sc))
        for t in np.linspace(1, 0, 25):
            pts.append((sx + side_ * (22 + 60 * t) * sc, sy + 6 * sc + np.sin(t * np.pi) * 6 * sc))
        df.polygon(pts, fill=255)
    L = np.asarray(lines) > 0
    F = np.asarray(fills) > 0
    G = np.asarray(grooves) > 0
    h = np.maximum(tube(L, 5.5 * sc), dome(F, 9 * sc))
    h -= tube(G, 1.8 * sc) * 0.9
    h = zoom(gaussian_filter(h, 0.8 * sc), 1 / sc, order=1) / sc
    return h[:mould, :Wc]


def baroque_profile(u):
    h = 0.55 * smooth(0.0, 0.07, u) + 0.35                       # rounded outer lip
    h = np.where((u > 0.10) & (u < 0.52), 0.62 - 0.30 * bump(u, 0.31, 0.21), h)   # deep cove
    h = np.where((u >= 0.52) & (u < 0.80), 0.55 + 0.40 * bump(u, 0.66, 0.14), h)  # carved torus
    h = np.where((u >= 0.80) & (u < 0.87), 0.50, h)                               # step
    h = np.where(u >= 0.87, 0.38 + 0.10 * bump(u, 0.93, 0.06), h)                 # pearl row base
    return h


def baroque_height(width, depth=22.0):
    mask, d, side, mitre = ring((0, 0, W, H), width)
    u = np.clip(d / width, 0, 1)
    along = np.where(side < 2, XX, YY)
    h = baroque_profile(u) * depth
    # egg-and-dart on the torus
    per = 26.0
    ph = np.mod(along, per) - per / 2
    egg = np.clip(1 - (ph / 9.0) ** 2 - ((u - 0.66) / 0.09) ** 2, 0, 1) ** 0.5 * 5.0
    dart = np.clip(1 - (np.abs(np.mod(along + per / 2, per) - per / 2) / 1.6) - np.abs(u - 0.66) / 0.10, 0, 1) * 3.0
    h += np.where((u > 0.55) & (u < 0.78), egg + dart, 0)
    # pearl row
    per2 = 11.0
    ph2 = np.mod(along, per2) - per2 / 2
    pearl = np.clip(1 - (ph2 / 4.2) ** 2 - ((u - 0.93) / 0.045) ** 2, 0, 1) ** 0.5 * 4.0
    h += np.where(u > 0.87, pearl, 0)
    # corner cartouches
    S = int(width * 2.3)
    cp = corner_patch(S, width)
    orn = np.zeros((H, W), np.float32)
    orn[:S, :S] = np.maximum(orn[:S, :S], cp)
    orn[:S, W - S:] = np.maximum(orn[:S, W - S:], cp[:, ::-1])
    orn[H - S:, :S] = np.maximum(orn[H - S:, :S], cp[::-1, :])
    orn[H - S:, W - S:] = np.maximum(orn[H - S:, W - S:], cp[::-1, ::-1])
    # shell cartouches mid-rail
    Wc = int(width * 3.0)
    ce = center_patch(Wc, width)
    x0 = W // 2 - Wc // 2
    orn[:width, x0:x0 + Wc] = np.maximum(orn[:width, x0:x0 + Wc], ce)
    orn[H - width:, x0:x0 + Wc] = np.maximum(orn[H - width:, x0:x0 + Wc], ce[::-1, :])
    cev = ce.T                                                        # rotate for the side rails
    y0 = H // 2 - Wc // 2
    orn[y0:y0 + Wc, :width] = np.maximum(orn[y0:y0 + Wc, :width], cev)
    orn[y0:y0 + Wc, W - width:] = np.maximum(orn[y0:y0 + Wc, W - width:], cev[:, ::-1])
    # ornament sits on the moulding: where it's present it replaces the carved band detail
    base = baroque_profile(np.full_like(u, 0.45)) * depth
    hh = np.where(orn > 0.3, np.maximum(h * 0.6, base + orn * 1.1), h)
    hh = np.where(mask, hh, 0)
    return mask, u, hh, mitre


def paint_baroque(img, width):
    mask, u, h, mitre = baroque_height(width)
    hs = gaussian_filter(h, 0.6)
    gy, gx = np.gradient(hs)
    n = np.dstack([-gx, -gy, np.ones_like(hs)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    ndl = np.clip((n * LIGHT).sum(-1), 0, 1)
    ndh = np.clip((n * HALF).sum(-1), 0, 1)
    # cavities (ambient occlusion): below the local average
    ao = np.clip((gaussian_filter(hs, 6) - hs) / 6, 0, 1)
    # lacquer: very dark body, a crisp highlight, a broad sheen, and a faint reflection of a bright room above
    body = np.array([13, 12, 14], np.float32) * (0.5 + 1.2 * ndl)[..., None]
    crisp = ndh ** 140 * 1.25
    sheen = ndh ** 14 * 0.16
    refl_y = np.clip(-n[..., 1] * 0.8 + 0.2, 0, 1)                   # normals facing up catch the bright ceiling
    fres = (1 - n[..., 2]) ** 2
    env = refl_y * fres * 0.45
    out = body + ((crisp + sheen + env) * 255)[..., None] * np.array([0.96, 0.97, 1.0], np.float32)
    out *= (1 - 0.7 * ao)[..., None]
    out *= (1 - 0.35 * np.exp(-(mitre / 0.8) ** 2))[..., None]
    img[mask] = out[mask]
    return img


# ============================================================== build
def build(fid, mould, mat, painter, mat_color, path, shadow_nomat=(18, 0.40)):
    img = np.zeros((H, W, 3), np.float32)
    img = painter(img, mould)
    b = mould + mat
    win = (b, b, W - b, H - b)
    if mat:
        img = rf.paper_mat(img, (mould, mould, W - mould, H - mould), win, mat_color)
        sh = rf.inner_shadow(win)
    else:
        sh = rf.inner_shadow(win, depth=shadow_nomat[0], strength=shadow_nomat[1])
    rgba = np.dstack([np.clip(img, 0, 255), np.full((H, W), 255, np.float32)])
    wm = (XX >= win[0]) & (XX < win[2]) & (YY >= win[1]) & (YY < win[3])
    rgba[wm] = 0
    rgba[..., 3][wm] = sh[wm] * 255
    Image.fromarray(np.nan_to_num(rgba).astype(np.uint8), "RGBA").save(path, optimize=True)
    return win


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    worn = load_tex("wood_cabinet_worn_long.jpg")
    rustic = lambda img, w: paint_rustic(img, w, worn)
    print(build("rustic-antique", 72, 64, rustic, (236, 226, 204), os.path.join(OUT, "rustic-antique.png")))
    print(build("rustic-antique", 72, 0, rustic, None, os.path.join(OUT, "rustic-antique-no-mat.png")))
    print(build("baroque-black", 120, 48, paint_baroque, (240, 236, 226), os.path.join(OUT, "baroque-black.png")))
    print(build("baroque-black", 120, 0, paint_baroque, None, os.path.join(OUT, "baroque-black-no-mat.png"),
                shadow_nomat=(22, 0.45)))
