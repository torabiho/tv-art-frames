"""Generate TV Art starter frames: <id>-base.png, <id>-overlay.png, frames.json, previews."""
import json, os
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter

W, H = 2048, 1152
OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def noise(sigma, amp, shape=(H, W)):
    n = gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma)
    return n / (n.std() + 1e-6) * amp


def wall(color):
    img = np.ones((H, W, 3), np.float32) * np.array(color, np.float32)
    img += noise(1.2, 1.6)[..., None] + noise(40, 1.2)[..., None]
    # soft light falloff: brighter top-centre
    cx, cy = W / 2, H * 0.25
    d = np.sqrt(((XX - cx) / W) ** 2 + ((YY - cy) / H) ** 2)
    img *= (1.04 - 0.16 * d)[..., None]
    return img


def rect_mask(x0, y0, x1, y1):
    return ((XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)).astype(np.float32)


def drop_shadow(img, box, offset=(0, 18), blur=28, strength=0.38):
    x0, y0, x1, y1 = box
    m = rect_mask(x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1])
    m = gaussian_filter(m, blur)
    # tight contact shadow
    c = gaussian_filter(rect_mask(x0, y0 + 4, x1, y1 + 4), 5)
    s = np.clip(m * strength + c * 0.25, 0, 0.6)
    return img * (1 - s)[..., None]


def ring_coords(outer, width):
    """For pixels in the moulding ring return (mask, d, t, side).
    d = distance from outer edge (0..width), t = position along the side, side 0=top 1=bottom 2=left 3=right."""
    x0, y0, x1, y1 = outer
    dl, dr, dt, db = XX - x0, (x1 - 1) - XX, YY - y0, (y1 - 1) - YY
    inside = (dl >= 0) & (dr >= 0) & (dt >= 0) & (db >= 0)
    d = np.minimum(np.minimum(dl, dr), np.minimum(dt, db))
    mask = inside & (d < width)
    side = np.argmin(np.stack([dt, db, dl, dr]), axis=0)
    t = np.where(side < 2, XX, YY)
    return mask, d, t, side


# Light comes from the top-left: faces are lit by side
SIDE_LIGHT = np.array([1.08, 0.86, 1.0, 0.92], np.float32)


def paint_moulding(img, outer, width, profile_fn, texture=None):
    mask, d, t, side = ring_coords(outer, width)
    u = d / width  # 0 = outer edge, 1 = inner edge
    col = profile_fn(u, t, side)
    col *= SIDE_LIGHT[side][..., None]
    if texture is not None:
        col = texture(col, u, t, side)
    # tiny dark seam at the miter
    img[mask] = col[mask]
    return img


def paint_mat(img, mat_box, win_box, color, bevel=7):
    x0, y0, x1, y1 = mat_box
    m = rect_mask(*mat_box) > 0
    mat = np.ones((H, W, 3), np.float32) * np.array(color, np.float32)
    mat += noise(0.8, 2.2)[..., None] + noise(6, 1.2)[..., None]
    img[m] = mat[m]
    # bevel: bright white core cut, lit differently per side
    wx0, wy0, wx1, wy1 = win_box
    b_outer = (wx0 - bevel, wy0 - bevel, wx1 + bevel, wy1 + bevel)
    bm, bd, bt, bs = ring_coords(b_outer, bevel)
    shade = np.array([250, 222, 244, 230], np.float32)[bs]
    bcol = np.stack([shade, shade * 0.995, shade * 0.985], -1)
    img[bm] = bcol[bm]
    # mat shadow from the moulding onto the mat (top/left heavier)
    inner = gaussian_filter(rect_mask(x0, y0, x1, y1), 1)
    edge = np.clip(np.minimum.reduce([XX - x0, x1 - XX, (YY - y0) * 0.8, (y1 - YY) * 1.6]), 0, None)
    sh = np.exp(-edge / 10) * 0.22 * (m)
    img *= (1 - sh)[..., None]
    return img


def overlay_png(win_box, depth=26, strength=0.45, sheen=True):
    """Transparent overlay: inner shadow on the photo + faint glass sheen."""
    x0, y0, x1, y1 = win_box
    inside = rect_mask(*win_box)
    # distances from each window edge, weighted so shadow falls from top/left
    dt, dl = np.clip(YY - y0, 0, None), np.clip(XX - x0, 0, None)
    db, dr = np.clip(y1 - YY, 0, None), np.clip(x1 - XX, 0, None)
    s = (np.exp(-dt / depth) * 1.0 + np.exp(-dl / depth) * 0.75
         + np.exp(-db / (depth * 0.4)) * 0.25 + np.exp(-dr / (depth * 0.4)) * 0.3)
    alpha = np.clip(s * strength, 0, 0.7) * inside
    rgba = np.zeros((H, W, 4), np.float32)
    rgba[..., :3] = 0
    rgba[..., 3] = alpha * 255
    if sheen:
        # faint diagonal glass highlight in the upper-left
        g = ((XX - x0) + (YY - y0) * 1.2) / ((x1 - x0) + (y1 - y0) * 1.2)
        band = np.exp(-((g - 0.18) / 0.10) ** 2) * 0.05 * inside
        a_s = band
        a_tot = alpha + a_s * (1 - alpha)
        col = np.where(a_tot[..., None] > 0,
                       (a_s[..., None] * 255) / np.maximum(a_tot[..., None], 1e-6), 0)
        rgba[..., :3] = col
        rgba[..., 3] = a_tot * 255
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


# ---------- moulding profiles ----------
def black_profile(u, t, side):
    base = 28 + 18 * np.exp(-((u - 0.18) / 0.08) ** 2) + 10 * np.exp(-((u - 0.85) / 0.06) ** 2)
    base -= 10 * (u > 0.93)
    c = np.stack([base, base, base * 1.03], -1)
    return c + noise(0.7, 1.5)[..., None]


def oak_profile(u, t, side):
    # rounded profile: brighter crown
    crown = 0.82 + 0.25 * np.clip(np.sin(np.clip(u, 0, 1) * np.pi), 0, 1) ** 0.7
    crown -= 0.25 * (u > 0.92)
    base = np.array([196, 160, 116], np.float32)
    return base * crown[..., None]


def oak_texture(col, u, t, side):
    # grain runs along each side; compute coordinate across the grain (d) and along (t)
    along = t.astype(np.float32)
    across = u * 60
    warp = noise(30, 6)
    grain = np.sin((across + warp + side * 13.0) * 1.6 + np.sin(along / 90.0) * 2.0)
    streak = gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), (0.6, 0.6))
    fine = 0.5 + 0.5 * grain
    tone = 1 - 0.10 * fine - 0.03 * streak
    out = col * tone[..., None]
    out[..., 2] *= 0.97
    return out


def gold_profile(u, t, side):
    # stepped ornate profile: several highlight ridges
    ridges = (0.55 * np.exp(-((u - 0.12) / 0.05) ** 2) + 0.9 * np.exp(-((u - 0.40) / 0.10) ** 2)
              + 0.45 * np.exp(-((u - 0.70) / 0.05) ** 2) + 0.6 * np.exp(-((u - 0.88) / 0.04) ** 2))
    shade = 0.45 + 0.75 * ridges
    shade -= 0.25 * (np.abs(u - 0.58) < 0.03)  # groove
    shade -= 0.3 * (u > 0.95)
    base = np.array([176, 136, 62], np.float32)
    hi = np.array([248, 220, 150], np.float32)
    k = np.clip(shade - 0.6, 0, 1)[..., None]
    col = base * shade[..., None] * (1 - k) + hi * k
    # beaded pattern on the outer ridge
    bead = 0.5 + 0.5 * np.cos(t / 7.0 * np.pi)
    col *= (1 - 0.12 * bead * np.exp(-((u - 0.12) / 0.05) ** 2))[..., None]
    return col + noise(0.8, 3)[..., None]


def walnut_profile(u, t, side):
    base = np.array([74, 50, 36], np.float32)
    shade = 0.85 + 0.25 * np.exp(-((u - 0.3) / 0.2) ** 2)
    return base * shade[..., None]


def walnut_texture(col, u, t, side):
    warp = noise(25, 4)
    grain = np.sin((u * 40 + warp) * 2.1 + np.sin(t / 70.0) * 1.5)
    return col * (1 - 0.08 * (0.5 + 0.5 * grain))[..., None]


# ---------- frame definitions ----------
# Edge-to-edge: the moulding's outer edge is the TV's edge, so no wall shows.
def edge_win(mould, inner):
    b = mould + inner
    return (b, b, W - b, H - b)

FRAMES = [
    dict(id="gallery-black", name="Gallery Black", wall=(233, 229, 222),
         win=edge_win(30, 64), mat=64, mould=30, mat_color=(244, 241, 234),
         profile=black_profile, texture=None),
    dict(id="natural-oak", name="Natural Oak", wall=(226, 224, 219),
         win=edge_win(48, 60), mat=60, mould=48, mat_color=(242, 238, 228),
         profile=oak_profile, texture=oak_texture),
    dict(id="classic-gold", name="Classic Gold", wall=(64, 72, 70),
         win=edge_win(60, 44), mat=44, mould=60, mat_color=(238, 232, 218),
         profile=gold_profile, texture=None),
    dict(id="floating-walnut", name="Floating Walnut", wall=(236, 233, 227),
         win=edge_win(26, 14), mat=0, gap=14, mould=26, mat_color=None,
         profile=walnut_profile, texture=walnut_texture),
]


def build(f):
    x0, y0, x1, y1 = f["win"]
    img = wall(f["wall"])
    if f["mat"]:
        m = f["mat"]
        mat_box = (x0 - m, y0 - m, x1 + m, y1 + m)
        outer = (mat_box[0] - f["mould"], mat_box[1] - f["mould"], mat_box[2] + f["mould"], mat_box[3] + f["mould"])
    else:
        g = f["gap"]
        mat_box = (x0 - g, y0 - g, x1 + g, y1 + g)
        outer = (mat_box[0] - f["mould"], mat_box[1] - f["mould"], mat_box[2] + f["mould"], mat_box[3] + f["mould"])
    dark_wall = np.mean(f["wall"]) < 120
    img = drop_shadow(img, outer, strength=0.5 if dark_wall else 0.38)
    img = paint_moulding(img, outer, f["mould"], f["profile"], f["texture"])
    if f["mat"]:
        img = paint_mat(img, mat_box, f["win"], f["mat_color"])
    else:
        # floating: dark recessed gap, photo seems to float with a shadow behind it
        gm = rect_mask(*mat_box) > 0
        gap = np.ones((H, W, 3), np.float32) * 22
        img[gm] = gap[gm]
        fl = gaussian_filter(rect_mask(x0 + 4, y0 + 8, x1 + 4, y1 + 8), 6)
        img *= (1 - 0.5 * fl * gm)[..., None]
    # window placeholder grey (covered by the photo)
    wm = rect_mask(*f["win"]) > 0
    img[wm] = 128
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    if f["mat"]:
        ov = overlay_png(f["win"])
    elif f.get("lip"):
        # no mat: the moulding's inner lip casts a shadow straight onto the photo
        ov = overlay_png(f["win"], depth=16, strength=0.38, sheen=True)
    else:
        ov = overlay_png(f["win"], depth=10, strength=0.18, sheen=False)
    # One file per frame: opaque frame + mat, see-through window that carries only the inner shadow.
    merged = np.array(base.convert("RGBA"))
    ova = np.array(ov)
    wmask = rect_mask(*f["win"]) > 0
    merged[wmask] = ova[wmask]
    Image.fromarray(merged, "RGBA").save(os.path.join(OUT, f"{f['id']}.png"), optimize=True)
    return dict(id=f["id"], name=f["name"], file=f"{f['id']}.png",
                x=x0, y=y0, w=x1 - x0, h=y1 - y0)


# Every matted frame also gets a "No mat" version: photo runs right up to the moulding.
NO_MAT = [dict(f, id=f["id"] + "-no-mat", mat=0, gap=0, lip=True, win=edge_win(f["mould"], 0))
          for f in FRAMES if f["mat"]]

frames = [build(f) for f in FRAMES]
no_mat = {f["name"]: build(dict(f)) for f in NO_MAT}

# catalog: frame name -> variant name -> frame entry (read by shortcut v8+).
# A frame with one variant makes the shortcut skip the mat question automatically.
catalog = {}
for f in frames:
    if f["name"] in no_mat:
        catalog[f["name"]] = {"With mat": f, "No mat": no_mat[f["name"]]}
    else:
        catalog[f["name"]] = {"Standard": f}

manifest = {"version": 3, "canvas": {"w": W, "h": H},
            "frames": frames + list(no_mat.values()),
            "by_name": {f["name"]: f for f in frames},   # kept for shortcut v7
            "catalog": catalog}
with open(os.path.join(OUT, "frames.json"), "w") as fh:
    json.dump(manifest, fh, indent=2)
print(json.dumps(manifest, indent=2))
