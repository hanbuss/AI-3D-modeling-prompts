"""starship/lib/fore.py — 舰首段（Fore Section）：舱盖 / 座舱 / 鼻锥传感器 / 装甲板 / 进气口 / RCS / 航行灯

坐标（全工程统一）：+X = 舰首，+Y = 右舷，+Z = 上，单位米。
外形真值一律来自 hull.py（sect / surf / surf_n / frame / plate / deck_z），
本模块不自己猜船壳形状 —— 所有贴付件都用 hull.surf(x, th, off) 落在壳面上。

舱盖的"泡泡"曲面是本模块自己定义的一层附加曲面（canopy surface）：
基线 = hull.deck_z(x)（甲板平面），横截面 = 超椭圆幂 2.8 的圆顶，
半宽与隆起沿 X 各自插值。玻璃、框条、内衬全部按同一参数域 (x, vy) 采样，
所以玻璃缝、框条、内衬天然对齐，不会出现"框浮在玻璃外"的破绽。

模块契约：
    def build(M, col) -> list[Object]
    每个零件都用 kit.part(...) 打标（part_id 前缀 fore_）。
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix

import kit
import hull
import mats
import spec as S

TAU = math.tau
R = math.radians


# ====================================================================== 基础工具
def _lerp(a, b, t):
    return a + (b - a) * t


def _pw(t, table):
    """分段平滑插值：table = [(t0,v0), (t1,v1), ...]（t 递增）"""
    if t <= table[0][0]:
        return table[0][1]
    if t >= table[-1][0]:
        return table[-1][1]
    for (t0, v0), (t1, v1) in zip(table[:-1], table[1:]):
        if t0 <= t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return _lerp(v0, v1, u)
    return table[-1][1]


def _m(n, p, up=None):
    """把局部 +Z 对齐到法线 n、原点放在 p 的 4x4 矩阵"""
    n = Vector(n).normalized()
    ref = Vector(up) if up else Vector((1.0, 0.0, 0.0))
    if abs(ref.dot(n)) > 0.94:
        ref = Vector((0.0, 1.0, 0.0))
    x = ref.cross(n).normalized()
    y = n.cross(x).normalized()
    return kit.mat_from_axes(x, y, n, tuple(p))


def _arc(x, th0, th1, n=12):
    """x 站位上 th0→th1 的弧长（米），把毫米缝隙换算成角度用"""
    ps = [hull.surf(x, th0 + (th1 - th0) * i / n) for i in range(n + 1)]
    return sum((ps[i + 1] - ps[i]).length for i in range(n))


def _inset(x0, x1, t0, t1, gap):
    """四边各内缩 gap/2（米）→ 真实板缝。返回 (x0, x1, t0, t1)"""
    xm = (x0 + x1) * 0.5
    a = _arc(xm, t0, t1) or 1.0
    dt = (gap * 0.5) / a * abs(t1 - t0)
    s = 1.0 if t1 > t0 else -1.0
    return (x0 - gap * 0.5, x1 + gap * 0.5, t0 + s * dt, t1 - s * dt)


def surf_normal(x, th):
    n = hull.surf_n(x, th)
    return Vector((0.0, n.y, n.z)).normalized()


def _cutter(name, x0, x1, t0, t1, o0, o1, col=None):
    """(x, th, offset) 空间里的六面体 —— 布尔切割用，切出来的孔是贴着曲面的"""
    bm = bmesh.new()
    V = {}
    for i, x in enumerate((x0, x1)):
        for j, th in enumerate((t0, t1)):
            for k, o in enumerate((o0, o1)):
                V[(i, j, k)] = bm.verts.new(hull.surf(x, th, o))
    quads = [
        [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
        [(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)],
        [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],
        [(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)],
        [(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)],
        [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
    ]
    for q in quads:
        try:
            bm.faces.new([V[k] for k in q])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, None, col, smooth=False)


def _patch(name, pfn, u0, u1, v0, v1, nu, nv, thick, mat, col, out=0.0, bw=0.0016):
    """参数面片（带厚度）：pfn(u, v) -> (点, 法线)。玻璃 / 内衬 / 地板 / 凹陷底板都用它"""
    nu, nv = max(1, nu), max(1, nv)
    bm = bmesh.new()
    O, I = [], []
    for i in range(nu + 1):
        u = u0 + (u1 - u0) * i / nu
        ro, ri = [], []
        for j in range(nv + 1):
            v = v0 + (v1 - v0) * j / nv
            p, n = pfn(u, v)
            ro.append(bm.verts.new(p + n * out))
            ri.append(bm.verts.new(p + n * (out - thick)))
        O.append(ro)
        I.append(ri)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((O[i][j], O[i + 1][j], O[i + 1][j + 1], O[i][j + 1]))
            bm.faces.new((I[i][j], I[i][j + 1], I[i + 1][j + 1], I[i + 1][j]))
    for j in range(nv):
        bm.faces.new((O[0][j], O[0][j + 1], I[0][j + 1], I[0][j]))
        bm.faces.new((O[nu][j], I[nu][j], I[nu][j + 1], O[nu][j + 1]))
    for i in range(nu):
        bm.faces.new((O[i][0], I[i][0], I[i + 1][0], O[i + 1][0]))
        bm.faces.new((O[i][nv], O[i + 1][nv], I[i + 1][nv], I[i][nv]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.bevel(ob, bw, 1, 42.0)
        kit.apply_modifiers(ob)
    return ob


def _sweep(name, pts, nrms, prof, mat, col, closed=False, cap=True, bw=0.0012):
    """沿空间折线扫掠 2D 剖面（u = 面内横向，v = 沿法线向外）。框条 / 百叶 / 唇口都是它做的"""
    n = len(pts)
    if n < 2:
        return None
    bm = bmesh.new()
    rings = []
    for i in range(n):
        p, nr = Vector(pts[i]), Vector(nrms[i]).normalized()
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
        t = Vector(b) - Vector(a)
        if t.length < 1e-9:
            t = Vector((1.0, 0.0, 0.0))
        t.normalize()
        side = nr.cross(t)
        if side.length < 1e-9:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        rings.append([bm.verts.new(p + side * u + nr * v) for (u, v) in prof])
    m = len(prof)
    idx = range(n) if closed else range(n - 1)
    for i in idx:
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(m):
            try:
                bm.faces.new((a[k], a[(k + 1) % m], b[(k + 1) % m], b[k]))
            except ValueError:
                pass
    if cap and not closed:
        try:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.bevel(ob, bw, 1, 42.0)
        kit.apply_modifiers(ob)
    return ob


def _prof_rail(w, h):
    """框条剖面：底平、顶收窄带小圆角（六边形闭环）"""
    hw = w * 0.5
    return [(-hw, 0.0), (-hw * 0.90, h * 0.46), (-hw * 0.52, h),
            (hw * 0.52, h), (hw * 0.90, h * 0.46), (hw, 0.0)]


def _prof_louver(w, h, tilt=0.42):
    """百叶剖面：平行四边形倾斜叶片"""
    hw = w * 0.5
    return [(-hw, 0.0), (hw, 0.0), (hw + h * tilt, h), (-hw + h * tilt, h)]


def _prof_flat(w, h, taper=0.86):
    hw = w * 0.5
    return [(-hw, 0.0), (hw, 0.0), (hw * taper, h), (-hw * taper, h)]


def _mx(xdir, p):
    """局部 +X → 给定方向、原点在 p 的 4x4（RCS 这类轴向零件整体映射用）"""
    x = Vector(xdir).normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(x.z) < 0.9 else Vector((0.0, 1.0, 0.0))
    y = ref.cross(x).normalized()
    z = x.cross(y).normalized()
    return kit.mat_from_axes(x, y, z, tuple(p))


def _scoop_pad(name, x0, x1, t0, t1, mat, col, out_front=0.03, out_mid=0.10,
               out_rear=0.04, thick=0.07, nx=12, nt=8, bw=0.0028):
    """变厚度曲面整流罩：前缘贴壳、中后段鼓起、尾端收薄（进气/散热口的基座）"""
    bm = bmesh.new()
    layers = []
    for i in range(nx + 1):
        u = i / nx
        x = _lerp(x0, x1, u)
        if u < 0.45:
            off = _lerp(out_front, out_mid, u / 0.45)
        else:
            off = _lerp(out_mid, out_rear, (u - 0.45) / 0.55)
        ro, ri = [], []
        for j in range(nt + 1):
            th = _lerp(t0, t1, j / nt)
            ro.append(bm.verts.new(hull.surf(x, th, off)))
            ri.append(bm.verts.new(hull.surf(x, th, max(0.002, off - thick))))
        layers.append((ro, ri))
    for i in range(nx):
        (ao, ai), (bo, bi) = layers[i], layers[i + 1]
        for j in range(nt):
            bm.faces.new((ao[j], bo[j], bo[j + 1], ao[j + 1]))
            bm.faces.new((ai[j], ai[j + 1], bi[j + 1], bi[j]))
    (ao, ai) = layers[0]
    for j in range(nt):
        bm.faces.new((ao[j], ao[j + 1], ai[j + 1], ai[j]))
    (ao, ai) = layers[-1]
    for j in range(nt):
        bm.faces.new((ao[j], ai[j], ai[j + 1], ao[j + 1]))
    for (ro, ri) in (layers[0], layers[-1]):
        pass
    for i in range(nx):
        (ao, ai) = layers[i]
        (bo, bi) = layers[i + 1]
        bm.faces.new((ao[0], ai[0], bi[0], bo[0]))
        bm.faces.new((ao[nt], bo[nt], bi[nt], ai[nt]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.bevel(ob, bw, 1, 42.0)
        kit.apply_modifiers(ob)
    return ob


def _bolt(name, x, th, r=0.017, h=0.012, mat=None, col=None, off=0.014):
    """落在船壳表面上的螺钉（沿局部法线立起来）"""
    p = hull.surf(x, th, off)
    nrm = surf_normal(x, th)
    ob = kit.cyl(name, r, h, axis='Z', mat=mat, col=col, seg=6, bw=0.0016, segs=1)
    ob.matrix_world = _m(nrm, p + nrm * (h * 0.5))
    return ob


def _th_for(x, ty, tz):
    """给定 (x, 目标 y, 目标 z) 反求参数角 th —— spec 里写的是绝对坐标，贴付件要落到壳面上"""
    best, bt = 1e9, 0.0
    for i in range(361):
        th = -math.pi + TAU * i / 360.0
        y, z = hull.surface_yz(x, th)
        d = (y - ty) ** 2 + (z - tz) ** 2
        if d < best:
            best, bt = d, th

    def err(t):
        y, z = hull.surface_yz(x, t)
        return (y - ty) ** 2 + (z - tz) ** 2

    lo, hi = bt - 0.02, bt + 0.02
    for _ in range(48):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if err(m1) < err(m2):
            hi = m2
        else:
            lo = m1
    return (lo + hi) * 0.5


# ====================================================================== 舱盖曲面
CAN_FRONT = 9.35          # 舱盖前缘（风挡底缘，落在甲板上）
CAN_REAR = 6.15           # 舱盖后缘
CAN_P = 2.55              # 横截面超椭圆幂：顶部圆、两侧向下收
CAN_SILL = 0.008          # 玻璃槛高出甲板

# 注意：_pw() 要求控制表按 x **递增**排列（递减会让所有 x 都取到端点值）
_CAN_W = [(6.15, 0.660), (6.75, 0.772), (7.40, 0.780), (8.00, 0.720),
          (8.55, 0.600), (9.00, 0.455), (9.35, 0.300)]
_CAN_R = [(6.15, 0.560), (6.60, 0.790), (7.10, 0.860), (7.60, 0.855),
          (8.00, 0.790), (8.40, 0.650), (8.75, 0.450), (9.10, 0.230),
          (9.35, 0.080)]
COAM_TH = (1.045, 2.096)  # 座舱开口围框的内缘参数角（+Y 侧 / -Y 侧）


def can_hw(x):
    return _pw(x, _CAN_W)


def can_rise(x):
    return _pw(x, _CAN_R)


def can_n(x, vy):
    """舱盖曲面法线（解析式，避开 vy=±1 的数值奇点）"""
    a = min(0.999, abs(vy))
    s = 1.0 if vy >= 0 else -1.0
    hw = can_hw(x)
    rz = can_rise(x)
    k = max(1e-6, 1.0 - a ** CAN_P)
    dzda = -rz * (a ** (CAN_P - 1.0)) * (k ** (1.0 / CAN_P - 1.0))
    dzda = max(-60.0, min(60.0, dzda))
    e = 0.02
    hw2 = (can_hw(x + e) - can_hw(x - e)) / (2 * e)
    rz2 = (can_rise(x + e) - can_rise(x - e)) / (2 * e)
    k2 = k ** (1.0 / CAN_P)
    ta = Vector((0.0, s * hw, dzda))
    tx = Vector((1.0, s * a * hw2, rz2 * k2))
    n = ta.cross(tx)
    if n.length < 1e-9:
        n = Vector((0.0, s, 1.0))
    n.normalize()
    if n.dot(Vector((0.0, s * a, 1.0))) < 0:
        n = -n
    return n


def can_pt(x, vy, out=0.0):
    """舱盖曲面上的一点（out>0 沿法线外推）"""
    a = min(1.0, abs(vy))
    hw = can_hw(x)
    z0 = hull.deck_z(x) + CAN_SILL
    k = max(0.0, 1.0 - a ** CAN_P)
    z = z0 + can_rise(x) * (k ** (1.0 / CAN_P))
    p = Vector((x, vy * hw, z))
    if out:
        p = p + can_n(x, vy) * out
    return p


def _can_pfn():
    return lambda u, v: (can_pt(u, v), can_n(u, v))


X_BOW = 8.55              # 风挡 / 顶窗的分界横梁（风挡顶缘）
V_ROOF = 0.62             # 顶窗 / 侧窗的分界纵梁


# ====================================================================== 1. 舱盖
def build_canopy(M, col):
    out = []
    G = "canopy"
    gs_out, gs_th = 0.001, 0.013

    def glass(nm, x0, x1, v0, v1, nu, nv):
        return _patch(nm, _can_pfn(), x0, x1, v0, v1, nu, nv, gs_th,
                      M['canopy'], col, out=gs_out, bw=0.0012)

    # 四片玻璃：前风挡（后倾 32°）+ 顶窗 + 左右侧窗
    ws = glass("canopy_glass_ws", CAN_FRONT - 0.004, X_BOW, -1.0, 1.0, 12, 20)
    roof = glass("canopy_glass_roof", X_BOW, CAN_REAR + 0.004, -V_ROOF, V_ROOF, 14, 10)
    sp = glass("canopy_glass_side_p", X_BOW, CAN_REAR + 0.004, V_ROOF, 1.0, 14, 5)
    ss = glass("canopy_glass_side_s", X_BOW, CAN_REAR + 0.004, -1.0, -V_ROOF, 14, 5)
    out += [
        kit.part(ws, "fore_canopy_glass_ws", "前风挡", "Canopy Windshield", G, (0.3, 0, 1),
                 note="环绕式风挡：底缘 x=9.35 落甲板，顶缘 x=8.55 抬高 0.5m（后倾约 32°）"),
        kit.part(roof, "fore_canopy_glass_roof", "顶窗", "Canopy Roof Window", G, (0, 0, 1),
                 note="顶部主观察窗，罩在双座头顶，与侧窗以纵梁真实分缝"),
        kit.part(sp, "fore_canopy_glass_side_p", "右舷侧窗", "Starboard Side Window", G,
                 (0.35, 0.9, 0.35), note="侧窗玻璃沿舷边向下收，四边被框条夹住"),
        kit.part(ss, "fore_canopy_glass_side_s", "左舷侧窗", "Port Side Window", G,
                 (0.35, -0.9, 0.35), note="侧窗玻璃沿舷边向下收，四边被框条夹住"),
    ]

    # ---- 框条（沿舱盖曲面扫掠；框顶比玻璃高 32mm → 框包玻璃）
    FR_W, FR_H = 0.046, 0.028
    prof = _prof_rail(FR_W, FR_H)
    fp = 0.006

    def arch(nm, x, n=24):
        pts, nrs = [], []
        for i in range(n + 1):
            v = _lerp(-1.0, 1.0, i / n)
            pts.append(can_pt(x, v, fp))
            nrs.append(can_n(x, v))
        return _sweep(nm, pts, nrs, prof, M['black'], col)

    def rail(nm, vy, x0, x1, n=16):
        pts, nrs = [], []
        for i in range(n + 1):
            x = _lerp(x0, x1, i / n)
            pts.append(can_pt(x, vy, fp))
            nrs.append(can_n(x, vy))
        return _sweep(nm, pts, nrs, prof, M['black'], col)

    a_bow = arch("canopy_frame_bow", X_BOW)
    a_rear = arch("canopy_frame_rear", CAN_REAR + 0.006)
    r_p = rail("canopy_rail_p", V_ROOF, X_BOW, CAN_REAR + 0.004)
    r_s = rail("canopy_rail_s", -V_ROOF, X_BOW, CAN_REAR + 0.004)
    out += [
        kit.part(a_bow, "fore_canopy_frame_bow", "舱盖横梁", "Canopy Bow Frame", G,
                 (0.3, 0, 1), note="风挡与顶窗之间的弓形横梁"),
        kit.part(a_rear, "fore_canopy_frame_rear", "后弧框", "Canopy Aft Frame", G,
                 (-1, 0, 0.35), note="舱盖后缘框，接后隔框与作动筒"),
        kit.part(r_p, "fore_canopy_rail_p", "右舷窗框纵梁", "Starboard Canopy Rail", G,
                 (0.25, 0.9, 0.45), note="顶窗 / 侧窗之间的纵梁，形成真实分缝"),
        kit.part(r_s, "fore_canopy_rail_s", "左舷窗框纵梁", "Port Canopy Rail", G,
                 (0.25, -0.9, 0.45), note="顶窗 / 侧窗之间的纵梁，形成真实分缝"),
    ]

    # ---- 座舱开口围框：整圈沿船壳弧面走（hull.surf 采样，闭合扫掠）
    coam = _coaming_ring(M, col)
    out.append(kit.part(coam, "fore_canopy_coaming", "座舱开口围框（coaming）",
                        "Cockpit Coaming Ring", G, (0, 0.15, 1),
                        note="整圈围框：宽 0.10m、外凸 0.03m，四点按 hull.surf 采样 → 顺船壳弧度"))

    # ---- 舱盖密封条（玻璃槛下的胶条，绕开口一圈）
    seal_pts, seal_nrs = [], []
    for i in range(41):
        t = i / 40.0
        x = _lerp(CAN_FRONT, CAN_REAR, t)
        v = 0.965 if i <= 20 else -0.965
        seal_pts.append(can_pt(x, v, -0.007))
        seal_nrs.append(can_n(x, v))
    seal = _sweep("canopy_seal", seal_pts, seal_nrs, _prof_flat(0.034, 0.014),
                  M['rubber'], col)
    out.append(kit.part(seal, "fore_canopy_seal", "舱盖密封条", "Canopy Seal", G,
                        (0, 0.2, 1), note="玻璃槛与围框之间的密封胶条（左右两道）"))

    # ---- 舱盖举升作动筒（左右各一）
    for sgn in (1, -1):
        bx = 6.34
        th = _th_for(bx, can_hw(bx) * sgn * 0.93, hull.deck_z(bx) + 0.06)
        p0 = hull.surf(bx, th, 0.030)
        p1 = can_pt(bx + 0.52, sgn * 0.88, 0.010)
        d = p1 - p0
        body = kit.cyl("canopy_act_%d" % sgn, 0.022, d.length * 0.58, axis='Z',
                       mat=M['frame'], col=col, seg=10, bw=0.0014, segs=1)
        body.matrix_world = _m(d.normalized(), p0 + d * 0.29)
        rod = kit.cyl("canopy_rod_%d" % sgn, 0.011, d.length * 0.66, axis='Z',
                      mat=M['alu'], col=col, seg=8, bw=0.0010, segs=1)
        rod.matrix_world = _m(d.normalized(), p0 + d * 0.65)
        ear = kit.cyl("canopy_ear_%d" % sgn, 0.028, 0.020, axis='Y',
                      mat=M['gunmetal'], col=col, seg=10, bw=0.0012, segs=1)
        ear.matrix_world = _m(d.normalized(), p0)
        ob = kit.join([body, rod, ear], "canopy_actuator_%s" % ("p" if sgn > 0 else "s"))
        out.append(kit.part(ob, "fore_canopy_actuator_" + ("p" if sgn > 0 else "s"),
                            "舱盖作动筒" + ("·右" if sgn > 0 else "·左"),
                            "Canopy Actuator " + ("Stbd" if sgn > 0 else "Port"), G,
                            (0.2, sgn * 0.7, 0.65), note="举升液压筒：底座落甲板、杆头接舱盖框"))
    return out


def _coaming_ring(M, col):
    """座舱开口整圈围框：沿船壳表面采样闭合路径再扫掠 —— 框体自然顺壳弧"""
    TH_S, TH_P = COAM_TH
    n_f, n_s = 14, 16
    pts, nrs = [], []
    for i in range(n_f):                                  # 前缘（沿 th 横扫）
        th = _lerp(TH_S, TH_P, i / float(n_f - 1))
        pts.append(hull.surf(CAN_FRONT + 0.06, th, 0.004))
        nrs.append(surf_normal(CAN_FRONT + 0.06, th))
    for i in range(n_s):                                  # 右舷侧（沿 x）
        x = _lerp(CAN_FRONT + 0.03, CAN_REAR - 0.03, i / float(n_s - 1))
        pts.append(hull.surf(x, TH_S, 0.004))
        nrs.append(surf_normal(x, TH_S))
    for i in range(n_f):                                  # 后缘（沿 th 反扫）
        th = _lerp(TH_P, TH_S, i / float(n_f - 1))
        pts.append(hull.surf(CAN_REAR - 0.06, th, 0.004))
        nrs.append(surf_normal(CAN_REAR - 0.06, th))
    for i in range(n_s):                                  # 左舷侧（沿 x 反向）
        x = _lerp(CAN_REAR - 0.03, CAN_FRONT + 0.03, i / float(n_s - 1))
        pts.append(hull.surf(x, TH_P, 0.004))
        nrs.append(surf_normal(x, TH_P))
    ring = _sweep("coaming_ring", pts, nrs, _prof_rail(0.082, 0.026),
                  M['hull_dark'], col, closed=True, bw=0.0022)
    lip_pts = [Vector((p.x, p.y, p.z)) for p in pts]
    lip = _sweep("coaming_lip", pts, nrs, _prof_rail(0.034, 0.034),
                 M['frame'], col, closed=True, bw=0.0018)
    return kit.join([ring, lip], "canopy_coaming")


# ====================================================================== 2. 座舱内部（并列双座）
def _seat(nm, xc, yc, zf, M, col, w=0.40):
    """弹射座椅：滑轨 / 分块坐垫 / 后倾靠背(带 Y 向内凹) / 头枕 / 侧向支撑 / 五点安全带"""
    ang = R(-17.0)
    o = []
    # 滑轨 + 座盆
    for i, y in ((0, -w * 0.40), (1, w * 0.40)):
        o.append(kit.box(nm + "_rail%d" % i, (0.44, 0.042, 0.028),
                         loc=(xc, yc + y, zf + 0.014), mat=M['frame'], col=col,
                         bw=0.002, seg=1))
    o.append(kit.box(nm + "_pan", (0.40, w, 0.070), loc=(xc, yc, zf + 0.055),
                     mat=M['gunmetal'], col=col, bw=0.004, seg=2))
    # 坐垫：分两块（大腿垫 + 膝前垫），中间留缝
    o.append(kit.box(nm + "_cush1", (0.24, w - 0.02, 0.070), loc=(xc + 0.055, yc, zf + 0.125),
                     mat=M['interior'], col=col, bw=0.008, seg=2))
    o.append(kit.box(nm + "_cush2", (0.10, w - 0.04, 0.055), loc=(xc - 0.095, yc, zf + 0.120),
                     mat=M['interior'], col=col, bw=0.008, seg=2))
    # 靠背：侧视剖面从坐垫后缘向上后倾，沿 Y 挤出；再叠两块侧支撑做内凹
    prof_xz = [(xc - 0.075, zf + 0.135), (xc - 0.030, zf + 0.245),
               (xc - 0.055, zf + 0.300), (xc - 0.115, zf + 0.300),
               (xc - 0.150, zf + 0.150), (xc - 0.115, zf + 0.120)]
    back = kit.prism(nm + "_back", prof_xz, yc - w * 0.42, yc + w * 0.42,
                     mat=M['interior'], col=col)
    kit.finish(back, 0.008, 2, 46.0)
    o.append(back)
    for i, y in ((0, -1.0), (1, 1.0)):
        bo = kit.box(nm + "_bol%d" % i, (0.085, 0.052, 0.235),
                     loc=(xc - 0.070, yc + y * (w * 0.40), zf + 0.215),
                     rot=(0, R(-14), y * R(6)), mat=M['interior'], col=col,
                     bw=0.006, seg=2)
        o.append(bo)
    # 头枕
    o.append(kit.box(nm + "_head", (0.085, 0.20, 0.095),
                     loc=(xc - 0.135, yc, zf + 0.355), rot=(0, R(-14), 0),
                     mat=M['interior'], col=col, bw=0.008, seg=2))
    # 五点式安全带：两条肩带 + 两条腰带 + 中央锁扣
    for i, y in ((0, -0.062), (1, 0.062)):
        o.append(kit.box(nm + "_sh%d" % i, (0.022, 0.030, 0.235),
                         loc=(xc - 0.045, yc + y, zf + 0.250), rot=(0, R(-16), 0),
                         mat=M['decal_dark'], col=col, bw=0.0018, seg=1))
    for i, y in ((0, -0.135), (1, 0.135)):
        o.append(kit.box(nm + "_lp%d" % i, (0.150, 0.028, 0.020),
                         loc=(xc + 0.010, yc + y, zf + 0.160), rot=(R(0), 0, 0),
                         mat=M['decal_dark'], col=col, bw=0.0018, seg=1))
    o.append(kit.box(nm + "_buckle", (0.055, 0.060, 0.026),
                     loc=(xc - 0.030, yc, zf + 0.176), mat=M['frame'], col=col,
                     bw=0.002, seg=1))
    return kit.join(o, nm)


def build_cockpit(M, col):
    out = []
    G = "canopy"
    X0 = CAN_FRONT - 0.06
    X1 = CAN_REAR + 0.04

    # ---- 地板（贴着甲板的承力地板）
    def _floor_pfn(u, v):
        lim = max(0.12, can_hw(u) - 0.045)
        return (Vector((u, v * lim, hull.deck_z(u) + 0.012)), Vector((0, 0, 1)))

    floor = _patch("cockpit_floor", _floor_pfn, X1, X0, -1.0, 1.0, 16, 8, 0.014,
                   M['interior'], col, bw=0.002)

    # ---- 内衬：舱盖内侧覆板（顺曲面走，向内偏 44mm）
    liner_out = -0.044
    wal_p = _patch("cockpit_liner_p", _can_pfn(), X_BOW, CAN_REAR + 0.03,
                   0.62, 1.0, 12, 4, 0.012, M['interior'], col, out=liner_out, bw=0.0014)
    wal_s = _patch("cockpit_liner_s", _can_pfn(), X_BOW, CAN_REAR + 0.03,
                   -1.0, -0.62, 12, 4, 0.012, M['interior'], col, out=liner_out, bw=0.0014)

    # ---- 后隔框（舱盖后壁 / 座椅后方的结构墙）
    n = 20
    prof_yz = []
    for i in range(n + 1):
        p = can_pt(CAN_REAR + 0.02, _lerp(-0.985, 0.985, i / n))
        prof_yz.append((p.y * 0.99, p.z))
    prof_yz.append((can_pt(CAN_REAR + 0.02, 0.35).y * 0.99, hull.deck_z(CAN_REAR) + 0.02))
    prof_yz.append((can_pt(CAN_REAR + 0.02, -0.35).y * 0.99, hull.deck_z(CAN_REAR) + 0.02))
    bulk = kit.prism_zy("cockpit_bulkhead", prof_yz, CAN_REAR + 0.005, CAN_REAR + 0.06,
                        mat=M['interior'], col=col)
    kit.finish(bulk, 0.003, 2, 40.0)

    # ---- 前仪表台（斜面，贴风挡内侧）+ 仪表板 + 2 MFD + 开关阵
    zx = CAN_FRONT - 0.26
    z_top = hull.deck_z(zx) + 0.165
    prof_xz = [(zx, hull.deck_z(zx) + 0.012), (zx, z_top),
               (zx - 0.30, z_top - 0.030), (zx - 0.62, hull.deck_z(zx - 0.62) + 0.150),
               (zx - 0.62, hull.deck_z(zx - 0.62) + 0.012)]
    console = kit.prism("cockpit_console", prof_xz, -0.30, 0.30, mat=M['interior'], col=col,
                        bw=0.004)
    panel = kit.prism("cockpit_panel",
                      [(zx - 0.03, z_top - 0.050), (zx - 0.03, z_top - 0.012),
                       (zx - 0.34, z_top - 0.078), (zx - 0.34, z_top - 0.114)],
                      -0.28, 0.28, mat=M['black'], col=col, bw=0.002)
    dash_parts = []
    for s in (-1, 1):
        dash_parts.append(kit.box("mfd_%d" % s, (0.012, 0.20, 0.150),
                                  loc=(zx - 0.15, s * 0.135, z_top - 0.058),
                                  rot=(0, R(-16), 0), mat=M['mfd'], col=col,
                                  bw=0.002, seg=1))
        dash_parts.append(kit.box("mfd_bezel_%d" % s, (0.016, 0.226, 0.178),
                                  loc=(zx - 0.146, s * 0.135, z_top - 0.058),
                                  rot=(0, R(-16), 0), mat=M['black'], col=col,
                                  bw=0.002, seg=1))
    for i in range(7):
        y = -0.072 + i * 0.024
        dash_parts.append(kit.box("sw_%d" % i, (0.010, 0.024, 0.020),
                                  loc=(zx - 0.13, y, z_top - 0.034), rot=(0, R(-34), 0),
                                  mat=M['frame'] if i % 2 == 0 else M['gunmetal'], col=col,
                                  bw=0.0015, seg=1))
    dash = kit.join(dash_parts, "cockpit_dash_units")

    # ---- 侧操纵台（左右长条，兼扶手与开关板）
    sides = []
    for s in (-1, 1):
        y0, y1 = s * 0.552, s * 0.660
        prof_zy = [(y0, hull.deck_z(7.6) + 0.012), (y0, hull.deck_z(7.6) + 0.175),
                   (s * 0.638, hull.deck_z(7.6) + 0.190), (y1, hull.deck_z(7.6) + 0.150),
                   (y1, hull.deck_z(7.6) + 0.012)]
        ob = kit.prism_zy("console_side_%d" % s, prof_zy, CAN_REAR + 0.12, 7.62,
                          mat=M['interior'], col=col)
        kit.finish(ob, 0.004, 2, 40.0)
        sides.append(ob)

    # ---- 并列双座（驾驶员在左 y=+0.325，武器系统官在右 y=-0.325）
    z_s = hull.deck_z(7.95) + 0.018
    seat_p = _seat("seat_pilot", 7.95, 0.325, z_s, M, col)
    seat_s = _seat("seat_wso", 7.95, -0.325, z_s, M, col)

    # ---- HUD：贴着前风挡内侧，与风挡平行（法线 = 风挡法线）
    huds = []
    wh = can_pt(X_BOW, 0.0) - can_pt(CAN_FRONT, 0.0)
    ws_norm = Vector((wh.z, 0.0, -wh.x)).normalized() if wh.length > 1e-6 else Vector((0, 0, 1))
    if ws_norm.z < 0:
        ws_norm = -ws_norm
    tilt = math.atan2(ws_norm.x, ws_norm.z)
    for k, y in enumerate((0.325, -0.325)):
        hz = hull.deck_z(8.42) + 0.250
        g = kit.box("hud_glass_%d" % k, (0.006, 0.32, 0.155),
                    loc=(8.42, y, hz), rot=(0, tilt, 0),
                    mat=M['hud'], col=col, bw=0.0012, seg=1)
        f = kit.box("hud_frame_%d" % k, (0.022, 0.35, 0.013),
                    loc=(8.40, y, hz - 0.086), rot=(0, tilt, 0),
                    mat=M['black'], col=col, bw=0.0015, seg=1)
        pr = kit.box("hud_proj_%d" % k, (0.065, 0.09, 0.048),
                     loc=(8.80, y, hull.deck_z(8.80) + 0.16), rot=(0, R(-8), 0),
                     mat=M['gunmetal'], col=col, bw=0.003, seg=2)
        huds.append(kit.join([g, f, pr], "hud_%d" % k))

    # ---- 侧杆 + 油门
    sticks = []
    for k, (sx, y) in enumerate(((8.05, 0.325), (8.05, -0.325))):
        base = kit.box("stick_base_%d" % k, (0.085, 0.085, 0.040),
                       loc=(sx, y, z_s + 0.035), mat=M['frame'], col=col,
                       bw=0.002, seg=1)
        shaft = kit.cyl("stick_shaft_%d" % k, 0.017, 0.20, axis='Z',
                        loc=(sx - 0.012, y, z_s + 0.140), rot=(R(-8), 0, 0),
                        mat=M['gunmetal'], col=col, seg=10, bw=0.0014, segs=1)
        grip = kit.cyl("stick_grip_%d" % k, 0.028, 0.088, axis='Z',
                       loc=(sx - 0.028, y, z_s + 0.248), rot=(R(-12), 0, 0),
                       mat=M['rubber'], col=col, seg=10, bw=0.004, segs=2)
        trig = kit.box("stick_trig_%d" % k, (0.040, 0.010, 0.016),
                       loc=(sx - 0.048, y + 0.022, z_s + 0.242), mat=M['frame'], col=col,
                       bw=0.001, seg=1)
        sticks.append(kit.join([base, shaft, grip, trig], "stick_%d" % k))
    thr = kit.box("throttle", (0.085, 0.042, 0.046), loc=(8.30, 0.500, z_s + 0.150),
                  rot=(R(-24), 0, 0), mat=M['rubber'], col=col, bw=0.006, seg=2)
    thr_base = kit.box("throttle_base", (0.115, 0.055, 0.026),
                       loc=(8.30, 0.500, z_s + 0.105), mat=M['frame'], col=col,
                       bw=0.002, seg=1)
    throttle = kit.join([thr, thr_base], "throttle")

    out += [
        kit.part(floor, "fore_cockpit_floor", "座舱地板", "Cockpit Floor", G, (0, 0, 1),
                 note="贴合甲板弧度的承力地板，比甲板高 12mm"),
        kit.part(wal_p, "fore_cockpit_liner_p", "座舱内衬·右", "Cockpit Liner Stbd", G,
                 (0, 0.6, 0.9), note="舱盖内侧覆板，与玻璃同一曲面域采样，缝对得齐"),
        kit.part(wal_s, "fore_cockpit_liner_s", "座舱内衬·左", "Cockpit Liner Port", G,
                 (0, -0.6, 0.9), note="舱盖内侧覆板，与玻璃同一曲面域采样"),
        kit.part(bulk, "fore_cockpit_bulkhead", "座舱后隔框", "Cockpit Bulkhead", G,
                 (-1, 0, 0.3), note="座椅后方的结构隔框，封住舱盖后壁"),
        kit.part(console, "fore_cockpit_console", "操纵台", "Cockpit Console", G,
                 (0.6, 0, 0.8), note="斜面仪表台，贴风挡内侧托住仪表板与 HUD"),
        kit.part(panel, "fore_cockpit_panel", "仪表板", "Instrument Panel", G,
                 (0.6, 0, 0.85), note="深色仪表面板，嵌两块多功能显示器"),
        kit.part(dash, "fore_cockpit_dash", "显示器与开关阵", "MFD & Switch Cluster", G,
                 (0.7, 0, 0.7), note="两块 MFD + 中央 7 键开关阵（实物件，非贴图）"),
        kit.part(seat_p, "fore_seat_pilot", "驾驶员座椅", "Pilot Ejection Seat", G,
                 (0, 0.15, 1), note="左席：滑轨/分块坐垫/后倾靠背/侧支撑/头枕/五点安全带"),
        kit.part(seat_s, "fore_seat_wso", "武器系统官座椅", "WSO Ejection Seat", G,
                 (0, -0.15, 1), note="右席：同规格弹射座椅，并列布置"),
        kit.part(huds[0], "fore_hud_pilot", "HUD 平显·左", "HUD Combiner Port", G,
                 (0.8, 0.15, 0.6), note="贴风挡内侧、与风挡同倾角的组合镜 + 投影器"),
        kit.part(huds[1], "fore_hud_wso", "HUD 平显·右", "HUD Combiner Stbd", G,
                 (0.8, -0.15, 0.6), note="右席同规格 HUD 组合镜 + 投影器"),
        kit.part(sides[0], "fore_console_side_s", "侧操纵台·左", "Port Side Console", G,
                 (0, 0.8, 0.4), note="舷内侧长条操纵台，兼扶手与开关板"),
        kit.part(sides[1], "fore_console_side_p", "侧操纵台·右", "Stbd Side Console", G,
                 (0, -0.8, 0.4), note="舷内侧长条操纵台，兼扶手与开关板"),
        kit.part(sticks[0], "fore_stick_pilot", "操纵杆·左席", "Control Stick Port", G,
                 (0.2, 0.3, 0.9), note="侧杆 + 握把 + 扳机"),
        kit.part(sticks[1], "fore_stick_wso", "操纵杆·右席", "Control Stick Stbd", G,
                 (0.2, -0.3, 0.9), note="侧杆 + 握把 + 扳机"),
        kit.part(throttle, "fore_throttle", "油门台", "Throttle Quadrant", G,
                 (0.3, 0.5, 0.7), note="左侧油门杆 + 底座"),
    ]
    return out


# ====================================================================== 3. 鼻锥传感器
def build_nose(M, col):
    """鼻锥：雷达罩（与钝端面等径的椭圆穹顶）+ 螺栓圈 + EO/IR 光电球 + 空速管 + 星敏感器 + 光学窗口"""
    out = []
    G = "detail"
    NX = S.NOSE_X                       # 15.0 = 钝鼻端面
    CZ = 0.015                          # 端面中心（正对 ht=0.34 / hb=0.30 的椭圆中心）

    # ---- 雷达罩：椭圆穹顶，底圈坐在钝端面上（长半径 0.395 ≈ 端面半宽 0.42）
    RY, RZ = 0.395, 0.300
    H_D = 0.155
    NS, NR = 32, 8
    bm = bmesh.new()
    rings = []
    for i in range(NR + 1):
        t = i / NR
        k = math.cos(t * math.pi / 2) ** 0.62
        x = NX - 0.004 + H_D * math.sin(t * math.pi / 2)
        if k < 1e-3:
            rings.append([bm.verts.new((x, 0.0, CZ))])
        else:
            rings.append([bm.verts.new((x, RY * k * math.cos(TAU * j / NS),
                                        CZ + RZ * k * math.sin(TAU * j / NS)))
                          for j in range(NS)])
    for a, b in zip(rings[:-1], rings[1:]):
        if len(b) == 1:
            for k in range(NS):
                bm.faces.new((a[k], a[(k + 1) % NS], b[0]))
        else:
            for k in range(NS):
                bm.faces.new((a[k], a[(k + 1) % NS], b[(k + 1) % NS], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    radome = kit.obj_from_bm("nose_radome", bm, M['ceramic'], col, smooth=True)
    kit.finish(radome, 0.0035, 2, 38.0)

    # ---- 罩根加强环（切向环）+ 一圈埋头螺栓（沿端面椭圆排布，不会跑出端面轮廓）
    collar = kit.cyl("nose_collar", 0.024, 0.030, axis='X',
                     loc=(NX - 0.018, 0.0, CZ), mat=M['frame'], col=col,
                     seg=36, bw=0.0016, segs=2)
    collar.scale = (1.0, (RY + 0.020) / 0.024, (RZ + 0.020) / 0.024)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=36,
                          radius1=1.0, radius2=1.0, depth=1.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    ring_ob = kit.obj_from_bm("nose_collar_ring", bm, M['frame'], col, smooth=True)
    ring_ob.scale = (0.030, RY + 0.020, RZ + 0.020)
    ring_ob.location = (NX - 0.018, 0.0, CZ)
    kit.finish(ring_ob, 0.0016, 1)

    bolts = []
    NB = 18
    for i in range(NB):
        a = TAU * i / NB
        by = (RY + 0.012) * math.cos(a)
        bz = CZ + (RZ + 0.012) * math.sin(a)
        bolts.append(kit.cyl("nbolt_%d" % i, 0.013, 0.016, axis='X',
                             loc=(NX - 0.012, by, bz), mat=M['alu'], col=col,
                             seg=6, bw=0.0018, segs=1))
    bolt_ring = kit.join(bolts, "nose_bolts")

    # ---- EO/IR 光电球（颏部转塔：整流包 + 万向球 + 镀膜镜头）
    EX, EY, EZ = 14.63, 0.0, -0.310
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 0.150, v.co.y * 0.168, v.co.z * 0.128))
    fair = kit.obj_from_bm("nose_eo_fairing", bm, M['hull_dark'], col, smooth=True)
    fair.location = (EX, EY, EZ + 0.014)
    kit.finish(fair, 0.0035, 2, 40.0)

    EB = 0.106
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=26, v_segments=16, radius=EB)
    sphere = kit.obj_from_bm("nose_eo_ball", bm, M['gunmetal'], col, smooth=True)
    sphere.location = (EX, EY, EZ - 0.030)
    kit.finish(sphere, 0.0026, 2, 36.0)
    lens = kit.cyl("nose_eo_lens", EB * 0.62, 0.026, axis='X',
                   loc=(EX + EB * 0.78, EY, EZ - 0.030),
                   mat=M['lens'], col=col, seg=18, bw=0.0020, segs=2)
    lring = kit.tube("nose_eo_lensring", EB * 0.74, EB * 0.58, 0.024, axis='X',
                     loc=(EX + EB * 0.72, EY, EZ - 0.030),
                     mat=M['black'], col=col, seg=18, bw=0.0014)
    eo_ball = kit.join([sphere, lens, lring], "nose_eo_ball")

    # ---- 空速管 ×2（根部埋进壳面，杆体前伸，尖端 x=14.94 不越过鼻端）
    pitots = []
    for s in (-1, 1):
        py, pz = s * 0.545, -0.030
        base = kit.cyl("pitot_base_%d" % s, 0.048, 0.085, axis='X',
                       loc=(14.37, py * 0.93, pz), mat=M['frame'], col=col,
                       seg=12, bw=0.0024, segs=2)
        shaft = kit.cyl("pitot_shaft_%d" % s, 0.014, 0.50, axis='X',
                        loc=(14.615, py, pz), mat=M['alu'], col=col, seg=10,
                        bw=0.0011, segs=1)
        tip = kit.cyl("pitot_tip_%d" % s, 0.014, 0.060, axis='X', r2=0.0035,
                      loc=(14.905, py, pz), mat=M['black'], col=col, seg=10,
                      bw=0.0009, segs=1)
        vane = kit.box("pitot_vane_%d" % s, (0.055, 0.008, 0.070),
                       loc=(14.70, py, pz - 0.045), mat=M['alu'], col=col,
                       bw=0.0012, seg=1)
        pitots.append(kit.join([base, shaft, tip, vane],
                               "nose_pitot_%s" % ("p" if s > 0 else "s")))

    # ---- 星敏感器 ×2（坐鼻锥上表面，遮光筒轴线斜前上）
    tracker = []
    for s in (-1, 1):
        tx = 14.15
        th = 1.30 if s > 0 else (math.pi - 1.30)
        p = hull.surf(tx, th, 0.004)
        nrm = surf_normal(tx, th)
        aim = (nrm * 0.70 + Vector((0.70, 0.0, 0.12))).normalized()
        hous = kit.cyl("star_h_%d" % s, 0.058, 0.050, axis='Z', mat=M['gunmetal'],
                       col=col, seg=14, bw=0.0020, segs=2)
        hous.matrix_world = _m(aim, p + aim * 0.024)
        baff = kit.tube("star_b_%d" % s, 0.050, 0.034, 0.080, axis='X',
                        mat=M['black'], col=col, seg=14, bw=0.0013)
        baff.matrix_world = _m(aim, p + aim * 0.092)
        face = kit.cyl("star_f_%d" % s, 0.034, 0.010, axis='X', mat=M['lens'],
                       col=col, seg=14, bw=0.0010, segs=1)
        face.matrix_world = _m(aim, p + aim * 0.052)
        tracker.append(kit.join([hous, baff, face],
                                "nose_star_%s" % ("p" if s > 0 else "s")))

    # ---- 侧向光学窗口（嵌在壳面的凹框 + 镀膜玻璃）
    wins = []
    for s in (-1, 1):
        wx = 13.35
        th = 0.86 if s > 0 else (math.pi - 0.86)
        p = hull.surf(wx, th, 0.006)
        nrm = surf_normal(wx, th)
        frm = kit.box("win_f_%d" % s, (0.20, 0.14, 0.024), mat=M['black'], col=col,
                      bw=0.0030, seg=2)
        frm.matrix_world = _m(nrm, p + nrm * 0.006)
        pane = kit.box("win_g_%d" % s, (0.165, 0.108, 0.014), mat=M['lens'], col=col,
                       bw=0.0016, seg=1)
        pane.matrix_world = _m(nrm, p + nrm * 0.020)
        wins.append(kit.join([frm, pane], "nose_window_%s" % ("p" if s > 0 else "s")))

    # 罩体经向肋条 + 顶端帽：让深色陶瓷罩体在光下有结构可读（否则渲染成一块黑洞）
    ribs = []
    for i in range(6):
        a = TAU * i / 6.0 + 0.26
        pts, nrs = [], []
        for k in range(7):
            t = 0.10 + 0.86 * k / 6.0
            ang = t * math.pi / 2
            kk = math.cos(ang) ** 0.62
            x = NX - 0.004 + H_D * math.sin(ang)
            ry, rz = RY * kk, RZ * kk
            pts.append(Vector((x + 0.004, ry * math.cos(a), CZ + rz * math.sin(a))))
            nrm = Vector((-0.35, math.cos(a), math.sin(a) * (RZ / RY))).normalized()
            nrs.append(nrm)
        ribs.append(_sweep("radome_rib_%d" % i, pts, nrs,
                           _prof_rail(0.026, 0.014), M['frame'], col))
    tip_cap = kit.cyl("radome_cap", 0.052, 0.030, axis='Z', r2=0.030,
                      loc=(NX + H_D * 0.96, 0.0, CZ), mat=M['gunmetal'], col=col,
                      seg=14, bw=0.0020, segs=2)
    tip_cap.matrix_world = _mx(Vector((1.0, 0.0, 0.0)), Vector((NX + H_D * 0.92, 0.0, CZ)))
    ribs = kit.join(ribs + [tip_cap], "nose_radome_ribs")

    out += [
        kit.part(radome, "fore_nose_radome", "雷达罩", "Radar Dome", G, (1, 0, 0.15),
                 note="椭圆穹顶（0.395×0.300，与钝端面等径），底圈坐在 x=15 端面上，前凸 155mm"),
        kit.part(collar, "fore_nose_radome_collar", "雷达罩安装环", "Radome Collar", G,
                 (1, 0, 0.12), note="罩根加强环，压住罩体与端面的接缝"),
        kit.part(bolt_ring, "fore_nose_radome_bolts", "雷达罩螺栓圈", "Radome Bolt Ring", G,
                 (1, 0, 0.15), note="沿端面椭圆均布 18 颗埋头螺栓"),
        kit.part(ribs, "fore_nose_radome_ribs", "雷达罩肋条", "Radome Ribs & Cap", G,
                 (1, 0, 0.2), note="6 条经向肋 + 顶端帽，给深色陶瓷罩体结构可读性"),
        kit.part(fair, "fore_nose_eo_fairing", "光电转塔整流包", "EO/IR Turret Fairing", G,
                 (0.6, 0, -0.8), note="颏部整流包，包住球体与壳面的交线"),
        kit.part(eo_ball, "fore_nose_eo_ball", "EO/IR 光电球", "EO/IR Sensor Ball", G,
                 (1, 0, -0.5), note="万向球 + 镀膜镜头 + 镜头环，从整流包下前方探出"),
        kit.part(pitots[0], "fore_nose_pitot_s", "空速管·左", "Pitot Tube Port", G,
                 (1, -0.3, 0), note="根部埋入壳面、杆体前伸，尖端 x=14.94 不越过鼻端"),
        kit.part(pitots[1], "fore_nose_pitot_p", "空速管·右", "Pitot Tube Stbd", G,
                 (1, 0.3, 0), note="根部埋入壳面、杆体前伸，尖端 x=14.94 不越过鼻端"),
        kit.part(tracker[0], "fore_nose_startracker_s", "星敏感器·左", "Star Tracker Port", G,
                 (0.8, -0.2, 0.6), note="遮光筒 + 镜面 + 座，轴线朝斜前上"),
        kit.part(tracker[1], "fore_nose_startracker_p", "星敏感器·右", "Star Tracker Stbd", G,
                 (0.8, 0.2, 0.6), note="遮光筒 + 镜面 + 座，轴线朝斜前上"),
        kit.part(wins[0], "fore_nose_window_s", "光学窗口·左", "Optical Window Port", G,
                 (0.2, -0.9, 0.2), note="侧向光电窗口：黑框 + 镀膜玻璃，嵌在壳面"),
        kit.part(wins[1], "fore_nose_window_p", "光学窗口·右", "Optical Window Stbd", G,
                 (0.2, 0.9, 0.2), note="侧向光电窗口：黑框 + 镀膜玻璃，嵌在壳面"),
    ]
    return out


# ====================================================================== 4. 前段装甲板
ARMOR_R1 = [(13.95, 11.60), (11.60, 8.70), (8.70, 3.65)]          # 肩部带 th 0.60→0.88
ARMOR_R2 = [(14.25, 12.35), (10.65, 8.60), (8.60, 3.70)]          # 舷线带 th -0.15→0.15
ARMOR_R3 = [(13.60, 11.20), (11.20, 7.90)]                        # 下舷带 th -0.66→-0.38


def _armor_plate(nm, x0, x1, t0, t1, mat, col, gap=0.006, out=0.014, thick=0.011,
                 nx=8, nt=6):
    a, b, c, d = _inset(x0, x1, t0, t1, gap)
    return hull.plate(nm, a, b, c, d, out=out, thick=thick, nx=nx, nt=nt,
                      mat=mat, col=col, shrink=0.0, bw=0.0026)


def build_armor(M, col):
    out = []
    G = "hull_fore"
    plate_count = 0

    for s in (1, -1):
        sgn = "p" if s > 0 else "s"
        # 肩部带（主涂装）
        obs = []
        for i, (x0, x1) in enumerate(ARMOR_R1):
            obs.append(_armor_plate("ar1_%s_%d" % (sgn, i), x0, x1, s * 0.66, s * 0.90,
                                    M['hull'], col, gap=0.007))
            plate_count += 1
        ob = kit.join(obs, "armor_shoulder_%s" % sgn)
        out.append(kit.part(ob, "fore_armor_shoulder_" + sgn,
                            "肩部装甲板带" + ("·右" if s > 0 else "·左"),
                            "Shoulder Armor Belt " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 0.55, 0.85),
                            note="3 块顺舷线走的曲面装甲（hull.plate），板缝 7mm，与前排交错"))

        # 舷线带（次色深灰蓝）
        obs = []
        for i, (x0, x1) in enumerate(ARMOR_R2):
            obs.append(_armor_plate("ar2_%s_%d" % (sgn, i), x0, x1, s * 0.15, s * -0.15,
                                    M['hull_dark'], col, gap=0.006, nt=7))
            plate_count += 1
        ob = kit.join(obs, "armor_chine_%s" % sgn)
        out.append(kit.part(ob, "fore_armor_chine_" + sgn,
                            "舷线装甲带" + ("·右" if s > 0 else "·左"),
                            "Chine Armor Belt " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 1.0, 0.15),
                            note="跨硬舷线的深色装甲带，缝落在舷线上，是这级舰的识别特征"))

        # 下舷带
        obs = []
        for i, (x0, x1) in enumerate(ARMOR_R3):
            obs.append(_armor_plate("ar3_%s_%d" % (sgn, i), x0, x1, s * -0.38, s * -0.66,
                                    M['hull'], col, gap=0.008))
            plate_count += 1
        ob = kit.join(obs, "armor_lower_%s" % sgn)
        out.append(kit.part(ob, "fore_armor_lower_" + sgn,
                            "下舷装甲带" + ("·右" if s > 0 else "·左"),
                            "Lower Armor Belt " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 0.6, -0.8),
                            note="下舷 2 块大尺寸曲板，与舷线带缝位错开"))

        # 警示装甲块（红橙）
        acc = _armor_plate("accent_%s" % sgn, 13.55, 12.85, s * 0.62, s * 0.84,
                           M['accent'], col, gap=0.008, out=0.020, nx=5, nt=4)
        out.append(kit.part(acc, "fore_armor_accent_" + sgn,
                            "警示装甲块" + ("·右" if s > 0 else "·左"),
                            "Warning Armor Panel " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 0.5, 0.8), note="鼻锥后方的红橙警示块，高出常规板 6mm"))

        # ---- 检修盖板（板 + 铰链 + 手柄 + 一圈螺栓）
        hx0, hx1 = 9.95, 8.95
        ht0, ht1 = s * 0.30, s * 0.52
        a, b, c, d = _inset(hx0, hx1, ht0, ht1, 0.010)
        cov = hull.plate("hatch_%s" % sgn, a, b, c, d, out=0.026, thick=0.024,
                         nx=7, nt=5, mat=M['hull_dark'], col=col, bw=0.0030)
        parts = [cov]
        # 铰链（后缘两只）
        for k, (fx, ft) in enumerate(((hx1 + 0.02, s * 0.36), (hx1 + 0.02, s * 0.46))):
            p = hull.surf(fx, ft, 0.030)
            nrm = surf_normal(fx, ft)
            h = kit.box("ht_hinge_%s_%d" % (sgn, k), (0.070, 0.028, 0.030),
                        mat=M['frame'], col=col, bw=0.002, seg=1)
            h.matrix_world = _m(nrm, p + nrm * 0.014)
            parts.append(h)
        # 手柄（前缘中央）
        hp = hull.surf(hx0 - 0.02, s * 0.41, 0.030)
        hn = surf_normal(hx0 - 0.02, s * 0.41)
        handle = kit.box("ht_handle_%s" % sgn, (0.075, 0.032, 0.026), mat=M['alu'],
                         col=col, bw=0.002, seg=1)
        handle.matrix_world = _m(hn, hp + hn * 0.012)
        parts.append(handle)
        # 一圈螺栓（落在盖板外缘的壳面上）
        nb = 10
        for k in range(nb):
            t = k / float(nb)
            if t < 0.25:
                u = _lerp(a - 0.014, b + 0.014, t / 0.25)
                bx, bt = u, c - 0.020
            elif t < 0.5:
                u = _lerp(c - 0.020, d + 0.020, (t - 0.25) / 0.25)
                bx, bt = b + 0.018, u
            elif t < 0.75:
                u = _lerp(b + 0.014, a - 0.014, (t - 0.5) / 0.25)
                bx, bt = u, d + 0.020
            else:
                u = _lerp(d + 0.020, c - 0.020, (t - 0.75) / 0.25)
                bx, bt = a - 0.018, u
            parts.append(_bolt("ht_bolt_%s_%d" % (sgn, k), bx, bt, r=0.013, h=0.011,
                               mat=M['alu'], col=col, off=0.020))
        hb = kit.join(parts, "hatch_%s" % sgn)
        out.append(kit.part(hb, "fore_hatch_" + sgn,
                            "检修盖板" + ("·右" if s > 0 else "·左"),
                            "Access Hatch " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 0.9, 0.35),
                            note="曲面板 + 2 只铰链 + 手柄 + 10 颗螺栓，带 10mm 出檐"))

    # 装甲板数量写进场景属性，便于总装验收
    bpy.context.scene["fore_armor_plates"] = plate_count
    return out


# ====================================================================== 5. 进气 / 散热口
def build_intakes(M, col):
    out = []
    G = "hull_fore"
    IX0, IX1 = 13.45, 11.95
    IT0, IT1 = 0.28, 0.62
    OUT = 0.112

    for s in (1, -1):
        sgn = "p" if s > 0 else "s"
        t0, t1 = (IT0, IT1) if s > 0 else (-IT1, -IT0)

        # 外罩：前缘贴着壳面、向后渐厚到 100mm 再收薄 —— 楔形进气整流罩（不是一整块厚板）
        pad = _scoop_pad("intake_pad_%s" % sgn, IX0, IX1, t0, t1, M['hull_dark'], col,
                         out_front=0.030, out_mid=OUT, out_rear=0.045, thick=0.075,
                         nx=13, nt=9)
        # 开口（四边各留 0.13 罩缘）
        dx, dtt = 0.13, 0.052
        ox0, ox1 = IX0 - dx, IX1 + dx
        ot0, ot1 = (t0 + dtt, t1 - dtt) if t0 < t1 else (t0 - dtt, t1 + dtt)
        cut = _cutter("cut_%s" % sgn, ox0, ox1, ot0, ot1, -0.12, OUT + 0.30)
        kit.cut(pad, cut)

        # 凹陷底板（比壳面高 12mm 的暗色板，形成"深袋"感）
        def pfn(u, v, _n=surf_normal):
            return (hull.surf(u, v, 0.008), _n(u, v))
        base = _patch("intake_base_%s" % sgn, pfn, ox0, ox1, ot0, ot1, 10, 8, 0.010,
                      M['seam'], col, bw=0.0016)

        # 内部导流叶片（垂直于气流方向，等距 5 片）
        vanes = []
        nvan = 5
        for k in range(nvan):
            u = _lerp(ox0 + 0.10, ox1 - 0.10, k / float(nvan - 1))
            vn = _cutter("vane_%s_%d" % (sgn, k), u - 0.010, u + 0.010,
                         ot0 + 0.004, ot1 - 0.004, 0.014, OUT * 0.86)
            vanes.append(vn)
        # _cutter 造的是实体，材质后赋
        for v in vanes:
            if not v.data.materials:
                v.data.materials.append(M['alu'])

        # 唇口框（沿开口四边扫掠的加强框，全部贴着罩面）
        lip_prof = _prof_rail(0.062, 0.030)
        lips = []
        m = 10
        def lip_edge(nm, pts_xt):
            pts, nrs = [], []
            for (x, t) in pts_xt:
                pts.append(hull.surf(x, t, OUT + 0.001))
                nrs.append(surf_normal(x, t))
            return _sweep(nm, pts, nrs, lip_prof, M['black'], col)
        lips.append(lip_edge("lip_f_%s" % sgn, [(ox1, _lerp(ot0, ot1, i / m)) for i in range(m + 1)]))
        lips.append(lip_edge("lip_a_%s" % sgn, [(ox0, _lerp(ot1, ot0, i / m)) for i in range(m + 1)]))
        lips.append(lip_edge("lip_lo_%s" % sgn, [(_lerp(ox0, ox1, i / m), ot0) for i in range(m + 1)]))
        lips.append(lip_edge("lip_up_%s" % sgn, [(_lerp(ox1, ox0, i / m), ot1) for i in range(m + 1)]))
        lip = kit.join(lips, "intake_lip_%s" % sgn)

        # 唇口螺栓
        bl = []
        for k in range(6):
            u = _lerp(ox0 + 0.14, ox1 - 0.14, k / 5.0)
            bl.append(_bolt("ilb_%s_%d" % (sgn, k), u, ot1 + (0.05 if ot1 > ot0 else -0.05),
                            r=0.010, h=0.010, mat=M['alu'], col=col, off=OUT))
        bl = kit.join(bl, "intake_lip_bolts_%s" % sgn)

        out += [
            kit.part(pad, "fore_intake_pad_" + sgn,
                     "进气口外罩" + ("·右" if s > 0 else "·左"),
                     "Intake Fairing " + ("Stbd" if s > 0 else "Port"), G,
                     (0.3, s * 0.9, 0.15),
                     note="凸出壳面 112mm 的曲面罩，用 (x,th,offset) 六面体布尔开出真开口"),
            kit.part(base, "fore_intake_base_" + sgn,
                     "进气口内壁底板" + ("·右" if s > 0 else "·左"),
                     "Intake Duct Floor " + ("Stbd" if s > 0 else "Port"), G,
                     (0.3, s * 0.9, 0.1), note="凹陷底板，距罩面 100mm，形成深袋感"),
            kit.part(kit.join(vanes, "intake_vanes_%s" % sgn),
                     "fore_intake_vanes_" + sgn,
                     "进气导流叶片" + ("·右" if s > 0 else "·左"),
                     "Intake Vanes " + ("Stbd" if s > 0 else "Port"), G,
                     (0.4, s * 0.85, 0.1), note="5 片等距导流叶片，垂直气流方向排布"),
            kit.part(lip, "fore_intake_lip_" + sgn,
                     "进气口唇框" + ("·右" if s > 0 else "·左"),
                     "Intake Lip Frame " + ("Stbd" if s > 0 else "Port"), G,
                     (0.3, s * 0.95, 0.1), note="四边扫掠加强框，包住布尔切口毛边"),
            kit.part(bl, "fore_intake_bolts_" + sgn,
                     "进气口框螺栓" + ("·右" if s > 0 else "·左"),
                     "Intake Lip Bolts " + ("Stbd" if s > 0 else "Port"), G,
                     (0.3, s * 0.95, 0.1), note="唇框上沿 6 颗埋头螺栓"),
        ]

        # ---- 散热百叶（下舷，压在装甲带上的凸起散热窗）
        slats = []
        n_s = 7
        vx0, vx1 = 9.55, 8.55
        vt0, vt1 = s * -0.36, s * -0.60
        for k in range(n_s):
            u = _lerp(vt0, vt1, (k + 0.5) / n_s)
            pts, nrs = [], []
            for i in range(9):
                x = _lerp(vx0, vx1, i / 8.0)
                pts.append(hull.surf(x, u, 0.030))
                nrs.append(surf_normal(x, u))
            slats.append(_sweep("cs_%s_%d" % (sgn, k), pts, nrs,
                                _prof_louver(0.052, 0.016, 0.55), M['alu'], col))
        # 百叶外框（前后两道，贴着壳面扫掠）
        frame_pts, frame_nrs = [], []
        for i in range(11):
            u = _lerp(vt0 - 0.03, vt1 + 0.03, i / 10.0)
            frame_pts.append(hull.surf(vx0, u, 0.022))
            frame_nrs.append(surf_normal(vx0, u))
        slats.append(_sweep("cs_fr_a_%s" % sgn, frame_pts, frame_nrs,
                            _prof_rail(0.040, 0.020), M['frame'], col))
        frame_pts, frame_nrs = [], []
        for i in range(11):
            u = _lerp(vt1 + 0.03, vt0 - 0.03, i / 10.0)
            frame_pts.append(hull.surf(vx1, u, 0.022))
            frame_nrs.append(surf_normal(vx1, u))
        slats.append(_sweep("cs_fr_b_%s" % sgn, frame_pts, frame_nrs,
                            _prof_rail(0.040, 0.020), M['frame'], col))
        cool = kit.join(slats, "cool_vent_%s" % sgn)
        out.append(kit.part(cool, "fore_cool_vent_" + sgn,
                            "散热百叶" + ("·右" if s > 0 else "·左"),
                            "Heat Exchanger Louvers " + ("Stbd" if s > 0 else "Port"), G,
                            (0, s * 0.7, -0.7),
                            note="7 片倾斜百叶 + 前后框，骑在下舷装甲带上，向壳外斜排"))

    # ---- 甲板 APU 排气口 ×2（甲板是平面，用 kit.vent_grill 正好贴合）
    dv_parts = []
    for s in (1, -1):
        vx, vy = 5.55, s * 0.60
        dz = hull.deck_z(vx)
        frame = kit.box("deck_vent_frame_%d" % s, (0.52, 0.34, 0.022),
                        loc=(vx, vy, dz + 0.006), mat=M['frame'], col=col,
                        bw=0.002, seg=2)
        gr = kit.vent_grill("deck_vent_%d" % s, 0.44, 0.26, 6, depth=0.028,
                            loc=(vx, vy, dz + 0.017), mat=M['alu'], col=col)
        dv_parts.append(kit.join([frame, gr], "deck_vent_%s" % ("p" if s > 0 else "s")))
    deck_vent = kit.join(dv_parts, "deck_vent_pair")
    out.append(kit.part(deck_vent, "fore_deck_vent", "甲板 APU 排气口（一对）",
                        "APU Deck Vents", G, (0, 0, 1),
                        note="座舱之后的甲板两侧各一组：底板 + 加强框 + 6 片斜百叶"))

    return out


# ====================================================================== 6. RCS + 航行灯
def build_rcs_lights(M, col):
    out = []
    G = "detail"

    # ---- 前段 RCS 姿控喷口（spec.RCS_PORTS 里 x=+10.40 的那一对）
    #      先在"原点 + 轴线=+X"的本地空间里装配（螺栓圈才是真圆的），再整体映射到壳面
    for x, y, z, d, r in S.RCS_PORTS:
        if x < 8.0:
            continue
        s = 1 if y > 0 else -1
        sgn = "p" if s > 0 else "s"
        th = _th_for(x, y, z)
        p = hull.surf(x, th, -0.004)
        nrm = surf_normal(x, th)
        aim = (Vector(d).normalized() * 0.55 + nrm * 0.55).normalized()

        pieces = []
        pieces.append(kit.cyl("rcs_fl_%s" % sgn, r + 0.080, 0.030, axis='X',
                              loc=(0.014, 0, 0), mat=M['frame'], col=col,
                              seg=22, bw=0.0024, segs=2))
        pieces.append(kit.bolt_ring("rcs_bolts_%s" % sgn, 0.016, 0.0, 0.0,
                                    r + 0.048, 10, axis='X', mat=M['alu'], col=col,
                                    br=0.011, bh=0.014))
        pieces.append(kit.tube("rcs_bell_%s" % sgn, r + 0.022, r - 0.002, 0.080,
                               axis='X', loc=(0.062, 0, 0), mat=M['gunmetal'],
                               col=col, seg=22, bw=0.0016))
        pieces.append(kit.cyl("rcs_th_%s" % sgn, r - 0.004, 0.060, axis='X',
                              loc=(0.052, 0, 0), mat=M['heat_steel'], col=col,
                              seg=20, bw=0.0012, segs=1))
        pieces.append(kit.cyl("rcs_cap_%s" % sgn, r - 0.034, 0.014, axis='X',
                              loc=(0.020, 0, 0), mat=M['black'], col=col,
                              seg=16, bw=0.0012, segs=1))
        for k in range(4):
            ang = TAU * k / 4.0 + 0.25
            v = kit.box("rcs_v_%s_%d" % (sgn, k), (0.012, 0.016, (r - 0.006) * 1.8),
                        mat=M['alu'], col=col, bw=0.0012, seg=1)
            v.location = (0.066, math.cos(ang) * (r * 0.52), math.sin(ang) * (r * 0.52))
            v.rotation_euler = (ang + math.pi / 2, 0, 0)
            pieces.append(v)
        rcs = kit.join(pieces, "rcs_%s" % sgn)
        rcs.matrix_world = _mx(aim, p)
        out.append(kit.part(rcs, "fore_rcs_" + sgn,
                            "前段 RCS 喷口" + ("·右" if s > 0 else "·左"),
                            "Fore RCS Thruster " + ("Stbd" if s > 0 else "Port"), G,
                            (0.15, s * 0.9, 0.35),
                            note="按 spec.RCS_PORTS 前向一对定位：法兰 + 10 颗螺栓圈(kit.bolt_ring) + 喷管 + 喉部 + 4 片燃气舵"))

    # ---- 航行灯：左红右绿（+Y = 右舷 → 绿；-Y = 左舷 → 红）
    for s in (1, -1):
        is_stbd = s > 0
        lm = M['led_green'] if is_stbd else M['led_red']
        nm = "nav_%s" % ("p" if is_stbd else "s")
        x = 12.85
        th = s * 0.40
        p = hull.surf(x, th, 0.004)
        nrm = surf_normal(x, th)
        base = kit.cyl(nm + "_base", 0.062, 0.030, axis='Z', mat=M['frame'], col=col,
                       seg=14, bw=0.0020, segs=2)
        base.matrix_world = _m(nrm, p + nrm * 0.012)
        lens = kit.cyl(nm + "_lens", 0.044, 0.026, axis='Z', mat=lm, col=col,
                       seg=14, bw=0.0040, segs=3)
        lens.matrix_world = _m(nrm, p + nrm * 0.036)
        hood = kit.box(nm + "_hood", (0.085, 0.020, 0.055), mat=M['black'], col=col,
                       bw=0.0018, seg=1)
        hood.matrix_world = _m(nrm, p + nrm * 0.030) @ Matrix.Rotation(R(0), 4, 'Z')
        hood.matrix_world = _m(nrm, p + nrm * 0.030 + Vector((0.055, 0, 0)))
        ob = kit.join([base, lens, hood], nm)
        out.append(kit.part(ob, "fore_nav_" + ("p" if is_stbd else "s"),
                            "航行灯·" + ("右舷绿" if is_stbd else "左舷红"),
                            "Nav Light " + ("Stbd Green" if is_stbd else "Port Red"), G,
                            (0, s * 0.95, 0.3),
                            note="左红右绿：透镜 + 座 + 遮光罩，坐在肩部装甲带上"))

    # ---- 防撞灯（背部 + 腹部）
    for nm, z_side, pid, zh, en, mat in (
            ("beacon_top", 1, "fore_beacon_top", "防撞灯·背", "Anti-Collision Beacon Top",
             M['led_red']),
            ("beacon_bot", -1, "fore_beacon_bot", "防撞灯·腹", "Anti-Collision Beacon Belly",
             M['led_amber'])):
        x = 12.55 if z_side > 0 else 9.30
        th = math.pi / 2 if z_side > 0 else -math.pi / 2
        p = hull.surf(x, th, 0.004)
        nrm = surf_normal(x, th)
        base = kit.cyl(nm + "_b", 0.070, 0.026, axis='Z', mat=M['gunmetal'], col=col,
                       seg=16, bw=0.0022, segs=2)
        base.matrix_world = _m(nrm, p + nrm * 0.012)
        dome = kit.cyl(nm + "_d", 0.050, 0.044, axis='Z', r2=0.026, mat=mat, col=col,
                       seg=16, bw=0.0045, segs=3)
        dome.matrix_world = _m(nrm, p + nrm * 0.045)
        ring = kit.tube(nm + "_r", 0.062, 0.050, 0.020, axis='X', mat=M['black'],
                        col=col, seg=16, bw=0.0014)
        ring.matrix_world = _m(nrm, p + nrm * 0.030)
        ob = kit.join([base, dome, ring], nm)
        out.append(kit.part(ob, pid, zh, en, G,
                            (0.2 if z_side > 0 else -0.2, 0, z_side * 0.95),
                            note="防撞频闪灯：座 + 半球罩 + 压环"))

    # ---- 舷号 / 标识（真文字网格，烘进世界变换）
    try:
        tx = 12.60
        th = 0.735
        p = hull.surf(tx, th, 0.020)
        nrm = surf_normal(tx, th)
        t = kit.text_mesh("decal_bow", "07", size=0.30, mat=M['decal'], col=col,
                          extrude=0.0016)
        xa = (Vector((1.0, 0.0, 0.0)) - nrm * nrm.x).normalized()
        ya = nrm.cross(xa).normalized()
        t.matrix_world = kit.mat_from_axes(xa, ya, nrm, tuple(p))
        out.append(kit.part(t, "fore_decal_bow", "舷号 07", "Bow Number 07", G,
                            (0, 0.4, 0.9), note="贴在肩部装甲上的实心文字网格（非贴图）"))
    except Exception as e:
        print("  ! fore decal skipped:", e)
    return out


# ====================================================================== 材质补充
def _extra_mats():
    """本模块专用材质（前缀 S_Fore），不改 lib/mats.py"""
    hud = mats._principled("S_Fore_HUD", (0.10, 0.85, 0.55), 0.0, 0.10,
                           alpha=0.42, transmission=0.5,
                           emission=(0.12, 0.95, 0.55, 3.2), spec=1.0)
    mfd = mats._principled("S_Fore_MFD", (0.02, 0.10, 0.12), 0.0, 0.22,
                           emission=(0.06, 0.42, 0.55, 2.4))
    return hud, mfd


# ====================================================================== 总装
def _tune_canopy_mat(M):
    """让 M['canopy'] 在 EEVEE 里真的读成"玻璃"：
    原值 alpha=0.30 / transmission=0.86 在无光追弱光场景里几乎完全透明，看上去像没装玻璃。
    这里只改运行时数值（不改 lib/mats.py 源文件、不改材质名）。"""
    m = M.get('canopy')
    if not m or not m.use_nodes:
        return
    # DITHERED（随机抖动透明）在弱光下会出颗粒噪点，玻璃读起来像磨砂塑料 → 改成 BLENDED 平滑混合
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    for nd in m.node_tree.nodes:
        if nd.type == 'BSDF_PRINCIPLED':
            for k, v in (('Alpha', 0.30), ('Transmission Weight', 0.0),
                         ('Roughness', 0.06),
                         ('Base Color', (0.024, 0.052, 0.060, 1.0))):
                if k in nd.inputs:
                    try:
                        nd.inputs[k].default_value = v
                    except Exception:
                        pass
            if 'Coat Weight' in nd.inputs:
                nd.inputs['Coat Weight'].default_value = 0.65
            if 'Specular IOR Level' in nd.inputs:
                nd.inputs['Specular IOR Level'].default_value = 0.62


def build(M, col):
    P = []
    hud, mfd = _extra_mats()
    M = dict(M)
    M['hud'] = hud
    M['mfd'] = mfd
    _tune_canopy_mat(M)

    for fn in (build_canopy, build_cockpit, build_nose, build_armor,
               build_intakes, build_rcs_lights):
        try:
            got = fn(M, col) or []
            P += [o for o in got if o is not None]
        except Exception:
            import traceback
            print("!! fore sub-build %s FAILED" % fn.__name__)
            traceback.print_exc()
    print("FOREPARTS %d" % len(P))
    return P
