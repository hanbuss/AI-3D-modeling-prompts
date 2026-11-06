# -*- coding: utf-8 -*-
"""现代简约别墅 · 建筑外壳。

语言（取自参考图）：浅色石材大板 + 暖柚木竖格栅 + 近黑金属收边 + 通高玻璃，
平屋面 + 薄挑檐，三层只在西侧收，东侧退成露台。

坐标与层高严格遵守 LAYOUT.md §2/§3/§4。
"""
import math
import random
from mathutils import Vector, Matrix
from .kit import GB, D, TAU, lerp

# ---------------------------------------------------------------- 竖向
F0 = 0.00       # 场地
F1 = 0.15       # 1F 完成面
F1T = 3.30      # 1F 顶板下
F2 = 3.60       # 2F 完成面
F2T = 6.60
F3 = 6.90
F3T = 9.90
PARAPET = 10.45
SLAB = 0.30

# ---------------------------------------------------------------- 平面
PX0, PX1 = -7.20, 7.20      # 外墙外皮
PY0, PY1 = -1.50, 9.00
TE = 0.30                   # 外墙厚
X0, X1 = PX0 + TE, PX1 - TE  # 内皮 -6.90 / 6.90
Y0, Y1 = PY0 + TE, PY1 - TE  # 内皮 -1.20 / 8.70
TI = 0.20                   # 内墙厚

# 3F 只占西侧
P3X1 = 3.60
X3_1 = P3X1 - TE             # 3.30

# 门厅
FOY_X0, FOY_X1 = -1.60, 1.60
STAIR_Y0, STAIR_Y1 = 4.20, 9.00

SEED = random.Random(20261106)


# ================================================================ 基础
def _box(gb, x0, x1, y0, y1, z0, z1, mat):
    if x1 - x0 <= 1e-5 or y1 - y0 <= 1e-5 or z1 - z0 <= 1e-5:
        return
    gb.box((x1 - x0, y1 - y0, z1 - z0),
           ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), mat=mat)


def _ab(gb, axis, a0, a1, t0, t1, z0, z1, mat):
    """axis="X" 时 a 走 X、t 走 Y；"Y" 时 a 走 Y、t 走 X。"""
    if axis == "X":
        _box(gb, a0, a1, t0, t1, z0, z1, mat)
    else:
        _box(gb, t0, t1, a0, a1, z0, z1, mat)


def _wall(gb, axis, a0, a1, t0, t1, z0, z1, mat, openings=()):
    """带洞口的墙。openings=[(a0,a1,z0,z1)]，洞口处不生成墙体（框由 _glaze 补）。"""
    pieces = [(a0, a1, z0, z1)]
    for (oa0, oa1, oz0, oz1) in openings:
        oa0, oa1 = max(a0, oa0), min(a1, oa1)
        oz0, oz1 = max(z0, oz0), min(z1, oz1)
        if oa1 <= oa0 + 1e-5 or oz1 <= oz0 + 1e-5:
            continue
        newp = []
        for (pu0, pu1, pz0, pz1) in pieces:
            if oa1 <= pu0 + 1e-5 or oa0 >= pu1 - 1e-5 or \
               oz1 <= pz0 + 1e-5 or oz0 >= pz1 - 1e-5:
                newp.append((pu0, pu1, pz0, pz1))
                continue
            if oa0 > pu0 + 1e-5:
                newp.append((pu0, oa0, pz0, pz1))
            if oa1 < pu1 - 1e-5:
                newp.append((oa1, pu1, pz0, pz1))
            ix0, ix1 = max(pu0, oa0), min(pu1, oa1)
            if oz0 > pz0 + 1e-5:
                newp.append((ix0, ix1, pz0, oz0))
            if oz1 < pz1 - 1e-5:
                newp.append((ix0, ix1, oz1, pz1))
        pieces = newp
    for (pu0, pu1, pz0, pz1) in pieces:
        _ab(gb, axis, pu0, pu1, t0, t1, pz0, pz1, mat)


# ================================================================ 玻璃
def _glaze(gb, axis, a0, a1, t0, t1, z0, z1, cols=3, rows=1,
           glass="M_GlassClear", frame="M_SteelDark", fw=0.05,
           lit=()):
    """框 + 竖挺 + 玻璃。lit=[(i,j)] 指定用 M_WinGlow 的格。"""
    tm = (t0 + t1) / 2
    gt0, gt1 = tm - 0.012, tm + 0.012
    e = 0.008                      # 框料端头互相压进的量（不共面）
    gi = 0.002                     # 玻璃四边内让量（不贴框料外皮）
    ga0, ga1 = a0 + gi, a1 - gi
    gz0, gz1 = z0 + gi, z1 - gi
    # 玻璃分格
    for i in range(cols):
        ua = lerp(ga0, ga1, i / cols)
        ub = lerp(ga0, ga1, (i + 1) / cols)
        for j in range(rows):
            va = lerp(gz0, gz1, j / rows)
            vb = lerp(gz0, gz1, (j + 1) / rows)
            g = "M_WinGlow" if (i, j) in lit else glass
            _ab(gb, axis, ua, ub, gt0, gt1, va, vb, g)
    # 外框：竖梃通高，横档两端压进竖梃
    _ab(gb, axis, a0, a0 + fw, t0, t1, z0, z1, frame)
    _ab(gb, axis, a1 - fw, a1, t0, t1, z0, z1, frame)
    _ab(gb, axis, a0 + fw - e, a1 - fw + e, t0, t1, z0, z0 + fw, frame)
    _ab(gb, axis, a0 + fw - e, a1 - fw + e, t0, t1, z1 - fw, z1, frame)
    # 竖挺上下压进横档 / 横挺左右压进竖梃
    for i in range(1, cols):
        u = lerp(a0, a1, i / cols)
        _ab(gb, axis, u - 0.016, u + 0.016, t0, t1, z0 + fw - e, z1 - fw + e, frame)
    for j in range(1, rows):
        v = lerp(z0, z1, j / rows)
        _ab(gb, axis, a0 + fw - e, a1 - fw + e, t0, t1, v - 0.016, v + 0.016, frame)


def _reveal(gb, axis, a0, a1, t0, t1, z0, z1, mat="M_SteelDark", w=0.04,
            out=0.003):
    """洞口四周 0.04 金属压条。

    out：压条外表面再往外让出的量（默认 3 mm）。压条内表面本来就埋进墙体，
    外表面再多让 3 mm，保证与墙面/石材板不在同一平面（否则 GLB 深度精度下闪烁）。
    """
    ta, tb = (t0 - out, t1) if t0 <= t1 else (t0, t1 + out)
    n = 0.004                      # 向洞口内压进 4 mm，避免与洞口侧壁共面
    _ab(gb, axis, a0 - w, a1 + w, ta, tb, z1 - n, z1 + w, mat)
    _ab(gb, axis, a0 - w, a1 + w, ta, tb, z0 - w, z0 + n, mat)
    _ab(gb, axis, a0 - w, a0 + n, ta, tb, z0, z1, mat)
    _ab(gb, axis, a1 - n, a1 + w, ta, tb, z0, z1, mat)


# ================================================================ 石材大板
def _panels(gb, axis, a0, a1, t0, t1, z0, z1, mat="M_LimeStone",
            pw=1.20, ph=0.60, gap=0.006):
    """错缝石材大板：真实板缝（不靠贴图）。"""
    if a1 - a0 <= 0.02 or z1 - z0 <= 0.02:
        return
    rows = max(1, int(round((z1 - z0 + gap) / (ph + gap))))
    hh = (z1 - z0 - gap * (rows - 1)) / rows
    for j in range(rows):
        pz0 = z0 + j * (hh + gap)
        pz1 = pz0 + hh
        off = (pw * 0.5) if (j % 2) else 0.0
        x = a0 - off
        while x < a1 - 0.02:
            px0, px1 = max(x, a0), min(x + pw, a1)
            if px1 - px0 > 0.03:
                _ab(gb, axis, px0, px1, t0, t1, pz0, pz1, mat)
            x += pw + gap


# ================================================================ 木格栅
def _slats(gb, axis, a0, a1, t0, t1, z0, z1, w=0.045, gap=0.035,
           mat="M_SlatTeak"):
    """竖向柚木格栅：条宽 w、间隙 gap，贴在 t0..t1 这条带里。"""
    span = a1 - a0
    n = max(1, int((span + gap) / (w + gap)))
    total = n * w + (n - 1) * gap
    s = a0 + (span - total) / 2
    for i in range(n):
        x0 = s + i * (w + gap)
        _ab(gb, axis, x0, x0 + w, t0, t1, z0, z1, mat)


# ================================================================ 楼板
def _slab(gb, x0, x1, y0, y1, z0, z1, mat="M_Concrete", top=None):
    _box(gb, x0, x1, y0, y1, z0, z1, mat)
    if top:
        _box(gb, x0, x1, y0, y1, z1, z1 + 0.02, top)


# ================================================================ 内墙
def _part(gb, x0, x1, y0, y1, z0, z1, doors=(), mat="M_PlasterWhite"):
    """内隔墙：doors=[(x0,x1) 或 (y0,y1) 沿长边的洞口]，这里用 axis 自动判。"""
    if (x1 - x0) >= (y1 - y0):
        ops = [(d[0], d[1], z0, z0 + 2.10) for d in doors]
        _wall(gb, "X", x0, x1, y0, y1, z0, z1, mat, ops)
    else:
        ops = [(d[0], d[1], z0, z0 + 2.10) for d in doors]
        _wall(gb, "Y", y0, y1, x0, x1, z0, z1, mat, ops)


# ================================================================ 1F
def _emit(ctx, tag, gb_w, gb_g):
    if gb_w.verts:
        ctx.mesh(gb_w, tag + "_Solid", uv_scale=2.0)
    if gb_g.verts:
        ctx.mesh(gb_g, tag + "_Glass", uv_scale=2.0)


def build_1f(ctx):
    ctx.use("ARCH_1F")
    gb_w, gb_g = GB("a1w"), GB("a1g")
    # 底板 + 室内地面
    _slab(gb_w, PX0, PX1, PY0, PY1, F0 - 0.10, F1, "M_Concrete")
    _box(gb_w, X0, X1, Y0, Y1, F1 - 0.02, F1 + 0.005, "M_TileFloorGrey")

    # ---- 南立面（Y=-1.50 外皮，-1.20 内皮）通高玻璃
    so = [(-6.90, -1.95, F1, 3.15),      # 客厅
          (-1.80, -0.92, F1, 2.75),      # 门厅侧窗
          (0.92, 1.80, F1, 2.75),
          (-0.90, 0.90, F1, 2.60),       # 门洞
          (1.95, 6.90, F1, 3.15)]        # 餐厅
    _wall(gb_w, "X", PX0, PX1, PY0, PY0 + TE, F1, F1T, "M_LimeStone", so)
    _glaze(gb_g, "X", -6.90, -1.95, PY0 + 0.10, PY0 + 0.20, F1, 3.15, cols=4,
           lit=((1, 0), (2, 0)))
    _glaze(gb_g, "X", 1.95, 6.90, PY0 + 0.10, PY0 + 0.20, F1, 3.15, cols=4,
           lit=((0, 0), (3, 0)))
    _glaze(gb_g, "X", -1.80, -0.92, PY0 + 0.10, PY0 + 0.20, F1, 2.75, cols=1)
    _glaze(gb_g, "X", 0.92, 1.80, PY0 + 0.10, PY0 + 0.20, F1, 2.75, cols=1)
    for (a, b, c, d) in so:
        _reveal(gb_w, "X", a, b, PY0 - 0.01, PY0 + 0.045, c, d)

    # ---- 北立面（Y=9.00）
    no = [(-6.60, -4.60, 1.35, 2.55), (2.00, 3.60, 1.35, 2.55),
          (5.10, 6.40, 1.35, 2.55)]
    _wall(gb_w, "X", PX0, PX1, PY1 - TE, PY1, F1, F1T, "M_LimeStone", no)
    for (a, b, c, d) in no:
        _glaze(gb_g, "X", a, b, PY1 - 0.20, PY1 - 0.10, c, d, cols=2)
        _reveal(gb_w, "X", a, b, PY1 - 0.045, PY1 + 0.01, c, d)

    # ---- 东立面（X=7.20）
    eo = [(3.00, 4.80, 1.25, 2.65)]
    _wall(gb_w, "Y", Y0, Y1, PX1 - TE, PX1, F1, F1T, "M_LimeStone", eo)
    for (a, b, c, d) in eo:
        _glaze(gb_g, "Y", a, b, PX1 - 0.20, PX1 - 0.10, c, d, cols=2)
        _reveal(gb_w, "Y", a, b, PX1 - 0.045, PX1 + 0.01, c, d)

    # ---- 西立面（X=-7.20）：一条竖缝窗 + 石材
    wo = [(2.00, 3.40, 1.10, 2.70)]
    _wall(gb_w, "Y", Y0, Y1, PX0, PX0 + TE, F1, F1T, "M_LimeStone", wo)
    for (a, b, c, d) in wo:
        _glaze(gb_g, "Y", a, b, PX0 + 0.10, PX0 + 0.20, c, d, cols=1, lit=((0, 0),))
        _reveal(gb_w, "Y", a, b, PX0 - 0.01, PX0 + 0.045, c, d)

    # ---- 1F 内墙（按 LAYOUT §3）
    P = "M_PlasterWhite"
    # 门厅两侧（X=±1.60），留 0.90 门洞到客厅/餐厅
    _part(gb_w, FOY_X0 - TI, FOY_X0, Y0, 4.20, F1, F1T, [(-0.30, 0.60)])
    _part(gb_w, FOY_X1, FOY_X1 + TI, Y0, 4.20, F1, F1T, [(-0.30, 0.60)])
    # 客厅北墙 Y=6.40
    _part(gb_w, X0, FOY_X0, 6.40 - TI, 6.40, F1, F1T)
    # 餐厅/厨房 Y=4.00
    _part(gb_w, FOY_X1, X1, 4.00 - TI, 4.00, F1, F1T, [(2.20, 3.40)])
    # 厨房/储藏 WC Y=7.60
    _part(gb_w, FOY_X1, X1, 7.60 - TI, 7.60, F1, F1T, [(2.40, 3.30)])
    # 储藏/WC 之间 X=4.40
    _part(gb_w, 4.40 - TI / 2, 4.40 + TI / 2, 7.60, Y1, F1, F1T)
    # 楼梯间两侧 X=±1.60（4.20..9.00）
    _part(gb_w, FOY_X0 - TI, FOY_X0, 4.20, Y1, F1, F1T)
    _part(gb_w, FOY_X1, FOY_X1 + TI, 4.20, Y1, F1, F1T)
    # 注：X0…FOY_X0 的 Y=6.40 隔墙已在上面建过，此处原本重复建了一遍
    # （X0…-1.80 段两层完全重合 → 共面闪烁），已删除重复段。

    # 1F 内的楼梯 1F→2F、入户门、雨棚
    _stair(gb_w, gb_g, F1, F2, 17, 8.60, -1, xo=0.0)
    _entry(gb_w)
    _emit(ctx, "ARCH_1F", gb_w, gb_g)


def build_2f(ctx):
    ctx.use("ARCH_2F")
    gb_w, gb_g = GB("a2w"), GB("a2g")
    _slab(gb_w, PX0, PX1, PY0, PY1, F1T, F2, "M_Concrete")
    _box(gb_w, X0, X1, Y0, Y1, F2 - 0.02, F2 + 0.005, "M_OakFloor")

    # 南立面：主卧 + 次卧落地窗
    so = [(-6.90, -1.95, F2 + 0.15, F2 + 2.55),
          (1.95, 6.90, F2 + 0.15, F2 + 2.55)]
    _wall(gb_w, "X", PX0, PX1, PY0, PY0 + TE, F2, F2T, "M_LimeStone", so)
    _glaze(gb_g, "X", -6.90, -1.95, PY0 + 0.10, PY0 + 0.20, F2 + 0.15, F2 + 2.55,
           cols=4, lit=((0, 0), (3, 0)))
    _glaze(gb_g, "X", 1.95, 6.90, PY0 + 0.10, PY0 + 0.20, F2 + 0.15, F2 + 2.55,
           cols=4, lit=((1, 0),))
    for (a, b, c, d) in so:
        _reveal(gb_w, "X", a, b, PY0 - 0.01, PY0 + 0.045, c, d)

    # 北 / 东 / 西
    no = [(-6.40, -4.60, F2 + 0.95, F2 + 2.35),
          (2.10, 3.40, F2 + 1.35, F2 + 2.35),
          (4.60, 6.40, F2 + 1.35, F2 + 2.35)]
    _wall(gb_w, "X", PX0, PX1, PY1 - TE, PY1, F2, F2T, "M_LimeStone", no)
    for (a, b, c, d) in no:
        _glaze(gb_g, "X", a, b, PY1 - 0.20, PY1 - 0.10, c, d, cols=2)
    eo = [(1.20, 2.80, F2 + 0.95, F2 + 2.35)]
    _wall(gb_w, "Y", Y0, Y1, PX1 - TE, PX1, F2, F2T, "M_LimeStone", eo)
    for (a, b, c, d) in eo:
        _glaze(gb_g, "Y", a, b, PX1 - 0.20, PX1 - 0.10, c, d, cols=2)
    # 西墙：主卧整片竖木格栅 + 一条窗缝
    wo = [(1.00, 2.60, F2 + 0.95, F2 + 2.35)]
    _wall(gb_w, "Y", Y0, Y1, PX0, PX0 + TE, F2, F2T, "M_LimeStone", wo)
    for (a, b, c, d) in wo:
        _glaze(gb_g, "Y", a, b, PX0 + 0.10, PX0 + 0.20, c, d, cols=1)
    # 格栅板（贴西墙外侧，留 40 mm 净空避免与墙面共面闪烁）
    _slats(gb_g, "Y", -1.20, 4.90, PX0 - 0.11, PX0 - 0.04, F2, F2 + 2.45)
    # 南向悬挑阳台（主卧）
    _box(gb_w, -7.20, -1.60, -2.40, PY0, F2 - 0.18, F2, "M_Concrete")
    _box(gb_w, -7.20, -1.60, -2.42, PY0 + 0.02, F2 - 0.20, F2 - 0.16,
         "M_Fascia")
    # 无框玻璃栏板 1.05
    for (x0, x1, y0, y1) in ((-7.20, -1.60, -2.44, -2.40),
                             (-7.24, -7.20, -2.40, PY0),
                             (-1.64, -1.60, -2.40, PY0)):
        _box(gb_g, x0, x1, y0, y1, F2 + 0.02, F2 + 1.05, "M_GlassRail")
        _box(gb_w, x0 - 0.015, x1 + 0.015, y0 - 0.015, y1 + 0.015, F2,
             F2 + 0.09, "M_SteelDark")

    # 2F 内墙
    P = "M_PlasterWhite"
    _part(gb_w, X0, FOY_X0 - TI, 5.60 - TI, 5.60, F2, F2T, [(-6.20, -5.20)])
    _part(gb_w, X0, -1.60, 5.60, Y1, F2, F2T)          # 北侧横墙
    _part(gb_w, -4.60 - TI / 2, -4.60 + TI / 2, 5.60, Y1, F2, F2T,
          [(-4.60, -4.60)])                              # 主卫/衣帽间
    _part(gb_w, FOY_X0 - TI, FOY_X0, Y0, 4.20, F2, F2T)  # 楼梯厅西
    _part(gb_w, FOY_X1, FOY_X1 + TI, Y0, 4.20, F2, F2T)  # 楼梯厅东
    _part(gb_w, FOY_X1, X1, 4.00 - TI, 4.00, F2, F2T, [(2.40, 3.30)])
    _part(gb_w, FOY_X1, X1, 6.80 - TI, 6.80, F2, F2T, [(4.60, 5.50)])
    _part(gb_w, 4.40 - TI / 2, 4.40 + TI / 2, 4.00, 6.80, F2, F2T)
    _part(gb_w, FOY_X0, FOY_X1, 4.20 - TI, 4.20, F2, F2T)

    _stair(gb_w, gb_g, F2, F3, 17, 8.60, -1, xo=0.035)
    _emit(ctx, "ARCH_2F", gb_w, gb_g)


def build_3f(ctx):
    ctx.use("ARCH_3F")
    gb_w, gb_g = GB("a3w"), GB("a3g")
    # 3F 楼板只铺到 P3X1；东侧是露台（屋面在 6.60）
    _slab(gb_w, PX0, P3X1, PY0, PY1, F2T, F3, "M_Concrete")
    _box(gb_w, X0, X3_1, Y0, Y1, F3 - 0.02, F3 + 0.005, "M_OakFloor")
    # 露台面层（2F 屋面顶）
    _box(gb_w, P3X1, PX1, PY0, PY1, F2T, F3 - 0.02, "M_TeakFurn")
    for i in range(20):
        yy = lerp(PY0 + 0.2, PY1 - 0.2, i / 19)
        _box(gb_w, P3X1 + 0.1, PX1 - 0.1, yy - 0.004, yy + 0.004,
             F3 - 0.024, F3 - 0.016, "M_DeckTeakGap")

    # 南立面（书房横窗）
    so = [(-6.60, -1.95, F3 + 0.90, F3 + 2.50)]
    _wall(gb_w, "X", PX0, P3X1, PY0, PY0 + TE, F3, F3T, "M_SlatTeakDark", so)
    _glaze(gb_g, "X", -6.60, -1.95, PY0 + 0.10, PY0 + 0.20, F3 + 0.90, F3 + 2.50,
           cols=4, lit=((2, 0),))
    for (a, b, c, d) in so:
        _reveal(gb_w, "X", a, b, PY0 - 0.01, PY0 + 0.045, c, d)
    # 3F 南立面东段整片竖木格栅（设计签名：木体量要看得见"条"）
    _slats(gb_g, "X", -1.90, 3.26, PY0 - 0.11, PY0 - 0.04, F3, F3T - 0.05,
           mat="M_SlatTeak")
    # 窗上下也压一条横向木封边
    _box(gb_w, -6.64, -1.91, PY0 - 0.05, PY0 + 0.02, F3, F3 + 0.86, "M_SlatTeakDark")
    _box(gb_w, -6.64, -1.91, PY0 - 0.05, PY0 + 0.02, F3 + 2.54, F3T - 0.05,
         "M_SlatTeakDark")
    # 东立面（X=3.60，面向露台）：大面积玻璃
    eo = [(-0.90, 2.40, F3 + 0.15, F3 + 2.55)]
    _wall(gb_w, "Y", Y0, Y1, P3X1 - TE, P3X1, F3, F3T, "M_LimeStone", eo)
    _glaze(gb_g, "Y", -0.90, 2.40, P3X1 - 0.20, P3X1 - 0.10, F3 + 0.15, F3 + 2.55,
           cols=3, lit=((0, 0), (2, 0)))
    for (a, b, c, d) in eo:
        _reveal(gb_w, "Y", a, b, P3X1 - 0.045, P3X1 + 0.01, c, d)
    # 北 / 西
    no = [(-6.40, -4.40, F3 + 0.95, F3 + 2.35)]
    _wall(gb_w, "X", PX0, P3X1, PY1 - TE, PY1, F3, F3T, "M_LimeStone", no)
    for (a, b, c, d) in no:
        _glaze(gb_g, "X", a, b, PY1 - 0.20, PY1 - 0.10, c, d, cols=2)
    _wall(gb_w, "Y", Y0, Y1, PX0, PX0 + TE, F3, F3T, "M_LimeStone", ())

    # 露台玻璃栏板（三面）
    tr = F3
    for (x0, x1, y0, y1) in ((PX1 - 0.06, PX1, PY0, PY1),
                             (P3X1, PX1, PY1 - 0.06, PY1),
                             (P3X1, PX1, PY0, PY0 + 0.06)):
        _box(gb_g, x0, x1, y0, y1, tr, tr + 1.05, "M_GlassRail")
        _box(gb_w, x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, tr - 0.03,
             tr + 0.09,
             "M_SteelDark")

    # 3F 内墙
    P = "M_PlasterWhite"
    _part(gb_w, X0, FOY_X0 - TI, 4.40 - TI, 4.40, F3, F3T, [(-6.20, -5.20)])
    _part(gb_w, FOY_X0 - TI, FOY_X0, Y0, 4.20, F3, F3T)
    # 茶室/卫之间 Y=5.00：只建一道墙（原 0.20 厚贴片与墙正面完全重合，已删）
    _part(gb_w, FOY_X1, X3_1, Y0, 5.00, F3, F3T, [(-1.20, -0.30)])
    _part(gb_w, FOY_X0, FOY_X1, 4.20 - TI, 4.20, F3, F3T)
    _emit(ctx, "ARCH_3F", gb_w, gb_g)


# ================================================================ 屋面
def build_roof(ctx):
    ctx.use("ROOF")
    gb_w, gb_g = GB("arw"), GB("arg")
    # 3F 屋面：只盖西侧体量
    _box(gb_w, PX0, P3X1, PY0, PY1, F3T, F3T + 0.18, "M_Fascia")
    _box(gb_w, PX0 + 0.3, P3X1 - 0.3, PY0 + 0.3, PY1 - 0.3, F3T + 0.16,
         F3T + 0.20, "M_RoofMembrane")
    # 女儿墙 0.55
    for (x0, x1, y0, y1) in ((PX0 + 0.02, PX0 + 0.22, PY0 + 0.02, PY1 - 0.02),
                             (P3X1 - 0.22, P3X1 - 0.02, PY0 + 0.02, PY1 - 0.02),
                             (PX0 + 0.22, P3X1 - 0.22, PY0 + 0.02, PY0 + 0.22),
                             (PX0 + 0.22, P3X1 - 0.22, PY1 - 0.22, PY1 - 0.02)):
        _box(gb_w, x0, x1, y0, y1, F3T + 0.05, PARAPET - 0.05, "M_LimeStone")
        _box(gb_w, x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04,
             PARAPET - 0.06, PARAPET, "M_Fascia")
    # 薄挑檐（0.55 出挑，板厚 0.18）：顶面压到 F3T-0.02，与屋面体块底面
    # (F3T) 相隔 20 mm，避免整块footprint上两个不透明面共面
    ez0, ez1 = F3T - 0.20, F3T - 0.02
    _box(gb_w, PX0 - 0.55, P3X1 + 0.55, PY0 - 0.55, PY1 + 0.55, ez0, ez1,
         "M_Fascia")
    _box(gb_w, PX0 - 0.58, P3X1 + 0.58, PY0 - 0.58, PY1 + 0.58, ez0 - 0.01,
         ez0 + 0.02, "M_SteelDark")

    # 屋面设备：3 台空调外机
    for i, (ax, ay) in enumerate(((-5.60, 7.90), (-3.40, 7.90), (1.20, 7.90))):
        _box(gb_w, ax - 0.45, ax + 0.45, ay - 0.22, ay + 0.22,
             F3T + 0.20, F3T + 0.85, "M_AluGrey")
        for k in range(7):                      # 百叶
            zz = F3T + 0.28 + k * 0.078
            _box(gb_w, ax - 0.40, ax + 0.40, ay - 0.245, ay - 0.225, zz,
                 zz + 0.045, "M_SteelDarker")
        _box(gb_w, ax - 0.45, ax + 0.45, ay - 0.22, ay + 0.22,
             F3T + 0.85, F3T + 0.88, "M_SteelDarker")
    # 落水管（背面）
    # 落水管挪到北服务带（y 9.00 之外）：原来 y 8.90…8.98 埋在 0.30 厚墙里，
    # 既看不见又与女儿墙外皮共面
    for px in (-6.60, -1.90, 1.90, 6.60):
        _box(gb_w, px - 0.05, px + 0.05, PY1 + 0.02, PY1 + 0.10,
             F1, PARAPET - 0.10, "M_SteelDarker")
        for k in range(6):
            _box(gb_w, px - 0.07, px + 0.07, PY1 + 0.01, PY1 + 0.11,
                 F1 + 0.6 + k * 1.55, F1 + 0.66 + k * 1.55, "M_SteelDark")
    # 检修口 + 地漏
    _box(gb_w, -2.10, -1.10, 8.00, 8.50, F3T + 0.20, F3T + 0.26, "M_AluGrey")
    for (dx, dy) in ((-6.20, 0.40), (2.20, 0.40)):
        _box(gb_w, dx - 0.14, dx + 0.14, dy - 0.14, dy + 0.14, F3T + 0.195,
             F3T + 0.215, "M_MetalGrey")
    # 北服务带设备（1F 背后）
    for i, (ax, ay) in enumerate(((-6.20, 9.38), (-4.60, 9.38), (3.20, 9.38))):
        _box(gb_w, ax - 0.42, ax + 0.42, ay - 0.20, ay + 0.20, F1,
             F1 + 0.62, "M_AluGrey")
    _emit(ctx, "ROOF", gb_w, gb_g)


# ================================================================ 楼梯
def _stair(gb_w, gb_g, z0, z1, n, y_start, dir_=-1, xo=0.0):
    """沿 Y 方向的直跑梯：从 y_start 向 dir_ 走，宽 1.20 居中。"""
    dz = (z1 - z0) / n
    tread = 0.28
    w0, w1 = -0.60, 0.60
    for i in range(n):
        ya = y_start + dir_ * (i * tread)
        yb = ya + dir_ * tread
        zz = z0 + dz * (i + 1) - 0.004      # 踏面比楼板顶低 4 mm，避免共面
        _box(gb_w, w0, w1, min(ya, yb), max(ya, yb), zz - 0.06, zz,
             "M_TeakFurnDark")
        _box(gb_w, w0, w1, min(ya, yb), max(ya, yb), zz - 0.10, zz - 0.06,
             "M_SteelDark")
    # 玻璃栏板 + 扶手（两侧）
    y_end = y_start + dir_ * n * tread
    for sx in (w0 - 0.02 + xo, w1 + 0.02 + xo):
        _box(gb_g, sx - 0.012, sx + 0.012, min(y_start, y_end),
             max(y_start, y_end), z0, z1 + 0.95, "M_GlassRail")
        _box(gb_w, sx - 0.03, sx + 0.03, min(y_start, y_end),
             max(y_start, y_end), z1 + 0.95, z1 + 1.01, "M_SteelDark")



# ================================================================ 入户门
def _entry(gb_w):
    # 门外两级台阶
    _box(gb_w, -1.60, 1.60, PY0 - 0.60, PY0, F0, F1 - 0.15, "M_PaveSand")
    _box(gb_w, -1.20, 1.20, PY0 - 0.30, PY0, F0, F1 - 0.05, "M_PaveSand")
    # 柚木门扇
    _box(gb_w, -0.88, 0.88, PY0 + 0.12, PY0 + 0.20, F1, F1 + 2.58, "M_SlatTeak")
    _box(gb_w, -0.05, 0.05, PY0 + 0.10, PY0 + 0.12, F1 + 0.20, F1 + 2.40,
         "M_SteelDarker")
    # 长竖把手
    _box(gb_w, 0.62, 0.68, PY0 + 0.02, PY0 + 0.10, F1 + 0.85, F1 + 1.85,
         "M_SteelDark")
    # 门槛
    _box(gb_w, -0.95, 0.95, PY0 + 0.06, PY0 + 0.22, F1 - 0.03, F1 + 0.01,
         "M_MarbleGrey")
    # 雨棚薄板
    _box(gb_w, -2.10, 2.10, PY0 - 1.10, PY0, F1 + 2.75, F1 + 2.93, "M_Fascia")


# ================================================================ 主入口
def build(ctx):
    build_1f(ctx)
    build_2f(ctx)
    build_3f(ctx)
    build_roof(ctx)
    print("[arch2] 4 floors built")
