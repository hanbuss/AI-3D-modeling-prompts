"""starship/lib/wings.py — 左右后掠翼（翼型剖面放样 + 翼面细节 + 翼尖灯）

设计要点（不许改坏的几处）：
1. 翼根不贴名义 y=1.60：船体肩部壳面 y 随 x 变化（x=-2.90 处 ≈1.905 → x=-11.60 处 ≈1.523），
   所以根截面每个顶点都用 hull.surf 反算 y = f(x, z)，直接铺在真实壳面上再 blend 到平面站位，
   接缝天然为零。
2. 翼型是 NACA 4 位风格厚度分布（上下表面各 15 个弦向站位），前缘圆、后缘 1% 厚度，不是两块平板。
3. 固定翼到 74.5% 弦长收口，襟翼/副翼各自独立放样，与固定翼留 6 mm 缝（真实铰链线）。
4. 翼根整流罩（fillet）：沿弦向 9 段 × 展向 6 环，径向偏置 0.100 → 0.020 递减，把根部接缝整个包住。
5. 翼刀 3 道 / 涡流片 10 片，展向等间距、平面内朝前缘倾 30°。
"""
import math
import bpy, bmesh
from mathutils import Vector

import kit
import hull
import spec as S

W = S.WING

# ---------------------------------------------------------------- 翼型参数
N_CHORD = 15            # 主翼弦向站位（上下表面各 15 点）
U_FIXED_TE = 0.745      # 固定翼弦向收口
GAP_M = 0.006           # 缝宽 6 mm
CAMBER_K = 0.008        # 弯度系数（× 当地弦长）
SPAN_S = [0.0, 0.012, 0.030, 0.055, 0.090, 0.140, 0.200, 0.270, 0.350,
          0.440, 0.530, 0.620, 0.710, 0.790, 0.860, 0.920, 0.962, 1.0]

_CACHE = {}

# 结构线（板缝/检修板都对齐它）
SPAR_U = (0.150, 0.420, 0.660)            # 前梁 / 主梁 / 后梁的弦向位置
PANEL_BAYS = ((0.172, 0.398), (0.442, 0.638))
PANEL_S = (0.108, 0.260, 0.412, 0.564, 0.716, 0.868)     # 展向每 ~1.2 m
PANEL_HW = 0.062
JOINT_S = (0.184, 0.336, 0.488, 0.640, 0.792, 0.944)
DARK_PANELS = (1, 6, 9, 11)               # 一片翼只留 4 块深色板


# ---------------------------------------------------------------- 船壳反算
def hull_y(x, z):
    """+Y 舷侧：给定 (x, z) 求壳面 y（二分 th，全走 hull.surf 官方 API）"""
    key = (round(x, 4), round(z, 4))
    if key in _CACHE:
        return _CACHE[key]
    lo, hi = -math.pi / 2, math.pi / 2
    plo = hull.surf(x, lo).z - z
    phi = hull.surf(x, hi).z - z
    if plo * phi > 0:
        y = hull.surf(x, 0.0).y
        _CACHE[key] = y
        return y
    for _ in range(46):
        mid = 0.5 * (lo + hi)
        pm = hull.surf(x, mid).z - z
        if (pm >= 0) == (plo >= 0):
            lo, plo = mid, pm
        else:
            hi, phi = mid, pm
    y = hull.surf(x, 0.5 * (lo + hi)).y
    _CACHE[key] = y
    return y


def y_ref():
    """翼根参考 y：真实壳面上、弦中、翼中线高度处的 y（spec.WING['root_y'] 只是名义值）"""
    xm = 0.5 * (W["root_le_x"] + W["root_te_x"])
    return hull_y(xm, W["root_z"])


# ---------------------------------------------------------------- 平面形状
def x_le(s):
    return W["root_le_x"] + (W["tip_le_x"] - W["root_le_x"]) * s


def x_te(s):
    return W["root_te_x"] + (W["tip_te_x"] - W["root_te_x"]) * s


def chord_at(s):
    return x_le(s) - x_te(s)


def zc_at(s):
    return W["root_z"] + (W["tip_z"] - W["root_z"]) * s


def th_at(s):
    return W["root_th"] + (W["tip_th"] - W["root_th"]) * s


def y_at_s(s):
    """平面站位 y（s=0 取真实壳面，s=1 正好是 spec 的 tip_y=9.60）"""
    y0 = y_ref()
    return y0 + (W["tip_y"] - y0) * s


def span_at_y(y):
    y0 = y_ref()
    return (y - y0) / (W["tip_y"] - y0)


# ---------------------------------------------------------------- 翼型
def _yt(u):
    """NACA 4 位厚度分布（u=0.3 处 ≈ 1.0）"""
    u = max(0.0, min(1.0, u))
    return 5.0 * (0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u ** 2
                  + 0.2843 * u ** 3 - 0.1015 * u ** 4)


def _camber(u, ch):
    return CAMBER_K * ch * 4.0 * u * (1.0 - u)


def _chord_u(i, n):
    """弦向余弦分布（前缘加密）"""
    return 0.5 * (1.0 - math.cos(math.pi * i / n))


def sec_point(s, u, up=True, thick_mul=1.0, ext_f=0.0, ext_a=0.0, sgn=1):
    """翼面上一点（u=0 前缘，u=1 后缘）；sgn=-1 取左舷镜像"""
    ch = chord_at(s)
    L = ch + ext_f + ext_a
    x = x_le(s) + ext_f - u * L
    half = 0.5 * th_at(s) * _yt(u) * thick_mul
    z = zc_at(s) + _camber(u, L) + (half if up else -half)
    y = y_at_s(s)
    bl = (1.0 - min(1.0, s / 0.12)) ** 1.5          # 根部 drape：贴真实壳面
    if bl > 1e-4:
        yh = hull_y(x, z) - 0.012
        y = y + bl * (yh - y)
    return Vector((x, y * sgn, z))


def sec_ring(s, u0=0.0, u1=1.0, thick_mul=1.0, ext_f=0.0, ext_a=0.0, sgn=1, nseg=None):
    """闭合翼型环（无重复顶点，后缘合并成薄后缘）；nseg = 弦向分段数"""
    n = nseg if nseg else N_CHORD
    us = [u0 + (u1 - u0) * _chord_u(i, n - 1) for i in range(n)]
    pts = [sec_point(s, u, True, thick_mul, ext_f, ext_a, sgn) for u in us[:-1]]
    for u in reversed(us[1:-1]):
        pts.append(sec_point(s, u, False, thick_mul, ext_f, ext_a, sgn))
    p1 = sec_point(s, us[-1], True, thick_mul, ext_f, ext_a, sgn)
    p2 = sec_point(s, us[-1], False, thick_mul, ext_f, ext_a, sgn)
    pts.append((p1 + p2) * 0.5)
    return pts


def skin(s, u, up=True, sgn=1):
    return sec_point(s, u, up, sgn=sgn)


def skin_n(s, u, up=True, sgn=1, eps=0.005):
    p = sec_point(s, u, up, sgn=sgn)
    du = sec_point(s, u + eps, up, sgn=sgn) - p
    ds = sec_point(s + eps, u, up, sgn=sgn) - p
    n = du.cross(ds)
    if n.length < 1e-9:
        return Vector((0, 0, 1 if up else -1))
    n.normalize()
    if (n.z < 0) == up:
        n = -n
    return n


# ---------------------------------------------------------------- 通用几何
def loft3d(name, rings, mat=None, col=None, close_start=True, close_end=True, smooth=False):
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(vr[0])
    for a, b in zip(vr[:-1], vr[1:]):
        for i in range(n):
            try:
                bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            except ValueError:
                pass
    for flag, ring in ((close_start, list(reversed(vr[0]))), (close_end, vr[-1])):
        if flag:
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col, smooth=smooth)


def plate4(name, q, nrm, t=0.010, mat=None, col=None):
    """四角平板（沿 nrm 挤出 t 厚）"""
    n = Vector(nrm).normalized() * (t / 2.0)
    vs = [Vector(p) + n for p in q] + [Vector(p) - n for p in q]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    bm = bmesh.new()
    vv = [bm.verts.new(v) for v in vs]
    for idx in faces:
        try:
            bm.faces.new([vv[i] for i in idx])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col)


def skin_patch(name, s0, s1, u0, u1, sgn=1, out=0.006, thick=0.012, nu=2, nv=3,
               up=True, mat=None, col=None, bevel=0.0026):
    """贴合翼面的曲面板（检修盖板 / 挂点加强板 / 蒙皮分缝条）——真实厚度 + 四边倒角"""
    o, i = [], []
    for a in range(nu + 1):
        s = s0 + (s1 - s0) * a / nu
        ro, ri = [], []
        for b in range(nv + 1):
            u = u0 + (u1 - u0) * b / nv
            p = skin(s, u, up, sgn)
            n = skin_n(s, u, up, sgn)
            ro.append(p + n * out)
            ri.append(p + n * (out - thick))
        o.append(ro)
        i.append(ri)
    bm = bmesh.new()
    vo = [[bm.verts.new(p) for p in row] for row in o]
    vi = [[bm.verts.new(p) for p in row] for row in i]
    for a in range(nu):
        for b in range(nv):
            bm.faces.new((vo[a][b], vo[a + 1][b], vo[a + 1][b + 1], vo[a][b + 1]))
            bm.faces.new((vi[a][b], vi[a][b + 1], vi[a + 1][b + 1], vi[a + 1][b]))
    for b in range(nv):
        bm.faces.new((vo[0][b], vo[0][b + 1], vi[0][b + 1], vi[0][b]))
        bm.faces.new((vo[nu][b], vi[nu][b], vi[nu][b + 1], vo[nu][b + 1]))
    for a in range(nu):
        bm.faces.new((vo[a][0], vi[a][0], vi[a + 1][0], vo[a + 1][0]))
        bm.faces.new((vo[a][nv], vo[a + 1][nv], vi[a + 1][nv], vi[a][nv]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bevel:
        kit.finish(ob, bevel, 1, 44.0)
    return ob


def skin_groove(name, s0, s1, u, hw=0.0030, depth=0.0040, n=10, up=True, sgn=1,
                mat=None, col=None):
    """翼面上的真实凹槽（4 mm 深、6 mm 宽）：底板 + 两侧壁，读起来是板缝不是贴条"""
    bm = bmesh.new()
    rows = []
    for i in range(n + 1):
        s = s0 + (s1 - s0) * i / n
        pa = skin(s, u - hw, up, sgn)
        pb = skin(s, u + hw, up, sgn)
        na = skin_n(s, u - hw, up, sgn)
        nb = skin_n(s, u + hw, up, sgn)
        rows.append((bm.verts.new(pa), bm.verts.new(pa - na * depth),
                     bm.verts.new(pb - nb * depth), bm.verts.new(pb)))
    for a, b in zip(rows[:-1], rows[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0]))      # 左侧壁
        bm.faces.new((a[1], a[2], b[2], b[1]))      # 槽底
        bm.faces.new((a[2], a[3], b[3], b[2]))      # 右侧壁
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col, smooth=True)


def le_fairing(name, sgn, Mx, col, segs=None):
    """前缘根部整流：沿前缘 6 段、半径 0.12 → 0.03 的过渡体，把翼前缘与船壳缝住"""
    segs = segs or [(0.000, 0.120), (0.017, 0.101), (0.034, 0.084),
                    (0.052, 0.067), (0.070, 0.047), (0.090, 0.030)]
    rings = []
    for (s, r) in segs:
        c = skin(s, 0.0, True, sgn)
        ax = span_dir(s, sgn)
        ez = Vector((0, 0, 1))
        ec = ax.cross(ez).normalized()
        ez2 = ec.cross(ax).normalized()
        rings.append([c + ec * (r * math.cos(a)) + ez2 * (r * math.sin(a))
                      for a in [math.tau * i / 10 for i in range(10)]])
    ob = loft3d(name, rings, mat=Mx['hull'], col=col, smooth=True)
    kit.finish(ob, 0.003, 1, 40.0)
    return ob


def span_dir(s, sgn=1):
    a = sec_point(max(0.0, s - 0.02), 0.5, True, sgn=sgn)
    b = sec_point(min(1.0, s + 0.02), 0.5, True, sgn=sgn)
    return (b - a).normalized()


def _bolt(name, p, r=0.016, h=0.013, mat=None, col=None, seg=6):
    return kit.cyl(name, r, h, axis='Z', loc=(p.x, p.y, p.z), mat=mat, col=col,
                   seg=seg, bw=0, segs=1)


# ================================================================ 主结构
def _main_wing(name, sgn, M, col):
    obs = []

    # ---- 主翼盒（0 → 74.5% 弦长）
    rings = [sec_ring(s, 0.0, U_FIXED_TE, sgn=sgn) for s in SPAN_S]
    wing = loft3d(name, rings, mat=M['hull'], col=col, smooth=True)
    kit.finish(wing, 0.006, 2, 40.0)
    obs.append(wing)

    # 前缘 D 形梁加强带（深色，勾出前缘轮廓）
    le_rings = [sec_ring(s, 0.0, 0.10, thick_mul=1.012, sgn=sgn) for s in SPAN_S[1:-1]]
    le = loft3d(name + "_le", le_rings, mat=M['hull_dark'], col=col, smooth=True)
    kit.finish(le, 0.0035, 1, 40.0)
    obs.append(le)

    # ---- 蒙皮板缝：3 条弦向凹槽（4 mm 深，对齐前梁/主梁/后梁）+ 展向对接缝（每 ~1.2 m）
    for si, u in enumerate(SPAR_U):
        for up in (True, False):
            obs.append(skin_groove("%s_gr%d%s" % (name, si, "u" if up else "d"),
                                   0.030, 0.978, u, hw=0.0030, depth=0.0040, n=11,
                                   up=up, sgn=sgn, mat=M['seam'], col=col))
    for si, s in enumerate(JOINT_S):
        for up in (True, False):
            obs.append(skin_patch("%s_bt%d%s" % (name, si, "u" if up else "d"),
                                  s - 0.0014, s + 0.0014, 0.13, 0.715, sgn=sgn,
                                  out=0.0030, thick=0.004, nu=1, nv=6, up=up,
                                  mat=M['hull_dark'], col=col, bevel=0.0008))

    # ---- 后缘分块：2 块固定结构（翼根 / 翼尖）+ 襟翼副翼 3 块，全部留 6 mm 缝
    gu = GAP_M / chord_at(0.5)
    gs = GAP_M / (W["tip_y"] - y_ref())
    te_pieces = [
        (0.004, 0.110, "te_root", None),
        (0.110 + gs, 0.368, "flap_in", (0.10, 0.50, 0.90)),
        (0.368 + gs, 0.616, "flap_out", (0.10, 0.50, 0.90)),
        (0.616 + gs, 0.872, "aileron", (0.12, 0.50, 0.88)),
        (0.872 + gs, 0.997, "te_tip", None),
    ]
    for s0, s1, tag, hinges in te_pieces:
        us = [s0, (s0 + s1) * 0.5, s1]
        cs = loft3d("%s_%s" % (name, tag),
                    [sec_ring(s, U_FIXED_TE + gu, 1.0, sgn=sgn) for s in us],
                    mat=M['hull'], col=col, smooth=True)
        kit.finish(cs, 0.003, 1, 40.0)
        obs.append(cs)
        for k in (hinges or ()):
            s = s0 + (s1 - s0) * k
            base = skin(s, U_FIXED_TE + gu, True, sgn)
            ax = span_dir(s, sgn)
            hinge = kit.cyl("%s_%s_hg%d" % (name, tag, int(k * 10)), 0.021, 0.15, axis='Y',
                            loc=(0, 0, 0), mat=M['frame'], col=col, seg=10, bw=0.0012, segs=1)
            hinge.matrix_world = kit.mat_from_axes(ax.cross(Vector((1, 0, 0))).normalized(),
                                                   ax, Vector((1, 0, 0)))
            hinge.location = Vector((base.x, base.y, base.z - 0.014))
            obs.append(hinge)
            obs.append(kit.box("%s_%s_lug%d" % (name, tag, int(k * 10)), (0.11, 0.055, 0.055),
                               loc=(base.x, base.y, base.z - 0.055),
                               mat=M['frame'], col=col, bw=0.0014, seg=1))
        obs.append(kit.finish(loft3d("%s_%s_te" % (name, tag),
                                     [sec_ring(s, 0.962, 1.0, sgn=sgn) for s in us],
                                     mat=M['hull_dark'], col=col, smooth=True),
                              0.0016, 1, 40.0))

    # ---- 翼刀 3 道（沿展向等间距，平面内朝前缘倾 30°）
    for k, sf in enumerate((0.215, 0.325, 0.435)):
        u0, u1, h = 0.085, 0.470, 0.082
        lean = h * math.tan(math.radians(30.0))
        q = []
        for u in (u0, u1):
            p = skin(sf, u, True, sgn)
            q.append(Vector((p.x, p.y, p.z - 0.016)))
        for u in (u1, u0):
            p = skin(sf, u, True, sgn)
            q.append(Vector((p.x + lean, p.y, p.z + h)))
        fence = plate4("%s_fence%d" % (name, k), q, Vector((0, 1, 0)), 0.014,
                       mat=M['hull_dark'], col=col)
        kit.finish(fence, 0.0018, 1, 40.0)
        obs.append(fence)

    # ---- 涡流发生器 10 片（展向等间距，平面内朝前缘倾 30°）
    for k in range(10):
        s = 0.300 + 0.0585 * k
        p0 = skin(s, 0.075, True, sgn)
        p1 = skin(s, 0.190, True, sgn)
        h, lean = 0.050, 0.050 * math.tan(math.radians(30.0))
        q = [Vector((p0.x, p0.y, p0.z - 0.006)),
             Vector((p1.x, p1.y, p1.z - 0.006)),
             Vector((p0.x + lean, p0.y, p0.z + h)),
             Vector((p0.x + lean + 0.020, p0.y, p0.z + h * 0.45))]
        obs.append(plate4("%s_vg%d" % (name, k), q, Vector((0, 1, 0)), 0.006,
                          mat=M['alu'], col=col))

    # ---- 上表面检修板：对齐梁位（3 条弦向）+ 每 ~1.2 m 一道展向结构线，一片翼 12 块
    #      只有 4 块是深色（其余同主色），不再出现"棋盘"观感
    panels = []
    for bi, (ua, ub) in enumerate(PANEL_BAYS):
        for ri, s in enumerate(PANEL_S):
            panels.append((s - PANEL_HW, s + PANEL_HW, ua, ub))
    for i, (s0, s1, ua, ub) in enumerate(panels):
        dark = i in DARK_PANELS
        obs.append(skin_patch("%s_pnl%d" % (name, i), s0, s1, ua, ub, sgn=sgn,
                              out=0.0042, thick=0.0090, nu=2, nv=3, up=True,
                              mat=M['hull_dark'] if dark else M['hull'], col=col,
                              bevel=0.0024))
        for (ds, du) in ((0.10, 0.14), (0.10, 0.86), (0.90, 0.14), (0.90, 0.86),
                         (0.50, 0.14), (0.50, 0.86)):
            s = s0 + (s1 - s0) * ds
            u = ua + (ub - ua) * du
            p = skin(s, u, True, sgn) + skin_n(s, u, True, sgn) * 0.008
            obs.append(_bolt("%s_pnl%db%d" % (name, i, int(du * 100)), p, 0.014, 0.011,
                             mat=M['alu'], col=col))

    # ---- 下表面：挂点加强板 ×2 + 挂点耳片 + 检修口 ×2
    for i, (py, _xl, _xt, _n) in enumerate(S.PYLONS):
        s = span_at_y(py)
        obs.append(skin_patch("%s_hard%d" % (name, i), s - 0.072, s + 0.072, 0.50, 0.80,
                              sgn=sgn, out=0.005, thick=0.016, nu=2, nv=2, up=False,
                              mat=M['frame'], col=col, bevel=0.0028))
        for k, u in enumerate((0.56, 0.74)):
            p = skin(s, u, False, sgn)
            obs.append(kit.box("%s_hardlug%d_%d" % (name, i, k), (0.17, 0.032, 0.10),
                               loc=(p.x, p.y, p.z - 0.065),
                               mat=M['gunmetal'], col=col, bw=0.0016, seg=1))
    for i, s in enumerate((0.235, 0.665)):
        obs.append(skin_patch("%s_lowp%d" % (name, i), s - 0.055, s + 0.055, 0.24, 0.44,
                              sgn=sgn, out=0.005, thick=0.010, nu=2, nv=2, up=False,
                              mat=M['hull_dark'], col=col))

    # ---- 前缘根部整流（6 段、半径 0.12 → 0.03）：把翼前缘与船壳缝住
    obs.append(le_fairing(name + "_lefair", sgn, M, col))

    # ---- 翼根整流罩（fillet）：沿弦向 9 段 × 展向 6 环，偏置 0.100 → 0.020
    th0 = W["root_th"]
    fair = [(0.000, 0.100, 0.130), (0.055, 0.088, 0.112), (0.130, 0.074, 0.092),
            (0.225, 0.058, 0.070), (0.340, 0.038, 0.046), (0.470, 0.020, 0.024)]
    rr = []
    for (dy, off, ext) in fair:
        infl = (th0 + 2.0 * off) / th0
        ring = sec_ring(0.0, 0.012, 0.995, thick_mul=infl, ext_f=ext, ext_a=ext * 1.25,
                        sgn=1, nseg=10)
        rr.append([Vector((p.x, (p.y + dy) * sgn, p.z)) for p in ring])
    collar = loft3d(name + "_rootfair", rr, mat=M['hull'], col=col, smooth=True)
    kit.finish(collar, 0.0035, 1, 40.0)
    obs.append(collar)

    # 整流罩外缘一圈紧固件（贴在罩面收口处）
    ring_out = rr[-1]
    nout = len(ring_out)
    for k in range(1, nout - 1, 2):
        p = ring_out[k]
        obs.append(_bolt("%s_frf%d" % (name, k), Vector((p.x, p.y, p.z + 0.010 * (1 if p.z > zc_at(0) else -1))),
                         0.014, 0.011, mat=M['alu'], col=col))

    # ---- 翼尖：整流罩 + 端板 + 挂架 + 导轨
    tip_rings = []
    for (yy, infl) in ((0.0, 1.03), (0.070, 1.0), (0.128, 0.84)):
        ring = sec_ring(1.0, 0.0, 1.0, thick_mul=infl, sgn=1)
        tip_rings.append([Vector((p.x, (p.y + yy) * sgn, p.z)) for p in ring])
    obs.append(kit.finish(loft3d(name + "_tipfair", tip_rings, mat=M['hull'], col=col,
                                 smooth=True), 0.0035, 1, 40.0))

    p_le = skin(0.985, 0.02, True, sgn)
    p_te = skin(0.985, 0.98, True, sgn)
    q = [Vector((p_le.x, p_le.y + 0.145 * sgn, p_le.z + 0.010)),
         Vector((p_te.x, p_te.y + 0.145 * sgn, p_te.z + 0.004)),
         Vector((p_te.x, p_te.y + 0.145 * sgn, p_te.z - 0.014)),
         Vector((p_le.x, p_le.y + 0.145 * sgn, p_le.z - 0.038))]
    obs.append(kit.finish(plate4("%s_endplate" % name, q, Vector((0, 1, 0)), 0.016,
                                 mat=M['hull_dark'], col=col), 0.002, 1, 40.0))

    py = skin(1.0, 0.0, True, sgn)
    pyl = []
    for (t, r) in ((0.0, 0.026), (0.18, 0.050), (0.55, 0.048), (0.85, 0.036), (1.0, 0.020)):
        x = p_le.x - 0.58 + 0.58 * t
        pyl.append([Vector((x, py.y + r * math.cos(a) * sgn, py.z + 0.02 + r * math.sin(a) * 0.9))
                    for a in [math.tau * i / 10 for i in range(10)]])
    obs.append(kit.finish(loft3d("%s_tippylon" % name, pyl, mat=M['gunmetal'], col=col,
                                 smooth=True), 0.002, 1, 40.0))
    obs.append(kit.box("%s_tiprail" % name, (0.66, 0.030, 0.042),
                       loc=(p_le.x - 0.32, py.y, py.z - 0.048),
                       mat=M['frame'], col=col, bw=0.0015, seg=1))

    # ---- 航行灯：右绿左红（sgn>0 = 右舷 = 绿）+ 上下频闪
    lamp_mat = M['led_green'] if sgn > 0 else M['led_red']
    lx = p_le.x - 0.10
    obs.append(kit.cyl("%s_navh" % name, 0.060, 0.055, axis='Y',
                       loc=(lx, py.y - 0.012 * sgn, py.z + 0.022),
                       mat=M['black'], col=col, seg=14, bw=0.002, segs=1))
    obs.append(kit.cyl("%s_navlens" % name, 0.048, 0.050, axis='Y',
                       loc=(lx, py.y + 0.030 * sgn, py.z + 0.022),
                       mat=lamp_mat, col=col, seg=14, bw=0.0014, segs=1, r2=0.017))
    for k, dz in ((0, 0.058), (1, -0.052)):
        obs.append(kit.cyl("%s_strobe%d" % (name, k), 0.040, 0.042, axis='Z',
                           loc=(p_le.x - 0.30, py.y, py.z + dz), mat=M['led'], col=col,
                           seg=12, bw=0.0014, segs=1, r2=0.025))
        obs.append(kit.cyl("%s_strobec%d" % (name, k), 0.050, 0.018, axis='Z',
                           loc=(p_le.x - 0.30, py.y, py.z + dz + (0.026 if k == 0 else -0.026)),
                           mat=M['black'], col=col, seg=12, bw=0.001, segs=1))
    return obs


# ================================================================ build
def build(M, col):
    out = []
    for sgn, pid, zh, en, order, note in (
            (1, "wing_stbd", "右机翼", "Starboard Wing", 50,
             "肩部上单翼：NACA 剖面 18 站位×24 点、固定翼 0–74.5% 弦长、襟翼/副翼 6mm 缝+铰链；"
             "翼根 fillet 沿弦向 9 段×展向 6 环（偏置 0.10→0.02）；13 块检修板（9mm 厚+12 螺栓）；"
             "3 道翼刀 + 10 片涡流发生器（30° 前倾）；翼尖绿航行灯+双频闪"),
            (-1, "wing_port", "左机翼", "Port Wing", 52,
             "左舷镜像件：翼根按真实肩部壳面（y 1.523–1.905 随弦向变化）铺贴；翼尖红航行灯")):
        obs = [o for o in _main_wing(pid, sgn, M, col) if o]
        ob = kit.join(obs, pid)
        kit.part(ob, pid, zh, en, "wings", (0, sgn, 0.12), order=order, note=note)
        out.append(ob)
    return out
