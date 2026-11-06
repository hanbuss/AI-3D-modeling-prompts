"""园林植被与景观石。"""
import math
import random
from mathutils import Vector, Matrix
from .kit import GB, D, TAU, lerp

R = random.Random(77)


def pine(gb, h=6.0, r=2.2, bark="M_Bark", leaf="M_LeafPine", seed=0):
    """造型松：弯曲主干 + 3-4 层横向枝盘，每层由成团针叶簇构成。"""
    rng = random.Random(seed or int(h * 100))
    seg = 7
    pts = []
    lean = rng.uniform(-0.5, 0.5)
    for i in range(seg + 1):
        t = i / seg
        pts.append(Vector((lean * t * t, rng.uniform(-0.10, 0.10) * t, h * t)))
    for i in range(seg):
        p0, p1 = pts[i], pts[i + 1]
        d = p1 - p0
        mid = (p0 + p1) / 2
        yaw = math.atan2(d.y, d.x)
        pitch = math.atan2(math.hypot(d.x, d.y), d.z)
        M = Matrix.Translation(mid) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "Y")
        rad = lerp(0.145, 0.045, i / seg)
        with gb.frame(M):
            gb.cyl(rad, d.length * 1.06, (0, 0, 0), seg=9, mat=bark, r_top=rad * 0.9)

    layers = rng.randint(3, 4)
    for L in range(layers):
        t = 0.38 + 0.58 * L / max(1, layers - 1)
        cz = h * t
        rr = r * (1.0 - 0.42 * (L / layers)) * rng.uniform(0.9, 1.05)
        cx = lean * t * t
        n = rng.randint(4, 6)
        for k in range(n):
            a = TAU * k / n + rng.uniform(-0.35, 0.35)
            ox, oy = math.cos(a), math.sin(a)
            # 横向枝
            bl = rr * rng.uniform(0.55, 0.95)
            tip = Vector((cx + ox * bl, oy * bl, cz + rng.uniform(0.02, 0.10)))
            base = Vector((cx, 0, cz - 0.06))
            d = tip - base
            mid = (base + tip) / 2
            M = (Matrix.Translation(mid) @
                 Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z") @
                 Matrix.Rotation(math.atan2(math.hypot(d.x, d.y), d.z), 4, "Y"))
            with gb.frame(M):
                gb.cyl(0.028, d.length, (0, 0, 0), seg=6, mat=bark, r_top=0.014)
            # 针叶团：沿枝 3 团 + 端头 2 团
            for m in range(7):
                f = 0.45 + 0.55 * (m / 4)
                px = cx + ox * bl * f + rng.uniform(-0.14, 0.14)
                py = oy * bl * f + rng.uniform(-0.14, 0.14)
                pz = cz + rng.uniform(0.0, 0.16)
                gb.sphere(rr * rng.uniform(0.11, 0.17), (px, py, pz), seg=8, rings=5,
                          mat=leaf, scale=(1.35, 1.3, 0.40))
    # 顶冠
    gb.sphere(r * 0.26, (lean, 0, h + 0.02), seg=10, rings=6, mat=leaf,
              scale=(1.1, 1.1, 0.7))


def maple(gb, h=4.2, r=1.8, leaf="M_LeafMaple", seed=0):
    """红枫：主干分三杈，冠由 70+ 个小叶团构成，不是一堆大气球。"""
    rng = random.Random(seed or int(h * 37))
    gb.cyl(0.13, h * 0.42, (0, 0, h * 0.21), seg=10, mat="M_Bark", r_top=0.10)
    tips = []
    for k in range(3):
        a0 = TAU * k / 3 + rng.uniform(-0.35, 0.35)
        b0 = Vector((0, 0, h * 0.36))
        b1 = Vector((math.cos(a0) * r * 0.42, math.sin(a0) * r * 0.42, h * 0.72))
        mid = (b0 + b1) / 2
        d = b1 - b0
        M = (Matrix.Translation(mid) @ Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z") @
             Matrix.Rotation(math.atan2(math.hypot(d.x, d.y), d.z), 4, "Y"))
        with gb.frame(M):
            gb.cyl(0.062, d.length, (0, 0, 0), seg=7, mat="M_Bark", r_top=0.042)
        tips.append((b1, a0))
        # 二级枝
        for j in range(2):
            a1 = a0 + (j - 0.5) * 1.1
            t0 = b1
            t1 = b1 + Vector((math.cos(a1) * r * 0.34, math.sin(a1) * r * 0.34,
                              h * 0.20))
            mid2 = (t0 + t1) / 2
            d2 = t1 - t0
            M2 = (Matrix.Translation(mid2) @ Matrix.Rotation(math.atan2(d2.y, d2.x), 4, "Z") @
                  Matrix.Rotation(math.atan2(math.hypot(d2.x, d2.y), d2.z), 4, "Y"))
            with gb.frame(M2):
                gb.cyl(0.034, d2.length, (0, 0, 0), seg=6, mat="M_Bark", r_top=0.022)
            tips.append((t1, a1))
    # 叶团
    for (base, ang) in tips:
        for m in range(9):
            rr = rng.uniform(0.05, 0.52)
            a2 = ang + rng.uniform(-1.1, 1.1)
            p2 = base + Vector((math.cos(a2) * rr, math.sin(a2) * rr,
                                rng.uniform(-0.10, 0.42)))
            sc = rng.uniform(0.10, 0.20)
            M3 = (Matrix.Translation(p2) @ Matrix.Rotation(rng.uniform(0, TAU), 4, "Z") @
                  Matrix.Rotation(rng.uniform(-0.5, 0.5), 4, "Y"))
            with gb.frame(M3):
                gb.sphere(sc, (0, 0, 0), seg=7, rings=5, mat=leaf,
                          scale=(1.7, 1.3, 0.55))


def bamboo(gb, n=14, radius=1.1, h=5.5, seed=0):
    rng = random.Random(seed or 5)
    for i in range(n):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.0, radius)
        x, y = math.cos(a) * rr, math.sin(a) * rr
        hh = h * rng.uniform(0.7, 1.12)
        lean = rng.uniform(-0.18, 0.18)
        rad = rng.uniform(0.022, 0.038)
        seg = 5
        for s in range(seg):
            t0, t1 = s / seg, (s + 1) / seg
            p0 = Vector((x + lean * hh * t0 * t0, y, hh * t0))
            p1 = Vector((x + lean * hh * t1 * t1, y, hh * t1))
            d = p1 - p0
            mid = (p0 + p1) / 2
            pitch = math.atan2(math.hypot(d.x, d.y), d.z)
            yaw = math.atan2(d.y, d.x)
            M = Matrix.Translation(mid) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "Y")
            with gb.frame(M):
                gb.cyl(rad, d.length * 1.01, (0, 0, 0), seg=7, mat="M_Bamboo")
                gb.cyl(rad * 1.12, 0.012, (0, 0, d.length / 2 * 0.92), seg=7, mat="M_Bamboo")
        # 叶
        for k in range(rng.randint(14, 22)):
            t = rng.uniform(0.40, 1.0)
            lx = x + lean * hh * t * t
            lz = hh * t
            ang = rng.uniform(0, TAU)
            sc = rng.uniform(0.7, 1.2)
            M = (Matrix.Translation((lx + math.cos(ang) * 0.22,
                                     y + math.sin(ang) * 0.22, lz)) @
                 Matrix.Rotation(ang + rng.uniform(-0.5, 0.5), 4, "Z") @
                 Matrix.Rotation(rng.uniform(-0.5, 0.5), 4, "Y"))
            with gb.frame(M):
                gb.sphere(0.055 * sc, (0, 0, 0), seg=5, rings=3,
                          mat="M_LeafOlive" if k % 3 else "M_LeafGreen",
                          scale=(3.4, 0.75, 0.22))


def shrub(gb, r=0.55, leaf="M_LeafGreen", seed=0):
    rng = random.Random(seed or int(r * 100))
    for k in range(5):
        a = TAU * k / 5 + rng.uniform(-0.3, 0.3)
        gb.sphere(r * rng.uniform(0.6, 0.9),
                  (math.cos(a) * r * 0.4, math.sin(a) * r * 0.4, r * rng.uniform(0.5, 0.85)),
                  seg=9, rings=6, mat=leaf, scale=(1.1, 1.1, 0.82))


def grass_tuft(gb, r=0.22, h=0.32, leaf="M_LeafPale", seed=0):
    rng = random.Random(seed or int(h * 500))
    for k in range(6):
        a = rng.uniform(0, TAU)
        gb.cyl(0.012, h, (0, 0, h / 2), seg=4, mat=leaf,
               rot=None)
        gb.box((0.012, 0.014, h * 0.8), (math.cos(a) * r * 0.3,
                                        math.sin(a) * r * 0.3, h * 0.45), mat=leaf)


def rock(gb, r=1.0, mat="M_StoneDark", seed=0, squash=0.55):
    rng = random.Random(seed or int(r * 1000))
    for k in range(3):
        sc = (rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0), rng.uniform(0.4, 0.75))
        off = (rng.uniform(-0.35, 0.35) * r, rng.uniform(-0.35, 0.35) * r,
               rng.uniform(0.15, 0.5) * r)
        gb.sphere(r * rng.uniform(0.55, 0.8), off, seg=9, rings=6, mat=mat,
                  scale=(sc[0], sc[1], sc[2] * squash), smooth=True)


def lotus(gb, r=0.16, leaf="M_Lotus"):
    gb.cyl(r, 0.012, (0, 0, 0.004), seg=14, mat=leaf)
    gb.sphere(r * 0.45, (0, 0, 0.05), seg=8, rings=5, mat="M_Porcelain",
              scale=(1, 1, 0.6))


def reeds(gb, n=10, h=1.1, seed=0):
    rng = random.Random(seed or 9)
    for i in range(n):
        x = rng.uniform(-0.5, 0.5)
        y = rng.uniform(-0.5, 0.5)
        hh = h * rng.uniform(0.6, 1.2)
        gb.cyl(0.008, hh, (x, y, hh / 2), seg=4, mat="M_LeafPale")
        gb.sphere(0.03, (x, y, hh), seg=6, rings=4, mat="M_LeafOlive",
                  scale=(1, 1, 2.4))


def tree_broad(gb, h=7.0, r=3.0, leaf="M_LeafGreen", seed=0):
    """高大乔木（银杏/香樟感），冠幅大，做背景林。"""
    rng = random.Random(seed or int(h * 61))
    gb.cyl(0.22, h * 0.55, (0, 0, h * 0.275), seg=10, mat="M_Bark", r_top=0.15)
    for k in range(5):
        a = TAU * k / 5 + rng.uniform(-0.3, 0.3)
        b0 = Vector((0, 0, h * 0.42))
        b1 = Vector((math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, h * 0.72))
        d = b1 - b0
        mid = (b0 + b1) / 2
        yaw = math.atan2(d.y, d.x)
        pitch = math.atan2(math.hypot(d.x, d.y), d.z)
        M = Matrix.Translation(mid) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "Y")
        with gb.frame(M):
            gb.cyl(0.09, d.length, (0, 0, 0), seg=7, mat="M_Bark")
    for k in range(22):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.15, r * 0.92)
        z = h * rng.uniform(0.55, 1.02)
        gb.sphere(rng.uniform(0.45, 0.85) * r * 0.45,
                  (math.cos(a) * rr, math.sin(a) * rr, z),
                  seg=9, rings=6, mat=leaf, scale=(1.2, 1.15, 0.62))
