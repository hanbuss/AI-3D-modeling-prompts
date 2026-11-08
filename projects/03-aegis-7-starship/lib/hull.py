"""starship/lib/hull.py — 船体外形内核：站位插值 / 表面采样 / 贴合船壳的装甲板

外形不是超椭圆蛋壳，而是**带舷线的舰体剖面**（这是"看着像飞船"的关键）：
  平顶甲板 → 肩部倒角 → 硬舷线（chine）→ 下舷 → 平底
硬舷线处顶点**复制**一份，放样后自然形成硬边（不复制的话平滑着色会把棱线抹掉，看起来像香肠）。

对外 API（别的模块只许用这些，改签名会打断队友）：
  sect(x)              -> (半宽 w, 上高 ht, 下深 hb)
  surface_yz(x, th)    -> (y, z) 沿角度 th 的壳面点
  normal_yz(x, th)     -> (ny, nz) 外法线
  surf(x, th, off)     -> Vector 世界点（off 沿法线外推）
  surf_n(x, th)        -> Vector 法线
  frame(x, th)         -> (n, tx, tth) 表面切空间
  deck_z(x), keel_z(x) -> 背脊顶面 / 龙骨底面高度
  segment(name, x0, x1, ...)   -> 放样船体段
  plate(...), plate_band(...)  -> 贴合壳面的装甲板
"""
import math
import bpy, bmesh
from mathutils import Vector

import kit
import spec as S

# 剖面控制点（归一化：y 以 w 为单位，z 以 ht/hb 为单位）
# (yn, zn_ratio, kind)  kind: 'p'=普通点, 'h'=硬边（顶点复制）
PROFILE = [
    (0.000,  1.000, 'h'),   # 顶部甲板中点
    (0.520,  1.000, 'h'),   # 甲板边缘
    (0.800,  0.930, 'p'),   # 肩部
    (0.968,  0.700, 'p'),   # 肩部倒角下缘
    (1.000,  0.120, 'h'),   # 上舷线（硬棱）
    (1.000, -0.180, 'h'),   # 下舷线（硬棱）
    (0.905, -0.640, 'p'),
    (0.780, -0.900, 'p'),
    (0.430, -1.000, 'h'),   # 平底边缘
    (0.000, -1.000, 'h'),   # 平底中点
]
SUBDIV = 3   # 每段插值点数（越多越圆）


def sect(x):
    """x 处的 (半宽 w, 上部高 ht, 下部深 hb)，站位之间线性插值"""
    st = S.STATIONS
    if x >= st[0][0]:
        return st[0][1], st[0][2], st[0][3]
    if x <= st[-1][0]:
        return st[-1][1], st[-1][2], st[-1][3]
    for (x0, w0, ht0, hb0), (x1, w1, ht1, hb1) in zip(st[:-1], st[1:]):
        if x1 <= x <= x0:
            t = (x0 - x) / (x0 - x1)
            return (w0 + (w1 - w0) * t, ht0 + (ht1 - ht0) * t, hb0 + (hb1 - hb0) * t)
    return st[-1][1], st[-1][2], st[-1][3]


def profile_pts(x, subdiv=None):
    """x 处的闭合剖面点列 [(y,z), ...]；硬边处**重复顶点**（放样后成为硬棱）

    顺序：顶部甲板中点 → +Y 侧下行 → 底部中点 → -Y 侧上行 → 回顶（闭合）。
    """
    w, ht, hb = sect(x)
    sub = SUBDIV if subdiv is None else subdiv
    half = [(yn * w, (ht if zn >= 0 else hb) * zn) for (yn, zn, _k) in PROFILE]
    kinds_half = [k for (_yn, _zn, k) in PROFILE]
    # 拼成整圈控制点（含左右两侧），并带上每点的硬边标记
    ctrl = list(half) + [(-y, z) for (y, z) in half[-2:0:-1]]
    kinds = list(kinds_half) + [kinds_half[i] for i in range(len(half) - 2, 0, -1)]

    pts = []
    n = len(ctrl)
    for i in range(n):
        y0, z0 = ctrl[i]
        if kinds[i] == 'h':
            pts.append((y0, z0))          # 复制一份 → 硬棱
        pts.append((y0, z0))
        y1, z1 = ctrl[(i + 1) % n]
        for s in range(1, sub):
            t = s / sub
            pts.append((y0 + (y1 - y0) * t, z0 + (z1 - z0) * t))
    return pts


def _ray_poly(x, th):
    """从剖面中心沿角度 th 射线与剖面多边形的交点（保证表面采样与新外形一致）"""
    poly = profile_pts(x)
    dy, dz = math.cos(th), math.sin(th)
    best = None
    n = len(poly)
    for i in range(n):
        ay, az = poly[i]
        by, bz = poly[(i + 1) % n]
        ey, ez = by - ay, bz - az
        den = dy * ez - dz * ey
        if abs(den) < 1e-12:
            continue
        t = (ay * ez - az * ey) / den          # 射线参数
        u = -(dy * az - dz * ay) / den         # 边参数（符号由 Cramer 推导：u = (az*dy - ay*dz)/(-den)）
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            if best is None or t < best[0]:
                # 收集该边法线
                nl = math.hypot(ey, ez) or 1.0
                ny, nz = ez / nl, -ey / nl
                if ny * dy + nz * dz < 0:
                    ny, nz = -ny, -nz
                best = (t, ny, nz)
    if best is None:
        w, ht, hb = sect(x)
        return dy * w, dz * (ht if dz >= 0 else hb), 0.0, 1.0
    t, ny, nz = best
    return dy * t, dz * t, ny, nz


def surface_yz(x, th):
    y, z, _ny, _nz = _ray_poly(x, th)
    return y, z


def normal_yz(x, th):
    _y, _z, ny, nz = _ray_poly(x, th)
    return ny, nz


def surf(x, th, off=0.0):
    """世界坐标表面点，off > 0 沿外法线外推"""
    y, z, ny, nz = _ray_poly(x, th)
    return Vector((x, y + ny * off, z + nz * off))


def surf_n(x, th):
    _y, _z, ny, nz = _ray_poly(x, th)
    return Vector((0.0, ny, nz))


def dekc(x):
    return sect(x)


def deck_z(x):
    """背脊顶面高度"""
    return sect(x)[1]


def keel_z(x):
    return -sect(x)[2]


def frame(x, th):
    """表面切空间：返回 (法线, 沿 X 前向, 沿 th 切向)，都是世界单位向量"""
    n = surf_n(x, th)
    p0 = surf(x - 0.05, th)
    p1 = surf(x + 0.05, th)
    tx = (p1 - p0).normalized()
    tth = n.cross(tx).normalized()
    return n, tx, tth


# ------------------------------------------------------------------ 放样
def ring(x):
    return profile_pts(x)


def segment(name, x0, x1, nx=14, n=None, mat=None, col=None, cap_start=True, cap_end=True,
            smooth=True, bw=0.004):
    """船体段放样。n 参数只为兼容旧调用（剖面点列由 profile_pts 决定）"""
    rings = []
    for i in range(nx + 1):
        t = i / nx
        x = x0 + (x1 - x0) * t
        rings.append((x, profile_pts(x)))
    ob = kit.loft(name, rings, mat=mat, col=col, close_start=cap_start, close_end=cap_end,
                  smooth=smooth)
    if bw:
        kit.bevel(ob, bw, 2, 40.0)
        kit.apply_modifiers(ob)
    return ob


# ------------------------------------------------------------------ 贴合装甲板
def plate(name, x0, x1, th0, th1, out=0.014, thick=0.010, nx=6, nt=5,
          mat=None, col=None, shrink=0.0, bw=0.0035):
    """一块贴合船壳的曲面板（外贴装甲 / 检修盖板）。x0>x1 沿首→尾，th 为角度区间。"""
    if shrink:
        dx = (x0 - x1) * shrink
        x0 -= dx
        x1 += dx
        dth = (th1 - th0) * shrink
        th0 += dth
        th1 -= dth
    nx = max(2, nx)
    nt = max(1, nt)
    outer, inner = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * (i / nx)
        ro, ri = [], []
        for j in range(nt + 1):
            th = th0 + (th1 - th0) * (j / nt)
            ro.append(surf(x, th, out))
            ri.append(surf(x, th, out - thick))
        outer.append(ro)
        inner.append(ri)
    bm = bmesh.new()
    vo = [[bm.verts.new(p) for p in row] for row in outer]
    vi = [[bm.verts.new(p) for p in row] for row in inner]
    for i in range(nx):
        for j in range(nt):
            bm.faces.new((vo[i][j], vo[i + 1][j], vo[i + 1][j + 1], vo[i][j + 1]))
            bm.faces.new((vi[i][j], vi[i][j + 1], vi[i + 1][j + 1], vi[i + 1][j]))
    for j in range(nt):
        bm.faces.new((vo[0][j], vo[0][j + 1], vi[0][j + 1], vi[0][j]))
        bm.faces.new((vo[nx][j], vi[nx][j], vi[nx][j + 1], vo[nx][j + 1]))
    for i in range(nx):
        bm.faces.new((vo[i][0], vi[i][0], vi[i + 1][0], vo[i + 1][0]))
        bm.faces.new((vo[i][nt], vo[i + 1][nt], vi[i + 1][nt], vi[i][nt]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.bevel(ob, bw, 1, 42.0)
        kit.apply_modifiers(ob)
    return ob


def plate_band(name, x0, x1, center_th, span_th, out=0.013, thick=0.009, nx=8, nt=4,
               mat=None, col=None, gap=0.006, count=1, step=0.0):
    obs = []
    for k in range(count):
        c = center_th + step * k
        obs.append(plate("%s_%d" % (name, k), x0, x1, c - span_th / 2, c + span_th / 2,
                         out=out, thick=thick, nx=nx, nt=nt, mat=mat, col=col, shrink=gap))
    return kit.join(obs, name) if len(obs) > 1 else obs[0]


def place_on_hull(name, proto_fn, x, th, extra_out=0.0):
    """把局部 +Z 朝上的零件摆到船壳上（proto_fn(name) 返回对象）"""
    ob = proto_fn(name)
    p = surf(x, th, extra_out)
    n, tx, tth = frame(x, th)
    m = kit.mat_from_axes(tth, n, tx)
    ob.matrix_world = m
    ob.location = p
    return ob
