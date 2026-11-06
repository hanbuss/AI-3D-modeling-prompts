# -*- coding: utf-8 -*-
"""背景邻栋 —— 两层的现代住宅。

语言跟 arch2 的主宅同族（浅色石材大板 / 近黑金属收边 / 洞口真的开在墙上、
玻璃内凹 0.10 / 平屋面薄挑檐），但细节量只有主宅的 15~25%：
一栋 1.5k~3.5k 面，25 m 外读的是轮廓、二层分线、窗洞阴影和屋面。

局部坐标：原点 = 户型中心，底面 z = 0，+X 向右，街道在 −Y 一侧。
外部唯一入口：neighbour(gb, x, y, w, d, h, variant, rot)。
"""
import math
import random
from mathutils import Matrix

# ---------------------------------------------------------------- 尺度常量
TE = 0.28          # 外墙厚（洞口的进深就靠它，太薄内凹看不出来）
INS = 0.10         # 玻璃内凹：离外皮 0.10
OV = 0.30          # 檐口出挑
SIDE_IN = 0.20     # 房体左右退距（给出挑檐余量）
BACK_IN = 0.20
SETBACK = 1.20     # 临街退距 = 前院进深
ROOF_Z = 0.46      # 屋面区总高：板 0.14 + 女儿墙 0.32

# ---------------------------------------------------------------- 材质族
_GLASS = "M_GlassTint"
_TRIM = "M_SteelDark"
_BAND = "M_Fascia"
_ROOF = "M_RoofMembrane"


# ================================================================ 基本件
def _bx(gb, x0, x1, y0, y1, z0, z1, mat):
    if x1 - x0 <= 1e-4 or y1 - y0 <= 1e-4 or z1 - z0 <= 1e-4:
        return
    gb.box((x1 - x0, y1 - y0, z1 - z0),
           ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5), mat=mat)


def _ab(gb, axis, a0, a1, t0, t1, z0, z1, mat):
    """axis="X" 时 a 走 X、t 走 Y；"Y" 时 a 走 Y、t 走 X。"""
    if axis == "X":
        _bx(gb, a0, a1, t0, t1, z0, z1, mat)
    else:
        _bx(gb, t0, t1, a0, a1, z0, z1, mat)


def _wall(gb, axis, a0, a1, t0, t1, z0, z1, mat, ops=()):
    """带洞口的墙。洞是真的空的：墙体被拆成 sill / lintel / jamb 若干块。

    洞口的侧面自带墙体本身的材质面，等于免费得到一个有进深的窗套。
    """
    pieces = [(a0, a1, z0, z1)]
    for (oa0, oa1, oz0, oz1) in ops:
        oa0, oa1 = max(a0, oa0), min(a1, oa1)
        oz0, oz1 = max(z0, oz0), min(z1, oz1)
        if oa1 - oa0 <= 1e-4 or oz1 - oz0 <= 1e-4:
            continue
        newp = []
        for (pu0, pu1, pz0, pz1) in pieces:
            if (oa1 <= pu0 + 1e-4 or oa0 >= pu1 - 1e-4 or
                    oz1 <= pz0 + 1e-4 or oz0 >= pz1 - 1e-4):
                newp.append((pu0, pu1, pz0, pz1))
                continue
            if oa0 > pu0 + 1e-4:
                newp.append((pu0, oa0, pz0, pz1))
            if oa1 < pu1 - 1e-4:
                newp.append((oa1, pu1, pz0, pz1))
            ix0, ix1 = max(pu0, oa0), min(pu1, oa1)
            if oz0 > pz0 + 1e-4:
                newp.append((ix0, ix1, pz0, oz0))
            if oz1 < pz1 - 1e-4:
                newp.append((ix0, ix1, oz1, pz1))
        pieces = newp
    for (pu0, pu1, pz0, pz1) in pieces:
        _ab(gb, axis, pu0, pu1, t0, t1, pz0, pz1, mat)


def _shell(gb, b, z0, z1, mat, opf=(), opb=(), opl=(), opr=()):
    """四面外墙一圈（墙角让给前后墙，避免共面 z-fighting）。"""
    x0, x1, y0, y1 = b
    _wall(gb, "X", x0, x1, y0, y0 + TE, z0, z1, mat, opf)
    _wall(gb, "X", x0, x1, y1 - TE, y1, z0, z1, mat, opb)
    _wall(gb, "Y", y0 + TE, y1 - TE, x0, x0 + TE, z0, z1, mat, opl)
    _wall(gb, "Y", y0 + TE, y1 - TE, x1 - TE, x1, z0, z1, mat, opr)


def _glaze(gb, axis, a0, a1, t0, t1, z0, z1, glass=_GLASS, cols=2,
           frame=_TRIM, fw=0.05, back="M_SteelDarker", bdir=1):
    """内凹玻璃 + 细框 + 竖挺。调用方把 t0/t1 放在外皮内 0.10 处。

    两个"共面"坑（都会在近景里变成锯齿）：
    ① 框不能贴死洞口 —— 与墙的切面共面会 z-fighting，框整体内缩 5 mm；
    ② 玻璃不能顶到框内口 —— 再内缩 5 mm。
    半透玻璃背后还要压一块深色背板，否则会透到对面墙、远看是块发白的塑料。
    """
    E = 0.005
    fa0, fa1 = a0 + E, a1 - E
    fz0, fz1 = z0 + E, z1 - E
    if fa1 - fa0 < 2 * fw + 0.09 or fz1 - fz0 < 2 * fw + 0.09:
        return
    if back:
        mid = (t0 + t1) * 0.5 + bdir * 0.030
        _ab(gb, axis, fa0 + fw, fa1 - fw, mid - 0.005, mid + 0.005,
            fz0 + fw, fz1 - fw, back)
    _ab(gb, axis, fa0 + fw + E, fa1 - fw - E, t0 + 0.004, t1 - 0.004,
        fz0 + fw + E, fz1 - fw - E, glass)
    _ab(gb, axis, fa0, fa1, t0, t1, fz1 - fw, fz1, frame)
    _ab(gb, axis, fa0, fa1, t0, t1, fz0, fz0 + fw, frame)
    _ab(gb, axis, fa0, fa0 + fw, t0, t1, fz0, fz1, frame)
    _ab(gb, axis, fa1 - fw, fa1, t0, t1, fz0, fz1, frame)
    for i in range(1, max(1, cols)):
        u = fa0 + (fa1 - fa0) * i / cols
        _ab(gb, axis, u - 0.018, u + 0.018, t0, t1, fz0, fz1, frame)


def _win(gb, side, b, a0, a1, z0, z1, glass=_GLASS, cols=2, sill=None):
    """side: F 临街 / B 背街 / L 左(X−) / R 右(X+)。b = 该体块外皮。

    sill 给材质名时在洞下压一道 0.06 挑出的窗台石（远看是窗户的"落地证明"）。
    """
    x0, x1, y0, y1 = b
    if side == "F":
        _glaze(gb, "X", a0, a1, y0 + INS, y0 + INS + 0.04, z0, z1, glass, cols,
               bdir=1)
    elif side == "B":
        _glaze(gb, "X", a0, a1, y1 - INS - 0.04, y1 - INS, z0, z1, glass, cols,
               bdir=-1)
    elif side == "L":
        _glaze(gb, "Y", a0, a1, x0 + INS, x0 + INS + 0.04, z0, z1, glass, cols,
               bdir=1)
    else:
        _glaze(gb, "Y", a0, a1, x1 - INS - 0.04, x1 - INS, z0, z1, glass, cols,
               bdir=-1)
    if not sill:
        return
    if side == "F":
        _bx(gb, a0 - 0.06, a1 + 0.06, y0 - 0.05, y0 + 0.03, z0 - 0.07, z0, sill)
    elif side == "B":
        _bx(gb, a0 - 0.06, a1 + 0.06, y1 - 0.03, y1 + 0.05, z0 - 0.07, z0, sill)
    elif side == "L":
        _bx(gb, x0 - 0.05, x0 + 0.03, a0 - 0.06, a1 + 0.06, z0 - 0.07, z0, sill)
    else:
        _bx(gb, x1 - 0.03, x1 + 0.05, a0 - 0.06, a1 + 0.06, z0 - 0.07, z0, sill)


def _spread(a0, a1, n, win, edge=0.85, gap=0.70):
    """在一段墙内等距排 n 个窗，返回 [(u0, u1)]。"""
    span = (a1 - a0) - 2.0 * edge
    if span <= 0.4 or n <= 0:
        return []
    w = min(win, (span - (n - 1) * gap) / n)
    if w < 0.62:
        return [(a0 + (a1 - a0) * 0.5 - 0.35, a0 + (a1 - a0) * 0.5 + 0.35)]
    total = n * w + (n - 1) * gap
    s = a0 + edge + (span - total) * 0.5
    return [(s + i * (w + gap), s + i * (w + gap) + w) for i in range(n)]


def _clip(a0, a1, blocks):
    """把 [a0,a1] 里被 blocks 盖住的部分挖掉，返回若干段。"""
    segs = [(a0, a1)]
    for (c0, c1) in blocks:
        nxt = []
        for (s0, s1) in segs:
            if c1 <= s0 + 1e-4 or c0 >= s1 - 1e-4:
                nxt.append((s0, s1))
                continue
            if c0 > s0 + 1e-4:
                nxt.append((s0, c0))
            if c1 < s1 - 1e-4:
                nxt.append((c1, s1))
        segs = nxt
    return segs


def _face_lines(gb, side, b, a0, a1, z0, z1, nz=2, nx=3,
                mat="M_GraniteEdge", w=0.018, ops=()):
    """石材板缝：贴面 6 mm 的细线（分缝不靠贴图，跟主宅一个路子）。

    ops 传该立面的洞口，缝要绕开洞口 —— 否则一道道线会横穿玻璃。
    """
    x0, x1, y0, y1 = b
    if side == "F":
        t0, t1 = y0 - 0.006, y0 + 0.030
        axis = "X"
    elif side == "B":
        t0, t1 = y1 - 0.030, y1 + 0.006
        axis = "X"
    elif side == "L":
        t0, t1 = x0 - 0.006, x0 + 0.030
        axis = "Y"
    else:
        t0, t1 = x1 - 0.030, x1 + 0.006
        axis = "Y"
    for i in range(1, nz + 1):
        z = z0 + (z1 - z0) * i / (nz + 1.0)
        blocks = [(o[0], o[1]) for o in ops if o[2] - 0.02 < z < o[3] + 0.02]
        for (s0, s1) in _clip(a0, a1, blocks):
            _ab(gb, axis, s0, s1, t0, t1, z, z + w, mat)
    for i in range(1, nx + 1):
        u = a0 + (a1 - a0) * i / (nx + 1.0)
        blocks = [(o[2], o[3]) for o in ops if o[0] - 0.02 < u < o[1] + 0.02]
        for (s0, s1) in _clip(z0, z1, blocks):
            _ab(gb, axis, u, u + w, t0, t1, s0, s1, mat)


def _roof_bits(gb, b, zdeck, x_dim=1):
    """屋面小件：2 个雨水口 + 1 个检修口。远景里这几块就是"有人在维护"的证据。"""
    x0, x1, y0, y1 = b
    for xx in (x0 + 0.55, x1 - 0.55):
        _bx(gb, xx - 0.10, xx + 0.10, y0 + 0.20, y0 + 0.40,
            zdeck - 0.04, zdeck + 0.03, _TRIM)
    _bx(gb, x0 + 0.35, x0 + 0.35 + 0.62, y1 - 0.95, y1 - 0.32,
        zdeck - 0.02, zdeck + 0.14, _TRIM)


def _side_wins(a0, a1, n, win, edge=0.50, gap=0.35):
    """在一段墙 [a0,a1] 里排 n 个窗，严格不越界（用来避开入户门洞）。"""
    if a1 - a0 <= 2 * edge + 0.55:
        return []
    span = (a1 - a0) - 2 * edge - (n - 1) * gap
    if span <= 0.55:
        return []
    w = min(win, span / n)
    total = n * w + (n - 1) * gap
    s0 = a0 + edge + ((a1 - a0) - 2 * edge - total) * 0.5
    return [(s0 + i * (w + gap), s0 + i * (w + gap) + w) for i in range(n)]


def _slats(gb, axis, a0, a1, t0, t1, z0, z1, w=0.07, gap=0.06,
           mat="M_SlatTeak"):
    """竖向木格栅：条宽 w、间隙 gap，居中铺满 a0~a1。"""
    span = a1 - a0
    if span < w * 1.5:
        return
    n = max(1, int((span + gap) / (w + gap)))
    total = n * w + (n - 1) * gap
    s = a0 + (span - total) * 0.5
    for i in range(n):
        u = s + i * (w + gap)
        _ab(gb, axis, u, u + w, t0, t1, z0, z1, mat)


def _prism_x(gb, x0, x1, profile, mat):
    """把 (y, z) 剖面沿 X 挤出 —— 用来做单坡屋面 / 坡顶下的填充楔块。"""
    gb.prism(profile, x1 - x0, center=((x0 + x1) * 0.5, 0.0, 0.0),
             axis="X", mat=mat)


# ================================================================ 竖向
def _levels(h):
    """(0.12 台基顶, 一层墙顶, 分线带上沿=二层墙底, 二层墙顶)。"""
    wh = max(2.25, (h - 0.12 - 0.18 - ROOF_Z) / 2.0)
    g0 = 0.12
    g1 = g0 + wh
    b1 = g1 + 0.18
    u1 = b1 + wh
    return g0, g1, b1, u1


def _band(gb, b, g1, b1, spandrel):
    """楼板分线：0.18 高一条，底下 0.06 深色金属条外凸 0.05（远看就是两层）。"""
    x0, x1, y0, y1 = b
    _bx(gb, x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, g1 + 0.07, b1, spandrel)
    _bx(gb, x0 - 0.065, x1 + 0.065, y0 - 0.065, y1 + 0.065,
        g1 - 0.01, g1 + 0.07, _BAND)


def _roof_flat(gb, b, u1, h, parapet_mat):
    """平屋面：出挑 0.30 的深色檐口 + 卷材 + 0.32 女儿墙（压顶深色）。"""
    x0, x1, y0, y1 = b
    _bx(gb, x0 - OV, x1 + OV, y0 - OV, y1 + OV, u1, u1 + 0.14, _BAND)
    _bx(gb, x0 + 0.02, x1 - 0.02, y0 + 0.02, y1 - 0.02,
        u1 + 0.14, u1 + 0.17, _ROOF)
    ring = ((x0, x0 + 0.16, y0, y1), (x1 - 0.16, x1, y0, y1),
            (x0 + 0.16, x1 - 0.16, y0, y0 + 0.16),
            (x0 + 0.16, x1 - 0.16, y1 - 0.16, y1))
    for (a0, a1, c0, c1) in ring:
        _bx(gb, a0, a1, c0, c1, u1 + 0.14, h - 0.05, parapet_mat)
        _bx(gb, a0 - 0.028, a1 + 0.028, c0 - 0.028, c1 + 0.028,
            h - 0.05, h, _BAND)


# ================================================================ 入口
def _entry(gb, x0, x1, yface, z0, z1, canopy=True, step_mat="M_PaveSand"):
    """内凹玻璃门（0.14）+ 门套 + 雨棚 + 两级踏步。门洞已由 _wall 开出。"""
    cw = x1 - x0
    yb = yface + 0.14
    _bx(gb, x0, x0 + 0.055, yb, yb + 0.06, z0, z1, _TRIM)
    _bx(gb, x1 - 0.055, x1, yb, yb + 0.06, z0, z1, _TRIM)
    _bx(gb, x0, x1, yb, yb + 0.06, z1 - 0.055, z1, _TRIM)
    _bx(gb, x0 + 0.055, x1 - 0.055, yb + 0.06, yb + 0.08, z0 + 0.02,
        z1 - 0.055, "M_SteelDarker")
    _bx(gb, x0 + 0.058, x1 - 0.058, yb + 0.012, yb + 0.05, z0 + 0.023,
        z1 - 0.058, _GLASS)
    if cw > 1.5:                                    # 双扇中挺
        cxm = (x0 + x1) * 0.5
        _bx(gb, cxm - 0.028, cxm + 0.028, yb - 0.01, yb + 0.07, z0, z1, _TRIM)
    # 雨棚（薄板 + 深色收边）
    if canopy:
        _bx(gb, x0 - 0.45, x1 + 0.45, yface - 0.95, yface + 0.12,
            z1 + 0.16, z1 + 0.27, _TRIM)
        _bx(gb, x0 - 0.45, x1 + 0.45, yface - 0.95, yface - 0.90,
            z1 + 0.11, z1 + 0.16, _BAND)
    # 踏步
    _bx(gb, x0 - 0.45, x1 + 0.45, yface - 0.62, yface - 0.30, 0.0, 0.06, step_mat)
    _bx(gb, x0 - 0.30, x1 + 0.30, yface - 0.30, yface, 0.0, 0.12, step_mat)


# ================================================================ 阳台
def _balcony(gb, x0, x1, yface, z0, depth=1.35, rail="M_GlassRail"):
    """出挑阳台：板 0.14 + 玻璃栏板 1.02 + 深色扶手 + 立柱。"""
    y1 = yface - depth
    _bx(gb, x0 - 0.06, x1 + 0.06, y1, yface + 0.02, z0 - 0.02, z0 + 0.12, _BAND)
    _bx(gb, x0, x1, y1 + 0.02, yface, z0 + 0.12, z0 + 0.135, "M_PaveSand")
    top = z0 + 0.12 + 1.02
    # 玻璃栏板（三面）+ 扶手
    _bx(gb, x0 + 0.02, x1 - 0.02, y1 + 0.02, y1 + 0.045, z0 + 0.13, top, rail)
    _bx(gb, x0, x0 + 0.025, y1 + 0.02, yface - 0.04, z0 + 0.13, top, rail)
    _bx(gb, x1 - 0.025, x1, y1 + 0.02, yface - 0.04, z0 + 0.13, top, rail)
    _bx(gb, x0, x1, y1 + 0.02, y1 + 0.05, top, top + 0.05, _TRIM)
    for xx in (x0, x1):
        _bx(gb, xx - 0.022, xx + 0.022, y1 + 0.02, y1 + 0.05,
            z0 + 0.13, top + 0.05, _TRIM)
    # 从二层墙上挑出的斜撑（避免"浮着"的观感）
    for xx in (x0 + 0.18, x1 - 0.18):
        _bx(gb, xx - 0.03, xx + 0.03, y1 + 0.10, yface - 0.10,
            z0 - 0.34, z0 - 0.28, _TRIM)


# ================================================================ 前院
def _garden(gb, w, d, rng, tree=True, door_x=0.0):
    """临街前院：围墙 + 绿篱 + 门柱 + 汀步 + 植物，全部落在 w×d 之内。

    门洞与汀步都跟着入户门走（door_x）—— 院子中心线和门不对齐，
    25 m 外看就是"路没通到门口"。
    """
    yw0 = -d / 2 + 0.02
    yw1 = yw0 + 0.20
    px0, px1 = -w / 2 + 0.06, w / 2 - 0.06
    gate = 1.28                                     # 门洞半宽
    gw0, gw1 = max(px0, door_x - gate), min(px1, door_x + gate)
    H_LOW, H_END = 0.52, 1.60
    for (a0, a1) in ((px0, gw0), (gw1, px1)):
        if a1 - a0 < 0.30:
            continue
        _bx(gb, a0, a1, yw0 + 0.02, yw1, 0.0, H_LOW, "M_Concrete")
        _bx(gb, a0, a1, yw0 - 0.01, yw1 + 0.04, H_LOW, H_LOW + 0.05, _BAND)
    # 两侧 1.6 m 短翼（顺 Y 向后，不挡临街立面）
    for sx in (-1.0, 1.0):
        e0 = w * 0.5 * sx - 0.11 * sx
        _bx(gb, min(e0, e0 + 0.16 * sx), max(e0, e0 + 0.16 * sx),
            yw0, yw0 + 0.95, 0.0, H_END, "M_Concrete")
        _bx(gb, min(e0, e0 + 0.16 * sx) - 0.03,
            max(e0, e0 + 0.16 * sx) + 0.03,
            yw0 - 0.02, yw0 + 0.98, H_END, H_END + 0.06, _BAND)
    for xx in (gw0, gw1):
        _bx(gb, xx - 0.17, xx + 0.17, yw0 - 0.04, yw1 + 0.04, 0.0, 1.72,
            "M_LimeStone")
        _bx(gb, xx - 0.20, xx + 0.20, yw0 - 0.07, yw1 + 0.07, 1.72, 1.78, _BAND)
    # 绿篱：连续一条（不是一颗颗方块），顶上再压几块做高度起伏
    hy0, hy1 = yw1 - 0.04, yw1 + 0.62
    for (s0, s1) in ((px0 + 0.20, gw0 - 0.16), (gw1 + 0.16, px1 - 0.20)):
        if s1 - s0 < 0.5:
            continue
        _bx(gb, s0, s1, hy0, hy1, 0.02, 0.96, "M_LeafBox")
        n = max(2, int((s1 - s0) / 1.05))
        for i in range(n):
            u0 = s0 + (s1 - s0) * i / n
            u1 = s0 + (s1 - s0) * (i + 1) / n
            _bx(gb, u0, u1, hy0 + 0.03, hy1 - 0.03, 0.96,
                1.02 + rng.uniform(0.0, 0.22), "M_LeafBox")
    # 汀步：门洞 → 门口
    _bx(gb, door_x - 0.78, door_x + 0.78, yw1, -d / 2 + SETBACK, 0.0, 0.045,
        "M_PaveSand")
    _bx(gb, door_x - 0.88, door_x + 0.88, yw0 - 0.02, yw1, 0.0, 0.05,
        "M_PaveGrey")
    # 院内植物：落在两个角上（不在窗洞正中），一株高、一株矮
    for (px, tall) in ((-w * 0.5 + 0.45, tree), (w * 0.5 - 0.45, False)):
        py = yw1 + 0.46
        if tall:
            th = 2.30 + rng.uniform(0.0, 0.35)
            gb.cyl(0.065, th * 0.70, (px, py, th * 0.35), seg=6, mat="M_Bark")
            gb.sphere(th * 0.20, (px, py, th * 0.84), seg=7, rings=4,
                      mat="M_LeafDeep", scale=(1.0, 1.0, 0.95))
            gb.sphere(th * 0.14, (px + 0.17, py - 0.09, th * 0.99), seg=7,
                      rings=4, mat="M_LeafDeep", scale=(1.0, 1.0, 0.90))
        else:
            gb.cyl(0.045, 0.62, (px, py, 0.31), seg=6, mat="M_Bark")
            gb.sphere(0.30, (px, py, 1.22), seg=7, rings=4,
                      mat="M_LeafDeep", scale=(1.0, 1.0, 1.25))
    gb.sphere(0.24, (gw0 - 0.46, yw1 + 0.52, 0.98), seg=6, rings=3,
              mat="M_LeafBox", scale=(1.0, 1.0, 1.10))


# ================================================================ 三个户型
def _v0(gb, w, d, h, body, g0, g1, b1, u1, rng):
    """A · 石灰石 + 二层退台：二层只盖左侧 62%，右侧落成屋顶平台。"""
    x0, x1, y0, y1 = body
    bw = x1 - x0
    STONE, STONE2 = "M_LimeStone", "M_LimeStoneWarm"
    ux1 = x0 + bw * 0.62
    uy0 = y0 + 0.20                                  # 临街退 0.20
    ub = (x0, ux1, uy0, y1)

    # ---- 一层
    door = (x0 + bw * 0.5 - 0.55, x0 + bw * 0.5 + 0.55)
    fx = _side_wins(x0, door[0], 1, 2.45, edge=0.42) +         _side_wins(door[1], x1, 1, 2.45, edge=0.42)
    opf = [(a, b, 0.85, 2.56) for (a, b) in fx] + [(door[0], door[1], g0, 2.28)]
    bxs = _spread(x0 + 1.0, x1 - 1.0, 2, 1.60, edge=0.55, gap=1.6)
    opb = [(a, b, 0.95, 2.40) for (a, b) in bxs]
    op_l = [(y0 + 1.70, y0 + 3.30, 1.00, 2.45)]
    op_r = [(y0 + 2.10, y0 + 3.60, 0.95, 2.45)]
    _shell(gb, body, g0, g1, STONE, opf, opb, op_l, op_r)
    _bx(gb, x0 - 0.06, x1 + 0.06, y0 - 0.06, y1 + 0.06, 0.0, g0, "M_Concrete")
    _band(gb, body, g1, b1, STONE2)
    door_x = (door[0] + door[1]) * 0.5

    # ---- 一层玻璃
    for (a, b) in fx:
        _win(gb, "F", body, a, b, 0.85, 2.56, cols=2, sill=STONE)
    for (a, b) in bxs:
        _win(gb, "B", body, a, b, 0.95, 2.40, cols=1)
    _win(gb, "L", body, y0 + 1.70, y0 + 3.30, 1.00, 2.45, cols=1)
    _win(gb, "R", body, y0 + 2.10, y0 + 3.60, 0.95, 2.45, cols=1)
    _entry(gb, door[0], door[1], y0, g0, 2.28, canopy=True)
    _face_lines(gb, "F", body, x0 + 0.18, x1 - 0.18, 0.30, g1 - 0.06,
                nz=2, nx=5, mat="M_GraniteEdge", ops=opf)

    # ---- 二层（退 0.20，只盖左侧）
    uw = ux1 - x0
    ufx = _spread(x0, ux1, 2, min(2.0, uw * 0.30), edge=0.70, gap=0.60)
    ubx = _spread(x0 + 0.7, ux1 - 0.7, 1, 1.50, edge=0.4, gap=1.0)
    op_uf = [(a, b, b1 + 0.82, u1 - 0.52) for (a, b) in ufx]
    op_ub = [(a, b, b1 + 0.95, u1 - 0.52) for (a, b) in ubx]
    op_ur = [(uy0 + 1.30, uy0 + 3.40, b1 + 0.04, b1 + 2.16)]   # 上平台推拉门
    _shell(gb, ub, b1, u1, STONE2, op_uf, op_ub, (), op_ur)
    for (a, b) in ufx:
        _win(gb, "F", ub, a, b, b1 + 0.82, u1 - 0.52, cols=2, sill=STONE)
    for (a, b) in ubx:
        _win(gb, "B", ub, a, b, b1 + 0.95, u1 - 0.52, cols=1)
    _win(gb, "R", ub, uy0 + 1.30, uy0 + 3.40, b1 + 0.04, b1 + 2.16, cols=2)
    _roof_flat(gb, ub, u1, h, STONE)
    _roof_bits(gb, ub, u1 + 0.17)

    # ---- 屋顶平台（二层右侧那块）
    tx0, ty0 = ux1, y0
    _bx(gb, tx0 - 0.02, x1 + 0.02, ty0 - 0.02, y1 + 0.02, b1, b1 + 0.05, _ROOF)
    for (a0, a1, c0, c1) in ((tx0, x1, ty0, ty0 + 0.16),
                             (x1 - 0.16, x1, ty0 + 0.16, y1),
                             (tx0, tx0 + 0.16, ty0 + 0.16, y1)):
        _bx(gb, a0, a1, c0, c1, b1, b1 + 0.38, STONE)
        _bx(gb, a0 - 0.03, a1 + 0.03, c0 - 0.03, c1 + 0.03,
            b1 + 0.38, b1 + 0.44, _BAND)
    gb.sphere(0.40, (x1 - 0.75, y0 + 1.05, b1 + 0.40), seg=7, rings=4,
              mat="M_LeafBox", scale=(1.0, 1.0, 0.75))
    _bx(gb, x1 - 1.15, x1 - 0.35, y0 + 0.65, y0 + 1.45, b1 + 0.05, b1 + 0.50,
        "M_ConcretePot")

    # ---- 落水管
    for xx in (x0 + 0.10, x1 - 0.10):
        _bx(gb, xx - 0.045, xx + 0.045, y0 - 0.055, y0 - 0.005,
            g0, g1 - 0.05, _TRIM)
    return door_x


def _v1(gb, w, d, h, body, g0, g1, b1, u1, rng):
    """B · 柚木格栅 + 悬挑二层：二层临街挑出 0.22，阳台挂在挑檐下。"""
    x0, x1, y0, y1 = body
    bw = x1 - x0
    STONE, TEAK = "M_LimeStoneWarm", "M_SlatTeak"
    ub = (x0, x1, y0 - 0.22, y1 - 0.22)              # 前挑 0.22 / 后收 0.22

    # ---- 一层
    cx = x0 + bw * 0.50
    door = (cx - 0.52, cx + 0.52)
    fx = _side_wins(x0, door[0], 1, 2.45, edge=0.45) +         _side_wins(door[1], x1, 1, 2.45, edge=0.45)
    opf = [(a, b, 0.85, 2.54) for (a, b) in fx] + [(door[0], door[1], g0, 2.26)]
    bxs = _spread(x0 + 1.1, x1 - 1.1, 2, 1.45, edge=0.6, gap=1.4)
    opb = [(a, b, 0.98, 2.38) for (a, b) in bxs]
    op_l = [(y0 + 1.90, y0 + 3.10, 1.02, 2.42)]
    _shell(gb, body, g0, g1, STONE, opf, opb, op_l, ())
    _bx(gb, x0 - 0.06, x1 + 0.06, y0 - 0.06, y1 + 0.06, 0.0, g0, "M_Concrete")
    _band(gb, body, g1, b1, STONE)
    door_x = (door[0] + door[1]) * 0.5
    for (a, b) in fx:
        _win(gb, "F", body, a, b, 0.85, 2.54, cols=2, sill=STONE)
    for (a, b) in bxs:
        _win(gb, "B", body, a, b, 0.98, 2.38, cols=1)
    _win(gb, "L", body, y0 + 1.90, y0 + 3.10, 1.02, 2.42, cols=1)
    _entry(gb, door[0], door[1], y0, g0, 2.26, canopy=False)
    # 入口旁的柚木格栅屏风（从挑檐下往外 0.35）
    sp1 = door[0] - 0.16
    sp0 = max([b for (a, b) in fx if b < sp1] + [sp1 - 1.30]) + 0.14
    if sp1 - sp0 > 0.60:
        _slats(gb, "X", sp0, sp1, y0 - 0.26, y0 - 0.19, g0, g1 - 0.10,
               w=0.07, gap=0.055, mat=TEAK)
        _bx(gb, sp0 - 0.05, sp1 + 0.05, y0 - 0.30, y0 - 0.15, 0.0, 0.12, _BAND)
        _bx(gb, sp0 - 0.05, sp1 + 0.05, y0 - 0.30, y0 - 0.15,
            g1 - 0.10, g1 - 0.02, _BAND)
    # 一层悬挑体下方的斜撑（结构可信）
    for xx in (x0 + 0.35, x1 - 0.35):
        _bx(gb, xx - 0.05, xx + 0.05, y0 - 0.34, y0 - 0.02, g1 - 0.55, g1, _TRIM)

    # ---- 二层（前挑 0.22）
    bal_x0 = x0 + 0.95
    bal_x1 = bal_x0 + min(2.9, bw * 0.32)
    ufx = _spread(bal_x1 + 0.55, x1 - 0.75, 1, 1.75, edge=0.25, gap=0.5)
    ufx2 = _spread(x0 + 0.70, bal_x0 - 0.60, 1, 1.35, edge=0.15, gap=0.5)
    op_uf = ([(a, b, b1 + 0.10, b1 + 2.18) for (a, b) in
              [(bal_x0, bal_x1)] + ufx + ufx2])
    op_ub = [(a, b, b1 + 0.95, u1 - 0.55)
             for (a, b) in _spread(x0 + 0.9, x1 - 0.9, 1, 2.0, edge=0.5, gap=1.0)]
    op_ul = [(y0 + 1.60, y0 + 3.05, b1 + 0.95, u1 - 0.55)]
    _shell(gb, ub, b1, u1, STONE, op_uf, op_ub, op_ul, ())
    _face_lines(gb, "F", body, x0 + 0.18, x1 - 0.18, 0.30, g1 - 0.06,
                nz=2, nx=5, mat="M_PaveGrey", ops=opf)
    # 挑出体的底面（挑檐下表面）
    _bx(gb, x0, x1, y0 - 0.24, y0 + 0.02, b1 - 0.06, b1 + 0.02, _BAND)
    _bx(gb, x0 + 0.20, x1 - 0.20, y0 - 0.22, y0 - 0.02, b1 - 0.075,
        b1 - 0.055, "M_SlatTeakDark")
    # 阳台（挂在挑出体上）
    _win(gb, "F", ub, bal_x0, bal_x1, b1 + 0.10, b1 + 2.18, cols=2)
    for (a, b) in ufx + ufx2:
        _win(gb, "F", ub, a, b, b1 + 0.10, b1 + 2.18, cols=1, sill=STONE)
    for (a, b, c, d) in op_ub:
        _win(gb, "B", ub, a, b, c, d, cols=1)
    _win(gb, "L", ub, y0 + 1.60, y0 + 3.05, b1 + 0.95, u1 - 0.55, cols=1)
    _balcony(gb, bal_x0 - 0.30, bal_x1 + 0.30, ub[2], b1, depth=1.35)
    # 二层右侧的柚木格栅饰面
    _slats(gb, "X", bal_x1 + 0.60, x1 - 0.35, ub[2] - 0.10, ub[2] - 0.03,
           u1 - 1.55, u1 - 0.35, w=0.075, gap=0.055, mat=TEAK)
    _roof_flat(gb, ub, u1, h, STONE)
    _roof_bits(gb, ub, u1 + 0.17)
    # 后侧露出的平屋面
    _bx(gb, x0, x1, y1 - 0.28, y1 + 0.02, b1, b1 + 0.06, _ROOF)
    for xx in (x0 + 0.10, x1 - 0.10):
        _bx(gb, xx - 0.045, xx + 0.045, y0 - 0.06, y0 - 0.01,
            g0, g1 - 0.05, _TRIM)
    return door_x


def _v2(gb, w, d, h, body, g0, g1, b1, u1, rng):
    """C · 白灰泥 + 黑钢 + 单坡屋面：二层临街退 0.22，深色单坡顶压出侧向轮廓。"""
    x0, x1, y0, y1 = body
    bw = x1 - x0
    PLAS = "M_PlasterWhite"
    ub = (x0, x1, y0 + 0.22, y1)                     # 临街退 0.22
    rise = 0.70
    ux0, ux1, uy0, uy1 = ub
    sl = rise / max(0.8, uy1 - uy0)
    zt = h - rise - 0.15                             # 墙顶 = 檐口最低处下方
    zback = h - OV * sl                              # 后檐口出挑端正好压到 h

    # ---- 一层（白灰泥 + 0.26 黑钢基座带）
    door = (x0 + bw * 0.32 - 0.55, x0 + bw * 0.32 + 0.55)
    fx = _side_wins(x0, door[0], 1, 2.30, edge=0.40) +         _side_wins(door[1], x1, 1, 2.45, edge=0.45)
    opf = [(a, b, 0.85, 2.52) for (a, b) in fx] + [(door[0], door[1], g0, 2.26)]
    bxs = _spread(x0 + 1.1, x1 - 1.1, 2, 1.40, edge=0.6, gap=1.5)
    opb = [(a, b, 0.98, 2.38) for (a, b) in bxs]
    op_r = [(y0 + 1.85, y0 + 3.25, 0.95, 2.42)]
    _shell(gb, body, g0, g1, PLAS, opf, opb, (), op_r)
    _bx(gb, x0 - 0.07, x1 + 0.07, y0 - 0.07, y1 + 0.07, 0.0, g0, "M_Concrete")
    _bx(gb, x0 - 0.055, x1 + 0.055, y0 - 0.055, y1 + 0.055,
        g0 - 0.01, g0 + 0.26, _TRIM)
    _band(gb, body, g1, b1, PLAS)
    door_x = (door[0] + door[1]) * 0.5
    for (a, b) in fx:
        _win(gb, "F", body, a, b, 0.85, 2.52, cols=2, glass="M_GlassGreen",
             sill="M_Concrete")
    for (a, b) in bxs:
        _win(gb, "B", body, a, b, 0.98, 2.38, cols=1)
    _win(gb, "R", body, y0 + 1.85, y0 + 3.25, 0.95, 2.42, cols=1,
         sill="M_Concrete")
    _entry(gb, door[0], door[1], y0, g0, 2.26, canopy=True)

    # ---- 二层（退 0.22，墙顶压到坡顶低边）
    dhead = min(b1 + 2.18, zt - 0.32)
    bal_x1 = x1 - 0.85
    bal_x0 = bal_x1 - min(3.0, bw * 0.34)
    ufx = _spread(x0 + 0.75, bal_x0 - 0.50, 1, 1.55, edge=0.15, gap=0.5)
    op_uf = [(bal_x0, bal_x1, b1 + 0.10, dhead)] +             [(a, b, b1 + 0.10, dhead) for (a, b) in ufx]
    uh0, uh1 = b1 + 0.95, zt - 0.55
    op_ub = [(a, b, uh0, uh1)
             for (a, b) in _spread(x0 + 0.9, x1 - 0.9, 1, 2.0, edge=0.5, gap=1.0)]
    op_ul = [(y0 + 1.55, y0 + 3.00, uh0, uh1)]
    _shell(gb, ub, b1, zt, PLAS, op_uf, op_ub, op_ul, ())
    _win(gb, "F", ub, bal_x0, bal_x1, b1 + 0.10, dhead, cols=2,
         glass="M_GlassGreen")
    for (a, b) in ufx:
        _win(gb, "F", ub, a, b, b1 + 0.10, dhead, cols=1, sill="M_Concrete")
    for (a, b, c, d) in op_ub:
        _win(gb, "B", ub, a, b, c, d, cols=1)
    _win(gb, "L", ub, y0 + 1.55, y0 + 3.00, uh0, uh1, cols=1)
    _balcony(gb, bal_x0 - 0.28, bal_x1 + 0.28, uy0, b1, depth=1.35)
    # 一层立面的黑钢竖fin（白灰泥上唯一的竖向节奏）
    for xx in (x0 + 0.30, x1 - 0.44):
        _bx(gb, xx - 0.045, xx + 0.045, y0 - 0.10, y0 + 0.02, g0 + 0.26,
            g1 - 0.12, _TRIM)
    # 二层前脸的黑钢竖带（把白盒子切成两段）
    _bx(gb, bal_x0 - 0.42, bal_x0 - 0.20, uy0 - 0.06, uy0 + 0.02,
        b1, zt, _TRIM)
    # 坡顶楔块（墙顶到屋面底）—— 从侧面看就是单坡的三角头
    _prism_x(gb, ux0, ux1, [(uy0, zt), (uy1, zback - 0.15), (uy1, zt)], PLAS)
    # 屋面板（同坡，前后各出挑 0.30，深色卷材）
    _prism_x(gb, ux0 - OV, ux1 + OV,
             [(uy0 - OV, zt - OV * sl), (uy1 + OV, zback),
              (uy1 + OV, zback - 0.15), (uy0 - OV, zt - 0.15 - OV * sl)],
             _ROOF)
    # 低边滴水线
    _bx(gb, ux0 - OV - 0.02, ux1 + OV + 0.02, uy0 - OV - 0.03, uy0 - OV + 0.07,
        zt - 0.10, zt + 0.02, _BAND)
    # 一层前沿露出的平屋面
    _bx(gb, x0, x1, y0 - 0.02, uy0 + 0.02, b1, b1 + 0.10, _ROOF)
    _bx(gb, x0 - 0.05, x1 + 0.05, y0 - 0.07, y0 + 0.02, b1 - 0.10, b1 + 0.10,
        _BAND)
    # 屋面设备（贴着坡面坐，不许顶破 h）
    ym = uy1 - 1.15
    zs = zt + (ym - uy0) * sl
    _bx(gb, x1 - 1.55, x1 - 0.95, ym - 0.35, ym + 0.35, zs - 0.06,
        min(zs + 0.50, h - 0.06), _TRIM)
    for xx in (x0 + 0.10, x1 - 0.10):
        _bx(gb, xx - 0.045, xx + 0.045, y0 - 0.06, y0 - 0.01,
            g0, g1 - 0.05, _TRIM)
    return door_x


_VARIANTS = (_v0, _v1, _v2)


def _house(gb, w, d, h, variant):
    rng = random.Random(20260101 + 7919 * variant)
    x0, x1 = -w / 2 + SIDE_IN, w / 2 - SIDE_IN
    y0, y1 = -d / 2 + SETBACK, d / 2 - BACK_IN
    body = (x0, x1, y0, y1)
    if (x1 - x0) < 4.0 or (y1 - y0) < 4.0 or h < 4.6:
        return
    g0, g1, b1, u1 = _levels(h)
    if u1 > h - 0.24:
        return
    dx = _VARIANTS[variant % 3](gb, w, d, h, body, g0, g1, b1, u1, rng)
    _garden(gb, w, d, rng, tree=(variant % 3 != 1),
            door_x=0.0 if dx is None else dx)


# ================================================================ 唯一入口
def neighbour(gb, x, y, w, d, h, variant, rot=0.0):
    """在 (x, y) 放一栋两层住宅：占位 w×d、总高 ≤ h、朝街面为 −Y。

    variant: 0 石灰石退台 / 1 柚木悬挑 / 2 白灰泥单坡。
    几何全部写进传入的 gb，局部坐标以户型中心为原点，底面 z = 0。
    """
    M = Matrix.Translation((float(x), float(y), 0.0)) @ \
        Matrix.Rotation(float(rot), 4, "Z")
    with gb.frame(M):
        _house(gb, float(w), float(d), float(h), int(variant))
