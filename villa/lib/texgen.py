# -*- coding: utf-8 -*-
"""别墅程序化贴图：纯 numpy + 自写 PNG 编码，全部严格可平铺。

用法：python lib/texgen.py [--res 512] [--only plaster,wood_oak]
产物：textures/<name>_albedo.png / <name>_normal.png / manifest.json
"""
import os
import sys
import json
import zlib
import struct
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "textures")
F = np.float32
RES = 512


# ------------------------------------------------------------------ PNG
def write_png(path, arr):
    """arr: (H,W,3) float32 0..1 -> 8bit RGB PNG（filter 0）"""
    a = np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)
    h, w, c = a.shape
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += a[y].tobytes()

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)
    return len(png)


# ------------------------------------------------------------------ 噪声
def _interp1(g, axis, res):
    cells = g.shape[axis]
    t = np.arange(res, dtype=F) * (cells / float(res))
    i0 = np.floor(t).astype(np.int64) % cells
    i1 = (i0 + 1) % cells
    f = (t - np.floor(t)).astype(F)
    f = f * f * (3.0 - 2.0 * f)
    g0 = np.take(g, i0, axis=axis)
    g1 = np.take(g, i1, axis=axis)
    shape = [1] * g.ndim
    shape[axis] = res
    f = f.reshape(shape)
    return g0 * (1.0 - f) + g1 * f


def value_noise(res, cells, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((cells, cells)).astype(F)
    g = _interp1(g, 0, res)
    g = _interp1(g, 1, res)
    return g


def fbm(res, cells=4, octaves=5, persistence=0.5, lacunarity=2.0, seed=0):
    out = np.zeros((res, res), F)
    amp, tot, c = 1.0, 0.0, int(cells)
    for o in range(octaves):
        out += amp * value_noise(res, max(1, c), seed + o * 17)
        tot += amp
        amp *= persistence
        c *= int(lacunarity)
    return out / max(tot, 1e-6)


def ridged(res, cells=4, octaves=4, seed=0):
    out = np.zeros((res, res), F)
    amp, tot, c = 1.0, 0.0, int(cells)
    for o in range(octaves):
        n = value_noise(res, max(1, c), seed + o * 29)
        out += amp * (1.0 - np.abs(n * 2.0 - 1.0))
        tot += amp
        amp *= 0.55
        c *= 2
    return out / max(tot, 1e-6)


def warp(h, amt, seed, res):
    """用两张低频噪声做位移，注意取模保持可平铺。"""
    dx = (fbm(res, 3, 3, 0.5, 2.0, seed) - 0.5) * 2 * amt
    dy = (fbm(res, 3, 3, 0.5, 2.0, seed + 71) - 0.5) * 2 * amt
    xs = (np.arange(res, dtype=F)[None, :] + dx * res).astype(np.int64) % res
    ys = (np.arange(res, dtype=F)[:, None] + dy * res).astype(np.int64) % res
    return h[ys, xs]


def blur(h, r=3):
    k = np.ones(2 * r + 1, F) / (2 * r + 1)
    for ax in (0, 1):
        for _ in range(2):
            h = np.apply_along_axis(lambda m: np.convolve(np.r_[m[-r:], m, m[:r]], k,
                                                          mode="same")[r:-r], ax, h)
    return h


def sstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(x, stops):
    """stops: [(pos, (r,g,b))] -> (H,W,3)"""
    x = np.clip(x, 0, 1)
    pos = np.array([s[0] for s in stops], F)
    cols = np.array([s[1] for s in stops], F)
    out = np.zeros(x.shape + (3,), F)
    for c in range(3):
        out[..., c] = np.interp(x, pos, cols[:, c])
    return out


def tint(base, shade, m):
    """base/shade 为 RGB，m 为 0..1 混合系数"""
    base = np.array(base, F)
    shade = np.array(shade, F)
    return base[None, None, :] * (1 - m[..., None]) + shade[None, None, :] * m[..., None]


def normal_map(h, strength=2.2):
    gy, gx = np.gradient(h.astype(F))
    nx = -gx * strength * 12.0
    ny = -gy * strength * 12.0
    nz = np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1)
    return n * 0.5 + 0.5


# ------------------------------------------------------------------ 材质
def m_plaster(res, seed=11):
    n = fbm(res, 6, 5, 0.55, 2.0, seed)
    fine = fbm(res, 48, 3, 0.5, 2.0, seed + 5)
    stroke = fbm(res, 2, 3, 0.5, 2.0, seed + 9)
    m = np.clip(0.55 * n + 0.30 * fine + 0.15 * stroke, 0, 1)
    alb = tint((0.862, 0.846, 0.804), (0.822, 0.806, 0.766), m)
    h = blur(0.35 * fine + 0.65 * n, 6) * 0.35
    return alb, h, 0.90


def m_stone(res, seed=23, light=False):
    grain = fbm(res, 96, 2, 0.5, 2.0, seed)
    patch = fbm(res, 5, 4, 0.55, 2.0, seed + 3)
    m = np.clip(0.62 * grain + 0.38 * patch, 0, 1)
    base = (0.700, 0.686, 0.652) if light else (0.400, 0.392, 0.372)
    dark = (0.610, 0.596, 0.566) if light else (0.300, 0.294, 0.280)
    alb = tint(base, dark, m)
    h = 0.7 * grain + 0.3 * patch
    return alb, h, 0.78


def m_marble(res, seed=31):
    v = ridged(res, 3, 4, seed)
    v = warp(v, 0.045, seed + 7, res)
    veins = sstep(0.62, 0.92, v)
    soft = fbm(res, 8, 4, 0.5, 2.0, seed + 13)
    m = np.clip(0.85 * veins + 0.15 * soft, 0, 1)
    alb = tint((0.905, 0.895, 0.878), (0.560, 0.556, 0.560), m)
    h = 0.4 * veins + 0.6 * soft
    return alb, h, 0.18


def m_wood(res, seed=41, light=True, charred=False):
    # 沿 V 方向的年轮：把 U 扭曲后取正弦
    u = np.arange(res, dtype=F)[None, :] / res
    v = np.arange(res, dtype=F)[:, None] / res
    w = fbm(res, 4, 4, 0.5, 2.0, seed)
    ring = np.sin((u * (9.0 if light else 6.0) + w * 1.6 + v * 0.35) * np.pi * 2)
    ring = 0.5 + 0.5 * ring
    fine = fbm(res, 64, 3, 0.5, 2.0, seed + 5)
    knot = sstep(0.86, 0.99, fbm(res, 6, 4, 0.5, 2.0, seed + 21))
    m = np.clip(0.55 * ring + 0.30 * fine + 0.15 * knot, 0, 1)
    if charred:
        alb = tint((0.128, 0.096, 0.074), (0.062, 0.050, 0.044), m)
        hs = 0.6 * fine + 0.4 * ring
        return alb, hs, 0.52
    if light:
        alb = tint((0.586, 0.462, 0.318), (0.486, 0.372, 0.246), m)
        hs = 0.5 * ring + 0.5 * fine
        return alb, hs, 0.55
    alb = tint((0.300, 0.196, 0.126), (0.226, 0.142, 0.086), m)
    hs = 0.55 * ring + 0.45 * fine
    return alb, hs, 0.52


def m_tile(res, seed=53):
    # 瓦垄方向沿 U：细条纹 + 泥灰斑
    u = np.arange(res, dtype=F)[None, :] / res
    stripe = 0.5 + 0.5 * np.cos(u * np.pi * 2 * 9)
    n = fbm(res, 12, 4, 0.5, 2.0, seed)
    stain = fbm(res, 3, 3, 0.5, 2.0, seed + 7)
    m = np.clip(0.45 * stripe + 0.35 * n + 0.20 * stain, 0, 1)
    alb = tint((0.112, 0.118, 0.126), (0.062, 0.068, 0.076), m)
    h = 0.75 * stripe + 0.25 * n
    return alb, h, 0.62


def m_fabric(res, seed=61):
    u = np.arange(res, dtype=F)[None, :]
    v = np.arange(res, dtype=F)[:, None]
    weave_u = 0.5 + 0.5 * np.cos(u / res * np.pi * 2 * 64)
    weave_v = 0.5 + 0.5 * np.cos(v / res * np.pi * 2 * 64)
    weave = np.clip(weave_u * 0.5 + weave_v * 0.5, 0, 1)
    n = fbm(res, 24, 3, 0.5, 2.0, seed)
    m = np.clip(0.55 * weave + 0.45 * n, 0, 1)
    alb = tint((0.760, 0.720, 0.660), (0.640, 0.596, 0.540), m)
    h = m
    return alb, h, 0.95


def m_rug(res, seed=67):
    n = fbm(res, 40, 3, 0.5, 2.0, seed)
    fuzz = fbm(res, 128, 2, 0.5, 2.0, seed + 3)
    m = np.clip(0.4 * n + 0.6 * fuzz, 0, 1)
    alb = tint((0.520, 0.478, 0.420), (0.410, 0.372, 0.322), m)
    return alb, m, 0.99


def m_grass(res, seed=73):
    clump = fbm(res, 6, 4, 0.55, 2.0, seed)
    blade = fbm(res, 90, 3, 0.5, 2.0, seed + 5)
    big = fbm(res, 2, 3, 0.5, 2.0, seed + 11)
    m = np.clip(0.45 * clump + 0.35 * blade + 0.20 * big, 0, 1)
    alb = tint((0.246, 0.318, 0.156), (0.140, 0.196, 0.096), m)
    # 少量亮草尖
    tip = sstep(0.86, 1.0, blade)
    alb = alb * (1 - tip[..., None]) + np.array((0.400, 0.470, 0.230), F)[None, None, :] * tip[..., None]
    return alb, m, 0.95


def m_gravel(res, seed=83):
    c = fbm(res, 30, 3, 0.5, 2.0, seed)
    peb = sstep(0.35, 0.75, c)
    fine = fbm(res, 110, 2, 0.5, 2.0, seed + 7)
    m = np.clip(0.7 * peb + 0.3 * fine, 0, 1)
    alb = tint((0.560, 0.540, 0.500), (0.360, 0.346, 0.318), m)
    return alb, m, 0.92


TILES = {
    "plaster":      (m_plaster, 2.0),
    "stone":        (lambda r, s=0: m_stone(r, 23, False), 2.0),
    "stone_light":  (lambda r, s=0: m_stone(r, 29, True), 2.0),
    "marble":       (m_marble, 3.0),
    "wood_oak":     (lambda r, s=0: m_wood(r, 41, True, False), 2.0),
    "wood_walnut":  (lambda r, s=0: m_wood(r, 47, False, False), 2.0),
    "wood_charred": (lambda r, s=0: m_wood(r, 59, False, True), 2.0),
    "tile":         (m_tile, 1.5),
    "fabric":       (m_fabric, 0.6),
    "rug":          (m_rug, 1.0),
    "grass":        (m_grass, 3.0),
    "gravel":       (m_gravel, 1.5),
}


def main():
    args = sys.argv[1:]
    res = RES
    only = None
    for a in args:
        if a.startswith("--res="):
            res = int(a.split("=", 1)[1])
        elif a.startswith("--res"):
            try:
                res = int(args[args.index(a) + 1])
            except Exception:
                pass
        elif a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")
        elif a.startswith("--only"):
            only = args[args.index(a) + 1].split(",")
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "manifest.json")
    man = {"tiles": {}}
    if os.path.exists(man_path):
        try:
            man = json.load(open(man_path, encoding="utf-8"))
            man.setdefault("tiles", {})
        except Exception:
            pass
    names = [n for n in TILES if (not only or n in only)]
    total = 0
    t_all = time.time()
    for name in names:
        fn, tile_m = TILES[name]
        t0 = time.time()
        alb, h, _rough = fn(res)
        h = blur(h, 2)
        # 法线降采样一半再求导，体积小很多且不影响观感
        hn = h[: (res // 2) * 2:2, : (res // 2) * 2:2]
        hn = blur(hn, 1)
        nm = normal_map(hn, 0.85)
        ap = os.path.join(OUT, f"{name}_albedo.png")
        npth = os.path.join(OUT, f"{name}_normal.png")
        ba = write_png(ap, alb)
        bn = write_png(npth, nm)
        total += ba + bn
        man["tiles"][name] = {"albedo": f"textures/{name}_albedo.png",
                              "normal": f"textures/{name}_normal.png",
                              "tile_m": tile_m}
        print(f"  {name:14s} {res}x{res}  albedo {ba/1024:6.1f}KB  normal {bn/1024:6.1f}KB"
              f"  {time.time()-t0:5.1f}s  mean={alb.mean():.3f} std={alb.std():.3f}")
    json.dump(man, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[texgen] {len(names)} 套 / 共 {total/1024/1024:.2f}MB / {time.time()-t_all:.1f}s")


if __name__ == "__main__":
    main()
