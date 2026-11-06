"""建筑构件：墙、门窗、楼板、栏杆、楼梯、坡屋顶、檐口、月亮门。"""
import math
from mathutils import Vector, Matrix, Euler
from .kit import GB, D, TAU, lerp


def ss(e0, e1, x):
    """smoothstep"""
    if e1 == e0:
        return 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def box_axis(gb, a0, a1, b0, b1, c0, c1, axis="X", mat="M_WallWhite", smooth=False):
    if a1 - a0 <= 1e-6 or c1 - c0 <= 1e-6 or b1 - b0 <= 1e-6:
        return
    if axis == "X":
        b = ((a0, a1), (b0, b1), (c0, c1))
    else:
        b = ((b0, b1), (a0, a1), (c0, c1))
    gb.boxb(b, mat=mat, smooth=smooth)


def wall(gb, a0, a1, b0, b1, c0, c1, axis="X", mat="M_WallWhite", openings=()):
    """沿 axis 走向的墙，openings=[(a0,a1,c0,c1)] 为洞口。"""
    pieces = [(a0, a1, c0, c1)]
    for (oa0, oa1, oc0, oc1) in openings:
        oa0, oa1 = max(a0, oa0), min(a1, oa1)
        oc0, oc1 = max(c0, oc0), min(c1, oc1)
        if oa1 <= oa0 + 1e-6 or oc1 <= oc0 + 1e-6:
            continue
        newp = []
        for (pu0, pu1, pz0, pz1) in pieces:
            if oa1 <= pu0 + 1e-6 or oa0 >= pu1 - 1e-6 or oc1 <= pz0 + 1e-6 or oc0 >= pz1 - 1e-6:
                newp.append((pu0, pu1, pz0, pz1))
                continue
            if oa0 > pu0 + 1e-6:
                newp.append((pu0, oa0, pz0, pz1))
            if oa1 < pu1 - 1e-6:
                newp.append((oa1, pu1, pz0, pz1))
            ix0, ix1 = max(pu0, oa0), min(pu1, oa1)
            if oc0 > pz0 + 1e-6:
                newp.append((ix0, ix1, pz0, oc0))
            if oc1 < pz1 - 1e-6:
                newp.append((ix0, ix1, oc1, pz1))
        pieces = newp
    for (pu0, pu1, pz0, pz1) in pieces:
        box_axis(gb, pu0, pu1, b0, b1, pz0, pz1, axis, mat)


def window(gb, a0, a1, c0, c1, b0, b1, axis="X", style="lattice",
           mat_frame="M_MetalBlack", cols=3, rows=2, glass="M_WinGlow", sill=True,
           surround=False):
    """在已开洞的位置装窗：外框 + 竖梃 + 玻璃 (+ 花格)。"""
    t = (b1 - b0)
    bm = (b0 + b1) / 2
    fw = 0.055
    # 玻璃
    box_axis(gb, a0, a1, bm - 0.008, bm + 0.008, c0, c1, axis, glass)
    # 框
    box_axis(gb, a0, a1, b0, b1, c0, c0 + fw, axis, mat_frame)
    box_axis(gb, a0, a1, b0, b1, c1 - fw, c1, axis, mat_frame)
    box_axis(gb, a0, a0 + fw, b0, b1, c0, c1, axis, mat_frame)
    box_axis(gb, a1 - fw, a1, b0, b1, c0, c1, axis, mat_frame)
    # 分格
    for i in range(1, cols):
        u = lerp(a0, a1, i / cols)
        box_axis(gb, u - 0.018, u + 0.018, b0, b1, c0, c1, axis, mat_frame)
    for j in range(1, rows):
        v = lerp(c0, c1, j / rows)
        box_axis(gb, a0, a1, b0, b1, v - 0.018, v + 0.018, axis, mat_frame)
    if style == "lattice":
        # 花格：小方格
        for i in range(cols):
            for j in range(rows):
                ua = lerp(a0, a1, i / cols) + fw
                ub = lerp(a0, a1, (i + 1) / cols) - fw
                va = lerp(c0, c1, j / rows) + fw
                vb = lerp(c0, c1, (j + 1) / rows) - fw
                for k in range(1, 3):
                    u = lerp(ua, ub, k / 3)
                    box_axis(gb, u - 0.012, u + 0.012, bm - 0.035, bm - 0.02, va, vb,
                             axis, "M_WoodDark")
                for k in range(1, 3):
                    v = lerp(va, vb, k / 3)
                    box_axis(gb, ua, ub, bm - 0.035, bm - 0.02, v - 0.012, v + 0.012,
                             axis, "M_WoodDark")
    if surround:
        # 外窗套：深木压边，让立面有厚度
        e = 0.075
        for sgn in (-1, 1):
            bb0 = b0 - e if sgn < 0 else b1
            bb1 = b0 if sgn < 0 else b1 + e
            box_axis(gb, a0 - e, a1 + e, bb0, bb1, c1, c1 + e, axis, "M_WoodDark")
            box_axis(gb, a0 - e, a1 + e, bb0, bb1, c0 - e, c0, axis, "M_WoodDark")
            box_axis(gb, a0 - e, a0, bb0, bb1, c0, c1, axis, "M_WoodDark")
            box_axis(gb, a1, a1 + e, bb0, bb1, c0, c1, axis, "M_WoodDark")
    if sill:
        box_axis(gb, a0 - 0.06, a1 + 0.06, b0 - 0.09, b1 + 0.09, c0 - 0.055, c0,
                 axis, "M_StoneLight")


def glasswall(gb, a0, a1, c0, c1, b0, b1, axis="X", cols=4, rows=1,
              mat_frame="M_MetalBlack"):
    """整面落地玻璃幕墙（新中式大扇推拉门）。"""
    window(gb, a0, a1, c0, c1, b0, b1, axis, style="plain",
           mat_frame=mat_frame, cols=cols, rows=rows, sill=False)
    # 轨道
    box_axis(gb, a0, a1, b0 - 0.03, b1 + 0.03, c0, c0 + 0.04, axis, mat_frame)


def door(gb, a0, a1, c0, c1, b0, b1, axis="X", mat="M_WoodDark", open_=0.55):
    """单扇平开门：门套 + 洞口内衬 + 门槛石 + 门扇（按 open_ 部分开启）。"""
    w = (a1 - a0)
    h = (c1 - c0)
    # 洞口内衬（把墙体切面盖住，避免露出毛边）
    for (u0, u1) in ((a0, a0 + 0.022), (a1 - 0.022, a1)):
        box_axis(gb, u0, u1, b0, b1, c0, c1, axis, "M_WallWhite")
    box_axis(gb, a0, a1, b0, b1, c1 - 0.022, c1, axis, "M_WallWhite")
    # 门槛石
    box_axis(gb, a0 - 0.02, a1 + 0.02, b0 - 0.04, b1 + 0.04, c0 - 0.03, c0 + 0.012,
             axis, "M_StoneLight")
    # 外门套（比墙面凸出一点）
    e = 0.07
    box_axis(gb, a0 - e, a0, b0 - 0.03, b1 + 0.03, c0, c1 + e, axis, mat)
    box_axis(gb, a1, a1 + e, b0 - 0.03, b1 + 0.03, c0, c1 + e, axis, mat)
    box_axis(gb, a0 - e, a1 + e, b0 - 0.03, b1 + 0.03, c1, c1 + e, axis, mat)
    # 门扇
    lw = w - 0.075
    lh = h - 0.05
    ang = D(min(38.0, 58.0 * open_))
    bm = (b0 + b1) / 2
    if axis == "X":
        M = (Matrix.Translation((a0 + 0.030, bm, c0 + 0.012)) @
             Matrix.Rotation(ang, 4, "Z"))
    else:
        M = (Matrix.Translation((bm, a0 + 0.030, c0 + 0.012)) @
             Matrix.Rotation(-ang, 4, "Z"))
    with gb.frame(M):
        if axis == "X":
            gb.box((lw, 0.05, lh), (lw / 2, 0, lh / 2), mat=mat)
            for k in range(1, 4):
                gb.box((lw - 0.06, 0.058, 0.012), (lw / 2, 0, lh * k / 4), mat="M_Brass")
            gb.cyl(0.028, 0.10, (lw - 0.12, 0.09, lh * 0.46), axis="Y", mat="M_Brass")
        else:
            gb.box((0.05, lw, lh), (0, lw / 2, lh / 2), mat=mat)
            for k in range(1, 4):
                gb.box((0.058, lw - 0.06, 0.012), (0, lw / 2, lh * k / 4), mat="M_Brass")
            gb.cyl(0.028, 0.10, (0.09, lw - 0.12, lh * 0.46), axis="X", mat="M_Brass")


def double_door(gb, a0, a1, c0, c1, b0, b1, axis="X", mat="M_WoodDark", open_=0.35):
    """双开平开门：一扇开、一扇掩着，配门套/内衬/门槛石。入户门用。"""
    w = a1 - a0
    h = c1 - c0
    for (u0, u1) in ((a0, a0 + 0.022), (a1 - 0.022, a1)):
        box_axis(gb, u0, u1, b0, b1, c0, c1, axis, "M_WallWhite")
    box_axis(gb, a0, a1, b0, b1, c1 - 0.022, c1, axis, "M_WallWhite")
    box_axis(gb, a0 - 0.02, a1 + 0.02, b0 - 0.05, b1 + 0.05, c0 - 0.03, c0 + 0.014,
             axis, "M_StoneLight")
    e = 0.085
    box_axis(gb, a0 - e, a0, b0 - 0.035, b1 + 0.035, c0, c1 + e, axis, mat)
    box_axis(gb, a1, a1 + e, b0 - 0.035, b1 + 0.035, c0, c1 + e, axis, mat)
    box_axis(gb, a0 - e, a1 + e, b0 - 0.035, b1 + 0.035, c1, c1 + e, axis, mat)
    bm = (b0 + b1) / 2
    lw = (w - 0.06) / 2
    lh = h - 0.05
    for side, swing in ((-1, D(34.0 * open_ / 0.35)), (1, D(1.5))):
        hinge = a0 + 0.030 if side < 0 else a1 - 0.030
        if axis == "X":
            M = (Matrix.Translation((hinge, bm, c0 + 0.014)) @
                 Matrix.Rotation(-swing if side < 0 else swing, 4, "Z"))
        else:
            M = (Matrix.Translation((bm, hinge, c0 + 0.014)) @
                 Matrix.Rotation(swing if side < 0 else -swing, 4, "Z"))
        with gb.frame(M):
            sgn = 1 if side < 0 else -1
            if axis == "X":
                gb.box((lw, 0.05, lh), (sgn * lw / 2, 0, lh / 2), mat=mat)
                for k in range(1, 4):
                    gb.box((lw - 0.10, 0.058, 0.012),
                           (sgn * lw / 2, 0, lh * k / 4), mat="M_Brass")
                gb.cyl(0.022, 0.24, (sgn * (lw - 0.10), 0.05, lh * 0.46),
                       axis="Z", mat="M_Brass")
            else:
                gb.box((0.05, lw, lh), (0, sgn * lw / 2, lh / 2), mat=mat)
                for k in range(1, 4):
                    gb.box((0.058, lw - 0.10, 0.012),
                           (0, sgn * lw / 2, lh * k / 4), mat="M_Brass")
                gb.cyl(0.022, 0.24, (0.05, sgn * (lw - 0.10), lh * 0.46),
                       axis="Z", mat="M_Brass")


def slab(gb, x0, x1, y0, y1, z, t=0.20, mat="M_Concrete", top_mat=None,
         holes=()):
    """楼板：holes=[(x0,x1,y0,y1)] 洞口（不抠洞，用 4 条带拼出）。"""
    hx = [(-1e9, 1e9)]
    hs = list(holes)
    if not hs:
        gb.box((x1 - x0, y1 - y0, t), ((x0 + x1) / 2, (y0 + y1) / 2, z - t / 2), mat=mat)
    else:
        # 沿 X 分段
        xs = sorted(set([x0, x1] + [c for h in hs for c in (h[0], h[1])]))
        xs = [max(x0, min(x1, v)) for v in xs]
        for i in range(len(xs) - 1):
            xa, xb = xs[i], xs[i + 1]
            if xb - xa < 1e-6:
                continue
            holes_here = [h for h in hs if h[0] <= xa + 1e-6 and h[1] >= xb - 1e-6]
            if not holes_here:
                gb.box((xb - xa, y1 - y0, t), ((xa + xb) / 2, (y0 + y1) / 2, z - t / 2), mat=mat)
                continue
            ys = sorted(set([y0, y1] + [c for h in holes_here for c in (h[2], h[3])]))
            for j in range(len(ys) - 1):
                ya, yb = ys[j], ys[j + 1]
                if yb - ya < 1e-6:
                    continue
                covered = any(h[2] <= ya + 1e-6 and h[3] >= yb - 1e-6 for h in holes_here)
                if covered:
                    continue
                gb.box((xb - xa, yb - ya, t), ((xa + xb) / 2, (ya + yb) / 2, z - t / 2), mat=mat)
    if top_mat:
        gb.box((x1 - x0, y1 - y0, 0.02),
               ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.01), mat=top_mat)


def railing(gb, a0, a1, b, z, axis="X", h=1.04, mat="M_WoodDark",
            style="wood", post=0.95, slat=0.115):
    """栏杆：上下横杆 + 立柱 + 竖向密条（新中式木栏）。"""
    rr = 0.045
    # 顶部扶手
    box_axis(gb, a0, a1, b - 0.055, b + 0.055, z + h - 0.055, z + h, axis, mat)
    # 底杆
    box_axis(gb, a0, a1, b - 0.03, b + 0.03, z + 0.10, z + 0.14, axis, mat)
    n = max(2, int((a1 - a0) / post) + 1)
    for i in range(n):
        u = lerp(a0, a1, i / (n - 1))
        box_axis(gb, u - rr, u + rr, b - rr, b + rr, z, z + h, axis, mat)
    if style == "wood":
        m = max(2, int((a1 - a0) / slat))
        for i in range(1, m):
            u = lerp(a0, a1, i / m)
            box_axis(gb, u - 0.014, u + 0.014, b - 0.016, b + 0.016,
                     z + 0.14, z + h - 0.055, axis, mat)
    elif style == "glass":
        box_axis(gb, a0 + 0.03, a1 - 0.03, b - 0.006, b + 0.006,
                 z + 0.14, z + h - 0.06, axis, "M_Glass")


def stair(gb, x0, x1, y0, y1, z0, z1, steps=20, mat="M_WoodLight",
          riser_mat="M_MetalBlack", handrail=True):
    """U 型双跑楼梯：占 x0..x1 宽, y0..y1 长（沿 Y 方向两跑）。"""
    n2 = steps // 2
    rise = (z1 - z0) / steps
    width = (x1 - x0 - 0.14) / 2
    total_run = (y1 - y0) * 0.62
    tread = total_run / n2
    # 第一跑：x0..x0+width，从 y1 向 y0 方向上升
    for i in range(n2):
        zz = z0 + rise * (i + 1)
        ya = y1 - tread * (i + 1)
        yb = y1 - tread * i
        gb.box((width, tread, 0.055), (x0 + width / 2, (ya + yb) / 2, zz - 0.0275), mat=mat)
        # 踏板下的斜梁
        gb.box((width + 0.04, tread, 0.03),
               (x0 + width / 2, (ya + yb) / 2, zz - 0.09), mat=riser_mat)
    # 休息平台
    zl = z0 + rise * n2
    gb.box((x1 - x0, (y1 - y0) - total_run, 0.09),
           ((x0 + x1) / 2, (y0 + (y1 - total_run)) / 2, zl - 0.045), mat=mat)
    # 第二跑：x0+width+0.14..x1，从 y0+(y1-y0-total_run) 向 y1 上升
    ystart = y1 - total_run
    for i in range(n2):
        zz = zl + rise * (i + 1)
        ya = ystart + tread * i
        yb = ystart + tread * (i + 1)
        xa = x0 + width + 0.14
        gb.box((width, tread, 0.055), (xa + width / 2, (ya + yb) / 2, zz - 0.0275), mat=mat)
        gb.box((width + 0.04, tread, 0.03),
               (xa + width / 2, (ya + yb) / 2, zz - 0.09), mat=riser_mat)
    if handrail:
        # 沿两跑的斜扶手（用多段近似）
        for (xa, xb, flip) in ((x0 + 0.05, x0 + 0.05, False),
                               (x1 - 0.05, x1 - 0.05, True)):
            pts = []
            for i in range(n2):
                zz = z0 + rise * (i + 1) + 0.92
                yy = y1 - tread * (i + 0.5)
                pts.append((xa, yy, zz))
            if flip:
                pts = []
                for i in range(n2):
                    zz = zl + rise * (i + 1) + 0.92
                    yy = ystart + tread * (i + 0.5)
                    pts.append((xa, yy, zz))
            for i in range(len(pts) - 1):
                p, q = Vector(pts[i]), Vector(pts[i + 1])
                mid = (p + q) / 2
                d = q - p
                ln = d.length
                ang = math.atan2(d.z, d.y)
                M = Matrix.Translation(mid) @ Matrix.Rotation(-ang, 4, "X")
                with gb.frame(M):
                    gb.box((0.05, 0.05, ln * 1.02), (0, 0, 0), mat="M_MetalBlack")
                gb.cyl(0.014, 0.9, (xa, pts[i][1], pts[i][2] - 0.46), axis="Z",
                       seg=8, mat="M_MetalBlack")


# ------------------------------------------------------------------ 屋顶
def _slope_mesh(gb, origin, du, dv, nu, nv, rib_amp, rib_n, mat,
                lift_fn=None, normal=(0, 0, 1)):
    """带瓦垄起伏的坡面：参数面 origin + u*du + v*dv。"""
    nx, ny, nz = normal
    vs = []
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            u = i / nu
            p = Vector(origin) + du * u + dv * v
            rib = 0.5 + 0.5 * math.cos(TAU * u * rib_n)
            off = rib_amp * (rib ** 1.5)
            p = p + Vector(normal) * off
            if lift_fn:
                p = p + Vector((0, 0, 1)) * lift_fn(u, v)
            vs.append(tuple(p))
    fs = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            fs.append([a, a + 1, a + nu + 2, a + nu + 1])
    gb._add_faces(vs, fs, mat)


def _quad_grid(gb, fn, nu, nv, mat, smooth=False):
    """按 fn(u,v)->(x,y,z) 生成 nu*nv 网格面。"""
    vs = []
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            vs.append(tuple(fn(i / nu, v)))
    fs = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            fs.append([a, a + 1, a + nu + 2, a + nu + 1])
    gb._add_faces(vs, fs, mat, smooth)


def _bar_between(gb, p0, p1, w, h, mat, extra=0.0):
    """沿 p0->p1 摆一根方料（正脊/垂脊/扶手通用）。"""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ln = d.length + extra
    if ln < 1e-5:
        return
    M = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    with gb.frame(M):
        gb.box((w, h, ln), (0, 0, 0), mat=mat)


def pitched_roof(gb, x0, x1, y0, y1, z, rise, overhang=0.85, ridge_inset=None,
                 mat="M_Tile", rib=0.05, corner_lift=0.40, rib_n=30):
    """庑殿（四坡）顶：梯形前后坡 + 三角端坡 + 瓦垄 + 正脊 + 垂脊 + 檐口。"""
    X0, X1 = x0 - overhang, x1 + overhang
    Y0, Y1 = y0 - overhang, y1 + overhang
    ym = (Y0 + Y1) / 2.0
    inset = ridge_inset if ridge_inset is not None else (X1 - X0) * 0.20
    rx0, rx1 = X0 + inset, X1 - inset
    zr = z + rise
    nu = int(rib_n * 2)

    def eave_lift(t):
        # 檐口四角起翘：t 越靠角越大
        e = 0.16
        return corner_lift * max(0.0, 1.0 - min(t, 1.0 - t) / e) ** 1.6 if min(t, 1.0 - t) < e else 0.0

    # ---- 前后坡（梯形）----
    for sgn, ye in ((-1, Y0), (1, Y1)):
        ny, nz = (-rise, (ym - ye)) if sgn < 0 else (rise, (ye - ym))
        nl = Vector((0, ny, nz))
        nl.normalize()

        def f(u, v, ye=ye, nl=nl):
            ex = X0 + u * (X1 - X0)
            rx = rx0 + u * (rx1 - rx0)
            x = ex + (rx - ex) * v
            y = ye + (ym - ye) * v
            zz = z + rise * v + eave_lift(u) * (1 - v) ** 2
            ribo = rib * (0.5 + 0.5 * math.cos(TAU * u * rib_n)) ** 1.4
            return (x + nl.x * ribo, y + nl.y * ribo, zz + nl.z * ribo)
        _quad_grid(gb, f, nu, 4, mat)

    # ---- 左右端坡（三角）----
    for sgn, xe, rx in ((-1, X0, rx0), (1, X1, rx1)):
        nl = Vector((-1.0 if sgn < 0 else 1.0, 0, rise / max(0.6, (ym - Y0)) * 0.55))
        nl.normalize()

        def f(u, v, xe=xe, rx=rx, nl=nl):
            ey = Y0 + u * (Y1 - Y0)
            x = xe + (rx - xe) * v
            y = ey + (ym - ey) * v
            zz = z + rise * v + eave_lift(u) * (1 - v) ** 2
            ribo = rib * (0.5 + 0.5 * math.cos(TAU * u * (rib_n * (Y1 - Y0) / (X1 - X0)))) ** 1.4
            return (x + nl.x * ribo, y + nl.y * ribo, zz + nl.z * ribo)
        _quad_grid(gb, f, int(rib_n * (Y1 - Y0) / (X1 - X0)) * 2, 4, mat)

    # ---- 正脊 ----
    _bar_between(gb, (rx0 - 0.10, ym, zr), (rx1 + 0.10, ym, zr), 0.30, 0.22, "M_TileEdge")
    _bar_between(gb, (rx0 - 0.24, ym, zr + 0.14), (rx1 + 0.24, ym, zr + 0.14),
                 0.44, 0.07, "M_TileEdge")
    for ex in (rx0 - 0.18, rx1 + 0.18):
        gb.box((0.24, 0.34, 0.34), (ex, ym, zr + 0.20), mat="M_TileEdge")
        gb.cyl(0.05, 0.50, (ex, ym, zr + 0.52), axis="X", seg=10, mat="M_TileEdge",
               r_top=0.018)

    # ---- 垂脊：四角 eave corner -> 正脊端点 ----
    for sx, rx in ((X0, rx0), (X1, rx1)):
        for sy in (Y0, Y1):
            p0 = Vector((sx, sy, z + corner_lift * 0.92))
            p1 = Vector((rx, ym, zr + 0.06))
            _bar_between(gb, p0, p1, 0.17, 0.13, "M_TileEdge")
            # 脊头小兽
            gb.box((0.20, 0.20, 0.20), (sx, sy, z + corner_lift * 0.92 + 0.10),
                   mat="M_TileEdge")

    # ---- 瓦当 / 滴水（檐口一排小圆瓦头）----
    for ye, sdir in ((Y0, -1), (Y1, 1)):
        n = int((X1 - X0) / 0.34)
        for i in range(n + 1):
            u = i / n
            x = X0 + u * (X1 - X0)
            zz = z + eave_lift(u) * 0.92
            gb.cyl(0.052, 0.055, (x, ye + sdir * 0.03, zz - 0.02), axis="Y",
                   seg=10, mat="M_TileEdge")
    for xe, sdir in ((X0, -1), (X1, 1)):
        n = int((Y1 - Y0) / 0.34)
        for i in range(n + 1):
            u = i / n
            y = Y0 + u * (Y1 - Y0)
            zz = z + eave_lift(u) * 0.92
            gb.cyl(0.052, 0.055, (xe + sdir * 0.03, y, zz - 0.02), axis="X",
                   seg=10, mat="M_TileEdge")

    # ---- 檐口封板（随起翘走）----
    for ye in (Y0, Y1):
        n = 40
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            x0_, x1_ = X0 + u0 * (X1 - X0), X0 + u1 * (X1 - X0)
            zz = z + (eave_lift(u0) + eave_lift(u1)) / 2
            gb.box(((x1_ - x0_) * 1.02, 0.06, 0.13),
                   ((x0_ + x1_) / 2, ye, zz - 0.05), mat="M_TileEdge")
    for xe in (X0, X1):
        n = 30
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            y0_, y1_ = Y0 + u0 * (Y1 - Y0), Y0 + u1 * (Y1 - Y0)
            zz = z + (eave_lift(u0) + eave_lift(u1)) / 2
            gb.box((0.06, (y1_ - y0_) * 1.02, 0.13),
                   (xe, (y0_ + y1_) / 2, zz - 0.05), mat="M_TileEdge")


def eave_canopy(gb, x0, x1, y0, y1, z, out=0.95, drop=0.55, mat="M_Tile",
                sides="NS", corner_lift=0.18, rib_n=26):
    """层层出挑的瓦檐带：坡度约 30°，带瓦垄与封檐板。"""
    def band(ax, a0, a1, bfixed, sdir, nrib, lift):
        # ax='X' 表示沿 X 展开、向北/南挑出
        def f(u, v):
            if ax == "X":
                uu = u if sdir > 0 else 1 - u
                x = a0 + uu * (a1 - a0)
                y = bfixed + sdir * (out * v)
            else:
                uu = u if sdir > 0 else 1 - u
                y = a0 + uu * (a1 - a0)
                x = bfixed + sdir * (out * v)
            zz = z - drop * v + lift * (1 - v) ** 2 * eave_lift_u(uu)
            return (x, y, zz)
        _quad_grid(gb, f, nrib * 2, 3, mat)

    def eave_lift_u(u):
        e = 0.10
        return 1.0 if min(u, 1 - u) < e else max(0.0, (1.0 - min(u, 1 - u) / e) * 0.0)

    def eave_lift_u2(u):
        e = 0.12
        t = min(u, 1 - u)
        return 0.0 if t > e else (1.0 - t / e) ** 1.5

    # 四角起翘用 eave_lift_u2
    def band2(ax, a0, a1, bfixed, sdir, nrib, lift):
        def f(u, v):
            uu = u if sdir > 0 else 1 - u
            if ax == "X":
                x = a0 + uu * (a1 - a0)
                y = bfixed + sdir * (out * v)
            else:
                y = a0 + uu * (a1 - a0)
                x = bfixed + sdir * (out * v)
            zz = z - drop * v + lift * (1 - v) ** 2 * eave_lift_u2(uu)
            # 瓦垄起伏
            ro = 0.02 * (0.5 + 0.5 * math.cos(TAU * uu * nrib))
            return (x, y, zz + ro)
        _quad_grid(gb, f, nrib * 2, 3, mat)

    if "S" in sides:
        band2("X", x0 - out, x1 + out, y1, 1, rib_n, corner_lift)
        gb.box((x1 - x0 + 2 * out, 0.08, 0.16),
               ((x0 + x1) / 2, y1 + out, z - drop - 0.05), mat="M_WoodDark")
    if "N" in sides:
        band2("X", x0 - out, x1 + out, y0, -1, rib_n, corner_lift)
        gb.box((x1 - x0 + 2 * out, 0.08, 0.16),
               ((x0 + x1) / 2, y0 - out, z - drop - 0.05), mat="M_WoodDark")
    if "E" in sides:
        band2("Y", y0 - out, y1 + out, x1, 1, int(rib_n * 0.7), corner_lift)
        gb.box((0.08, y1 - y0 + 2 * out, 0.16),
               (x1 + out, (y0 + y1) / 2, z - drop - 0.05), mat="M_WoodDark")
    if "W" in sides:
        band2("Y", y0 - out, y1 + out, x0, -1, int(rib_n * 0.7), corner_lift)
        gb.box((0.08, y1 - y0 + 2 * out, 0.16),
               (x0 - out, (y0 + y1) / 2, z - drop - 0.05), mat="M_WoodDark")
    # 转角戗檐：把两带交接的缺口盖住
    if len(sides) > 2:
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx = (x1 + out * 0.55) if sx > 0 else (x0 - out * 0.55)
                cy = (y1 + out * 0.55) if sy > 0 else (y0 - out * 0.55)
                gb.box((out * 1.15, out * 1.15, 0.20),
                       (cx, cy, z - drop * 0.62), mat=mat)
                gb.box((out * 1.2, out * 1.2, 0.09),
                       (cx, cy, z - drop * 0.62 - 0.13), mat="M_TileEdge")


def moon_gate_wall(gb, x0, x1, y, z0, h, cx, r, t=0.42, mat="M_WallWhite",
                   cap_mat="M_Tile"):
    """月亮门院墙：白墙 + 圆形洞 + 瓦顶压顶。"""
    # 左段
    if cx - r > x0:
        gb.box((cx - r - x0, t, h), ((x0 + cx - r) / 2, y, z0 + h / 2), mat=mat)
    if x1 > cx + r:
        gb.box((x1 - cx - r, t, h), ((cx + r + x1) / 2, y, z0 + h / 2), mat=mat)
    # 圆洞上下：竖向细条
    n = 64
    for i in range(n):
        ua = cx - r + 2 * r * i / n
        ub = cx - r + 2 * r * (i + 1) / n
        um = (ua + ub) / 2
        hh = math.sqrt(max(0.0, r * r - (um - cx) ** 2))
        if z0 + h * 0.0 + 0 < (z0 + h):
            pass
        zt = 1.15 + hh   # 洞中心高 1.15
        if z0 + h - zt > 0.01:
            gb.box((ub - ua + 0.004, t, z0 + h - zt),
                   (um, y, (zt + z0 + h) / 2), mat=mat)
        if zt - 2 * hh - z0 > 0.01:
            gb.box((ub - ua + 0.004, t, (1.15 - hh) - z0),
                   (um, y, (z0 + 1.15 - hh) / 2), mat=mat)
    # 洞口包边（深色石/木）
    ring_n = 40
    for i in range(ring_n):
        a0 = TAU * i / ring_n
        a1 = TAU * (i + 1) / ring_n
        p0 = (cx + math.cos(a0) * r, y, 1.15 + math.sin(a0) * r)
        p1 = (cx + math.cos(a1) * r, y, 1.15 + math.sin(a1) * r)
        mid = ((p0[0] + p1[0]) / 2, y, (p0[2] + p1[2]) / 2)
        ln = math.hypot(p1[0] - p0[0], p1[2] - p0[2]) * 1.12
        ang = math.atan2(p1[2] - p0[2], p1[0] - p0[0])
        M = Matrix.Translation(mid) @ Matrix.Rotation(-ang, 4, "Y")
        with gb.frame(M):
            gb.box((ln, t + 0.06, 0.13), (0, 0, 0), mat="M_TileEdge")
    # 压顶瓦
    gb.box((x1 - x0 + 0.3, t + 0.5, 0.10), ((x0 + x1) / 2, y, z0 + h + 0.05), mat=cap_mat)
    gb.box((x1 - x0 + 0.4, t + 0.62, 0.07), ((x0 + x1) / 2, y, z0 + h + 0.13), mat="M_TileEdge")
    for sx in (x0 - 0.1, x1 + 0.1):
        gb.box((0.4, t + 0.5, 0.42), (sx, y, z0 + h + 0.21), mat=cap_mat)


def belts(gb, x0, x1, y0, y1, z, h=0.10, out=0.06, mat="M_StoneLight"):
    """腰线：环绕一圈的窄挑条，给立面加水平分层。"""
    gb.boxb(((x0 - out, x1 + out), (y0 - out, y0 + out), (z, z + h)), mat=mat)
    gb.boxb(((x0 - out, x1 + out), (y1 - out, y1 + out), (z, z + h)), mat=mat)
    gb.boxb(((x0 - out, x0 + out), (y0, y1), (z, z + h)), mat=mat)
    gb.boxb(((x1 - out, x1 + out), (y0, y1), (z, z + h)), mat=mat)


def pavilion(gb, x0, x1, y0, y1, z, h=2.85, mat="M_WoodDark", roof=True):
    """四角亭 / 廊架：石础 + 木柱 + 美人靠 + 四坡小瓦顶。"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for sx in (x0 + 0.18, x1 - 0.18):
        for sy in (y0 + 0.18, y1 - 0.18):
            gb.box((0.30, 0.30, 0.16), (sx, sy, z + 0.08), mat="M_StoneDark")
            gb.cyl(0.085, h, (sx, sy, z + h / 2), seg=10, mat=mat, r_top=0.075)
    # 枋
    for (a0, a1, bb, ax) in ((x0, x1, y0 + 0.18, "X"), (x0, x1, y1 - 0.18, "X")):
        gb.box((a1 - a0, 0.12, 0.18), ((a0 + a1) / 2, bb, z + h - 0.12), mat=mat)
    for (b0, b1, aa) in ((y0, y1, x0 + 0.18), (y0, y1, x1 - 0.18)):
        gb.box((0.12, b1 - b0, 0.18), (aa, (b0 + b1) / 2, z + h - 0.12), mat=mat)
    # 美人靠（三面）
    railing(gb, x0 + 0.18, x1 - 0.18, y1 - 0.18, z, "X", 0.92, mat, "wood", post=0.7)
    railing(gb, y0 + 0.18, y1 - 0.18, x0 + 0.18, z, "Y", 0.92, mat, "wood", post=0.7)
    if roof:
        pitched_roof(gb, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, z + h, 0.95,
                     overhang=0.75, ridge_inset=(x1 - x0) * 0.18, corner_lift=0.32,
                     rib_n=12)


def cornice(gb, x0, x1, y0, y1, z, t=0.12, mat="M_StoneLight"):
    """腰线 / 压边"""
    for (bx, by, sx, sy) in ((0, y0, x1 - x0 + 2 * t, t), (0, y1, x1 - x0 + 2 * t, t),
                             (x0, 0, t, y1 - y0), (x1, 0, t, y1 - y0)):
        if sx > 1:
            gb.box((sx, sy, t * 1.2), (bx if sx > 1 else (x0 + x1) / 2,
                                      by if sy >= t else (y0 + y1) / 2, z), mat=mat)


def planter(gb, x0, x1, y0, y1, z, h=0.45, mat="M_StoneDark"):
    """种植池（无盖）"""
    t = 0.09
    gb.box((x1 - x0, y1 - y0, 0.06), ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.03), mat="M_Soil")
    for (bx, by, sx, sy) in ((0, y0, x1 - x0, t), (0, y1, x1 - x0, t),
                             (x0, 0, t, y1 - y0 - 2 * t), (x1, 0, t, y1 - y0 - 2 * t)):
        if sx > 1 or sy > 1:
            gb.box((sx, sy, h),
                   ((x0 + x1) / 2 if sx > 1 else bx, (y0 + y1) / 2 if sy > 1 else by,
                    z + h / 2), mat=mat)
