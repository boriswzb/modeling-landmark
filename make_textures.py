"""Procedural, seamless texture maps for the Giza plateau model.

Everything is generated with numpy/Pillow so the Blender scene is fully
self-contained and the exported glTF can embed the same images.
"""
from __future__ import annotations

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(20251020)


# ---------------------------------------------------------------- utilities
def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def periodic_noise(h, w, cells, octaves=5, persistence=0.55, seed=0):
    """Periodic value noise in [0, 1]; tiles seamlessly in both axes."""
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w), np.float32)
    norm = 0.0
    amp = 1.0
    for o in range(octaves):
        gh = max(2, int(cells * (2 ** o)))
        gw = max(2, int(cells * (2 ** o) * w / h))
        grid = rng.random((gh, gw), dtype=np.float32)
        ys = np.linspace(0, gh, h, endpoint=False, dtype=np.float32)
        xs = np.linspace(0, gw, w, endpoint=False, dtype=np.float32)
        y0 = np.floor(ys).astype(np.int32)
        x0 = np.floor(xs).astype(np.int32)
        ty = smoothstep(ys - y0)[:, None]
        tx = smoothstep(xs - x0)[None, :]
        y1 = (y0 + 1) % gh
        x1 = (x0 + 1) % gw
        a = grid[np.ix_(y0, x0)]
        b = grid[np.ix_(y0, x1)]
        c = grid[np.ix_(y1, x0)]
        d = grid[np.ix_(y1, x1)]
        total += amp * ((a * (1 - tx) + b * tx) * (1 - ty) +
                        (c * (1 - tx) + d * tx) * ty)
        norm += amp
        amp *= persistence
    out = total / norm
    out -= out.min()
    out /= max(out.max(), 1e-6)
    return out


def fbm(h, w, octaves=6, base=4, persistence=0.55, seed=1):
    return periodic_noise(h, w, base, octaves, persistence, seed)


def normal_from_height(height, strength=3.0):
    """OpenGL-style tangent normal map from a [0,1] height field."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    nz = np.ones_like(height)
    ln = np.sqrt(dx * dx + dy * dy + nz * nz)
    n = np.stack((-dx / ln, -dy / ln, nz / ln), axis=-1)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def save_rgb(name, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(os.path.join(OUT, name), optimize=True)


def save_gray(name, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "L").save(os.path.join(OUT, name), optimize=True)


def colorize(value, dark, light, gamma=1.0):
    """Map a [0,1] field between two RGB triples."""
    v = np.clip(value, 0, 1)[..., None] ** gamma
    return np.asarray(dark)[None, None, :] * (1 - v) + np.asarray(light)[None, None, :] * v


# ------------------------------------------------------------ limestone core
def limestone_core(size=2048, meters=16.0):
    """Weathered Nummulitic limestone in horizontal courses, 16 m tile."""
    ppm = size / meters
    rows = []
    y = 0
    while y < size:
        h = int(np.clip(RNG.normal(1.30, 0.18), 0.95, 1.75) * ppm)
        h = min(h, size - y)
        if size - (y + h) < 0.65 * ppm:
            h = size - y
        rows.append((y, h))
        y += h

    value = np.zeros((size, size), np.float32)
    rgb = np.zeros((size, size, 3), np.float32)
    height = np.full((size, size), 0.52, np.float32)
    rough = np.full((size, size), 0.86, np.float32)
    # per-block records for later detailing
    blocks = []
    for (y0, h) in rows:
        x = 0
        offset = int(RNG.integers(0, size))
        while x < size:
            w = int(np.clip(RNG.normal(3.2, 0.9), 1.7, 5.8) * ppm)
            w = min(w, size - x)
            if size - (x + w) < 1.1 * ppm:
                w = size - x
            blocks.append((x, y0, w, h, offset))
            x += w

    # base stone color variation
    macro = fbm(size, size, octaves=6, base=3, persistence=0.6, seed=11)
    mid = fbm(size, size, octaves=5, base=12, persistence=0.55, seed=17)
    fine = fbm(size, size, octaves=4, base=48, persistence=0.5, seed=23)

    for (x0, y0, w, h, offset) in blocks:
        # one flat block tone + a soft internal gradient
        tone = RNG.normal(0, 1)
        base = np.array([204, 186, 154], np.float32) + tone * np.array([3.0, 2.5, 2.0])
        base *= RNG.uniform(0.975, 1.025)
        rgb[y0:y0 + h, x0:x0 + w] = base
        value[y0:y0 + h, x0:x0 + w] = 0.55 + 0.06 * np.tanh(tone)

    # multiply in broad staining and fine grain
    stain = (macro - 0.5) * 0.10 + (mid - 0.5) * 0.05
    rgb *= (1.0 + stain[..., None])
    rgb += (fine[..., None] - 0.5) * 5.0

    # joint recesses: draw on a height canvas, then darken color there
    joint = Image.new("L", (size, size), 0)
    jd = ImageDraw.Draw(joint)
    for (x0, y0, w, h, offset) in blocks:
        jd.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=255, width=max(1, int(0.018 * ppm)))
    joint = np.asarray(joint.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255.0
    height -= joint * 0.26
    rgb *= (1.0 - joint[..., None] * 0.16)

    # chipped corners / patches
    chips = (fbm(size, size, octaves=4, base=60, persistence=0.55, seed=31) > 0.72).astype(np.float32)
    chips = np.asarray(Image.fromarray((chips * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
    rgb *= (1.0 - chips[..., None] * 0.035)
    height -= chips * 0.04

    # vertical desert varnish / rain streaks
    streak_seed = fbm(size, 32, octaves=4, base=3, persistence=0.55, seed=43)
    streak_seed = np.asarray(Image.fromarray((streak_seed * 255).astype(np.uint8)).resize(
        (size, size), Image.BICUBIC), np.float32) / 255.0
    streak = np.clip((streak_seed - 0.52) * 3.0, 0, 1) * (fbm(size, size, 4, 8, seed=47) * 0.6 + 0.4)
    rgb *= (1.0 - streak[..., None] * 0.05)

    # pitting / fossils
    pits = (fbm(size, size, octaves=3, base=110, persistence=0.5, seed=53) > 0.80).astype(np.float32)
    pits = np.asarray(Image.fromarray((pits * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
    rgb *= (1.0 - pits[..., None] * 0.09)
    height -= pits * 0.09

    height += (fine - 0.5) * 0.10
    rough = np.clip(0.84 + (macro - 0.5) * 0.12 + (fine - 0.5) * 0.05, 0.70, 0.97)

    # colour grade: warm, sun-bleached limestone
    rgb = np.clip(rgb, 0, 255)
    save_rgb("limestone_core_color.png", rgb)
    save_gray("limestone_core_height.png", height * 255)
    save_rgb("limestone_core_normal.png", normal_from_height(height, strength=2.6))
    save_gray("limestone_core_rough.png", rough * 255)


# ------------------------------------------------------------- smooth casing
def casing(size=1024, meters=8.0):
    n1 = fbm(size, size, 6, 3, seed=101)
    n2 = fbm(size, size, 5, 14, seed=103)
    n3 = fbm(size, size, 4, 60, seed=107)
    v = 0.72 + 0.18 * n1 + 0.07 * n2 + 0.03 * n3
    rgb = colorize(v, (196, 185, 158), (244, 236, 213), gamma=1.05)
    # faint horizontal tooling / bedding planes
    yy = np.arange(size, dtype=np.float32)[:, None]
    bedding = 0.5 + 0.5 * np.sin(yy / size * np.pi * 2 * 11 + 1.2)
    rgb *= (1.0 - 0.025 * bedding[..., None])
    # a few hairline cracks
    rng = np.random.default_rng(109)
    crack = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(crack)
    for _ in range(14):
        x = int(rng.integers(0, size)); y = int(rng.integers(0, size))
        pts = [(x, y)]
        for _ in range(int(rng.integers(4, 12))):
            x += int(rng.normal(0, 16)); y += int(rng.integers(4, 28))
            pts.append((x, y))
        d.line(pts, fill=int(rng.integers(80, 150)), width=1)
    crack = np.asarray(crack.filter(ImageFilter.GaussianBlur(0.5)), np.float32) / 255.0
    rgb *= (1 - 0.18 * crack[..., None])
    height = 0.55 + 0.10 * n1 + 0.05 * n2 - 0.18 * crack
    rough = np.clip(0.62 + (n2 - 0.5) * 0.12, 0.5, 0.82)
    save_rgb("casing_color.png", rgb)
    save_rgb("casing_normal.png", normal_from_height(height, 2.0))
    save_gray("casing_rough.png", rough * 255)


# ----------------------------------------------------- pyramid mass texture
def pyramid_stone(size=1024, meters=220.0):
    """Large-scale weathered limestone for the pyramid masses.

    No individual blocks: at 1-3 km a 1.3 m block is sub-pixel and turns into
    moire. Geometry supplies the courses, this map supplies broad staining,
    bedding and erosion.
    """
    n1 = fbm(size, size, 6, 4, seed=801)
    n2 = fbm(size, size, 5, 12, seed=803)
    n3 = fbm(size, size, 4, 48, seed=807)
    yy = np.arange(size, dtype=np.float32)[:, None]
    bedding = 0.5 + 0.5 * np.sin(yy / size * 2 * np.pi * 24 + (n1 - 0.5) * 3.2)
    # long vertical rain streaks
    streak = fbm(size, 64, 4, 7, seed=809)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize(
        (size, size), Image.BICUBIC), np.float32) / 255.0
    streak = np.clip((streak - 0.5) * 2.4, 0, 1)

    v = 0.58 + 0.15 * n1 + 0.06 * n2 + 0.02 * n3 - 0.05 * streak + 0.02 * bedding
    rgb = colorize(np.clip(v, 0, 1), (180, 158, 121), (226, 206, 170), gamma=1.0)
    rgb *= (1.0 - 0.025 * bedding[..., None])
    rgb *= (1.0 - 0.06 * streak[..., None])
    height = 0.5 + 0.16 * (n1 - 0.5) + 0.06 * (n2 - 0.5) + 0.025 * bedding - 0.04 * streak
    rough = np.clip(0.84 + (n1 - 0.5) * 0.08 + (n3 - 0.5) * 0.04, 0.74, 0.96)
    save_rgb("pyramid_color.png", rgb)
    save_rgb("pyramid_normal.png", normal_from_height(height, 2.0))
    save_gray("pyramid_rough.png", rough * 255)


# ------------------------------------------------------------------- granite
def granite(size=1024, meters=4.0):
    base = np.zeros((size, size, 3), np.float32)
    n = fbm(size, size, 5, 20, seed=201)
    base[..., 0] = 112 + 46 * n
    base[..., 1] = 92 + 40 * n
    base[..., 2] = 86 + 36 * n
    # feldspar / quartz speckles
    rng = np.random.default_rng(203)
    for _ in range(22000):
        x, y = rng.integers(0, size, 2)
        r = rng.integers(0, 3)
        c = rng.choice([[196, 178, 160], [52, 44, 44], [168, 132, 118], [220, 210, 190]])
        base[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = c
    base *= (0.86 + 0.28 * fbm(size, size, 3, 5, seed=207))[..., None]
    height = 0.5 + 0.25 * (fbm(size, size, 5, 50, seed=211) - 0.5)
    rough = np.clip(0.35 + 0.25 * fbm(size, size, 3, 9, seed=213), 0.25, 0.7)
    save_rgb("granite_color.png", base)
    save_rgb("granite_normal.png", normal_from_height(height, 1.5))
    save_gray("granite_rough.png", rough * 255)


# --------------------------------------------------------------------- sand
def sand(size=2048, meters=42.0):
    warp = fbm(size, size, 4, 6, seed=301)
    # wind ripples: irregular diagonal wave field
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    phase = (xx * 0.86 + yy * 0.50) / size * 2 * np.pi * 38
    phase += (warp - 0.5) * 10.0
    ripple = 0.5 + 0.5 * np.sin(phase)
    ripple = np.asarray(Image.fromarray((ripple * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.5)), np.float32) / 255.0
    grain = fbm(size, size, 4, 90, seed=303)
    macro = fbm(size, size, 5, 4, seed=305)
    gravel = (fbm(size, size, 3, 150, seed=307) > 0.76).astype(np.float32)
    gravel = np.asarray(Image.fromarray((gravel * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0

    v = 0.55 + 0.18 * ripple + 0.10 * grain + 0.15 * macro - 0.20 * gravel
    rgb = colorize(np.clip(v, 0, 1), (146, 116, 79), (213, 181, 134), gamma=1.0)
    # darker granules / tiny pebbles
    rng = np.random.default_rng(311)
    pts = rng.integers(0, size, (14000, 2))
    for x, y in pts:
        c = rng.choice([[120, 100, 80], [198, 172, 132], [150, 126, 98], [90, 78, 66]])
        rgb[y, x] = c
    height = 0.35 + 0.28 * ripple + 0.10 * grain + 0.18 * gravel
    rough = np.clip(0.88 + (grain - 0.5) * 0.08, 0.78, 0.98)
    save_rgb("sand_color.png", rgb)
    save_rgb("sand_normal.png", normal_from_height(height, 1.4))
    save_gray("sand_rough.png", rough * 255)


# ------------------------------------------------------------- bedrock/rock
def rock(size=1024, meters=12.0):
    n1 = fbm(size, size, 6, 5, seed=401)
    n2 = fbm(size, size, 5, 22, seed=403)
    # horizontal Mokattam bedding
    yy = np.arange(size, dtype=np.float32)[:, None]
    strata = 0.5 + 0.5 * np.sin(yy / size * 2 * np.pi * 9 + (n1 - 0.5) * 2.2)
    v = 0.45 + 0.26 * n1 + 0.10 * n2 + 0.10 * strata
    rgb = colorize(np.clip(v, 0, 1), (120, 105, 84), (206, 188, 155), gamma=1.1)
    # vertical erosion channels
    rng = np.random.default_rng(407)
    chan = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(chan)
    for _ in range(40):
        x = int(rng.integers(0, size)); w = int(rng.integers(2, 12))
        y0 = int(rng.integers(0, size // 2))
        d.line([(x, y0), (x + int(rng.normal(0, 12)), size)], fill=int(rng.integers(50, 150)), width=w)
    chan = np.asarray(chan.filter(ImageFilter.GaussianBlur(2.4)), np.float32) / 255.0
    rgb *= (1.0 - 0.25 * chan[..., None])
    height = 0.5 + 0.25 * (n1 - 0.5) + 0.15 * strata - 0.25 * chan + 0.05 * n2
    save_rgb("rock_color.png", rgb)
    save_rgb("rock_normal.png", normal_from_height(height, 2.8))
    save_gray("rock_rough.png", np.clip(0.85 + (n2 - 0.5) * 0.2, 0.65, 0.98) * 255)


# ---------------------------------------------------------- sphinx limestone
def sphinx_stone(size=2048, meters=16.0):
    n1 = fbm(size, size, 6, 4, seed=501)
    n2 = fbm(size, size, 5, 18, seed=503)
    n3 = fbm(size, size, 4, 80, seed=507)
    # severe vertical weathering, especially lower half
    yy = np.linspace(0, 1, size, dtype=np.float32)[:, None]
    streak_src = fbm(size, 64, 4, 8, seed=509)
    streak = np.asarray(Image.fromarray((streak_src * 255).astype(np.uint8)).resize(
        (size, size), Image.BICUBIC), np.float32) / 255.0
    streak = np.clip((streak - 0.45) * 2.0, 0, 1)
    v = 0.52 + 0.22 * n1 + 0.08 * n2 - 0.18 * streak * (1.15 - yy) + 0.04 * n3
    rgb = colorize(np.clip(v, 0, 1), (138, 117, 88), (216, 194, 155), gamma=1.0)
    # dark desert varnish in recesses
    rgb *= (1.0 - 0.18 * streak[..., None])
    height = 0.55 + 0.20 * (n1 - 0.5) + 0.10 * (n2 - 0.5) - 0.22 * streak + 0.04 * n3
    save_rgb("sphinx_color.png", rgb)
    save_rgb("sphinx_normal.png", normal_from_height(height, 3.0))
    save_gray("sphinx_rough.png", np.clip(0.78 + (n2 - 0.5) * 0.22, 0.6, 0.97) * 255)


# ---------------------------------------------------------------- mudbrick
def mudbrick(size=1024, meters=8.0):
    ppm = size / meters
    rgb = np.zeros((size, size, 3), np.float32)
    height = np.full((size, size), 0.5, np.float32)
    rows = []
    y = 0
    while y < size:
        h = int(np.clip(RNG.normal(0.42, 0.05), 0.30, 0.55) * ppm)
        h = min(h, size - y)
        rows.append((y, h)); y += h
    joint = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(joint)
    for (y0, h) in rows:
        x = 0
        while x < size:
            w = int(np.clip(RNG.normal(0.9, 0.15), 0.5, 1.4) * ppm)
            w = min(w, size - x)
            rgb[y0:y0 + h, x:x + w] = np.array([166, 133, 96]) + RNG.normal(0, 1) * 9
            d.rectangle([x, y0, x + w - 1, y0 + h - 1], outline=220, width=2)
            x += w
    joint = np.asarray(joint.filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255.0
    rgb *= (1 - 0.25 * joint[..., None])
    rgb *= (0.82 + 0.32 * fbm(size, size, 5, 10, seed=601))[..., None]
    height -= 0.25 * joint + 0.1 * fbm(size, size, 3, 40, seed=603)
    save_rgb("mudbrick_color.png", rgb)
    save_rgb("mudbrick_normal.png", normal_from_height(height, 1.8))


# ------------------------------------------------------------ nemes stripes
def nemes(size=1024, meters=8.0):
    """Eroded, faintly striped nemes headdress linen/stone."""
    ppm = size / meters
    yy = np.arange(size, dtype=np.float32)[:, None]
    # broad stripes about 0.42 m apart, softened by erosion
    band = 0.5 + 0.5 * np.sin(yy / ppm / 0.34 * 2 * np.pi)
    band = np.asarray(Image.fromarray((band * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.0)), np.float32) / 255.0
    n1 = fbm(size, size, 6, 4, seed=701)
    n2 = fbm(size, size, 4, 28, seed=703)
    streak = fbm(size, 48, 4, 9, seed=707)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize(
        (size, size), Image.BICUBIC), np.float32) / 255.0
    v = 0.55 + 0.12 * n1 + 0.07 * n2 - 0.12 * np.clip(streak - 0.5, 0, 1)
    rgb = colorize(np.clip(v, 0, 1), (128, 108, 78), (210, 192, 158), gamma=1.0)
    # faded blue-grey stripe pigment, heavily worn
    stripe_tint = np.array([78, 74, 64], np.float32)
    wear = np.clip(n1 * 0.8 + n2 * 0.2 - 0.10, 0, 1)
    rgb = rgb * (1 - 0.38 * band[..., None] * wear[..., None]) + stripe_tint[None, None, :] * (0.38 * band[..., None] * wear[..., None])
    rgb *= (1.0 - 0.10 * np.clip(streak - 0.55, 0, 1)[..., None])
    height = 0.5 + 0.20 * band + 0.10 * (n1 - 0.5) - 0.12 * np.clip(streak - 0.5, 0, 1)
    save_rgb("nemes_color.png", rgb)
    save_rgb("nemes_normal.png", normal_from_height(height, 1.8))
    save_gray("nemes_rough.png", np.clip(0.8 + (n2 - 0.5) * 0.15, 0.62, 0.95) * 255)


if __name__ == "__main__":
    import time
    t0 = time.time()
    print("limestone core...")
    limestone_core()
    print("casing...")
    casing()
    print("granite...")
    granite()
    print("sand...")
    sand()
    print("bedrock...")
    rock()
    print("sphinx stone...")
    sphinx_stone()
    print("mudbrick...")
    mudbrick()
    print(f"done in {time.time() - t0:.1f}s -> {OUT}")
