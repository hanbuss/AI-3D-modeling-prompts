"""starship/lib/mid.py — 中段船体（x ∈ [-9.2, 3.4]）

视觉目标：一眼看出是"人造的承力段"，不是光滑蛋壳贴花纹。
  背脊骨架（主梁 + 每 1.2 m 一道横肋骨）／三条带装甲分块（上舷 / 舷线 / 下舷，交错留缝）／
  左右舷可展开散热辐射板（铰链 + 液压作动筒）／上表面气闸舱门（围板凹陷 + 密封圈 + 手轮 + 观察窗）／
  侧面检修门／机械碎件与电缆／天线与传感器／涂装编号与舷线灯带。

几条不许改坏的（都踩过）：
1) **th 是极角**：hull 的剖面按 y = cos(th)、z = sin(th) 取点，所以
   th ∈ (0, π/2) = 右舷（上）、th < 0 = 右舷（下）、th ≈ π = 左舷。
   左舷 ≡ 右舷角度 a 的镜像 = **π − a**（不是 −a！）。_th() 统一做这件事。
2) 表面采样一律对 `hull.profile_pts()` 做射线求交（_ray/_surf），与 hull.surf 同源同结果；
   船壳段是 profile_pts 逐环放样、站位间线性插值 → 取到的点严格落在真实壳面上，贴片不浮不陷。
3) 装甲板缝落在**硬棱**上：上舷 / 舷线（th≈0 的竖直面）/ 下舷 三条带各自独立取样，
   任何一块板都不跨折角（跨折角的直纹面会切进船壳）。
4) 甲板是精确平面：|y| ≤ 0.52·w 处 z 恒等于 deck_z(x)，背脊/舱门/天线直接摆平面上，
   基座往甲板里沉 4–6 mm，杜绝"浮空 2 mm"。
5) 文字用 kit.text_mesh（世界变换已烘进网格），**逐字**贴各自法线摆 → 长串也不会被曲面吃掉。
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Matrix

import kit
import hull
import mats
import spec as S

TAU = math.tau
PI = math.pi

# ---------------------------------------------------------------- 区间与常量
X_F = 3.28          # 前边界（与 hull_fore 的接缝 3.40 内收 12 cm）
X_A = -9.08         # 后边界（与 hull_aft 的接缝 -9.20 内收 12 cm）
DECK_HALF = 0.52    # profile 里平甲的归一化半宽
GAP = 0.0026        # 板缝（plate 的 shrink 系数 → 实际缝 ≈5 mm）

# 三条带（角度全部按**右舷**书写；左舷由 _th() 镜像）
BAND_UP = (0.050 * PI, 0.262 * PI)     # 上舷：竖直上舷面 → 肩部倒角（到甲板边梁前）
BAND_CH = (-0.036 * PI, 0.038 * PI)    # 舷线：z≈±0.2 的竖直硬棱面
BAND_LO = (-0.215 * PI, -0.040 * PI)   # 下舷：竖直下舷面 → 底部折角前

OUT_ARMOR = 0.014      # 装甲板外表面离壳
TH_ARMOR = 0.010       # 装甲板厚
OUT_TRIM = 0.0175      # 涂装条（贴在装甲面上）
OUT_LED = 0.0205       # 灯带
OUT_TEXT = 0.0215      # 文字（比装甲面高 7.5 mm）


# ================================================================ 角度 / 采样
def _th(a, sgn):
    """把"右舷角度 a"映射到指定舷：左舷 = π − a（y 取负、z 不变）"""
    return a if sgn > 0 else (PI - a)


def _poly(x):
    return hull.profile_pts(x)


def _ray(x, th):
    """从剖面中心沿 th 求交 → (y, z, ny, nz)。硬棱处顶点重复，退化边自动跳过。"""
    poly = _poly(x)
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
        t = (ay * ez - az * ey) / den
        u = (dy * az - dz * ay) / -den
        if t > 0.0 and -1e-9 <= u <= 1.0 + 1e-9:
            if best is None or t < best[0]:
                nl = math.hypot(ey, ez) or 1.0
                ny, nz = ez / nl, -ey / nl
                if ny * dy + nz * dz < 0.0:
                    ny, nz = -ny, -nz
                best = (t, ny, nz)
    if best is None:                              # 兜底（正常不会走到）
        w, ht, hb = hull.sect(x)
        return dy * w, dz * (ht if dz >= 0 else hb), 0.0, (1.0 if dz >= 0 else -1.0)
    t, ny, nz = best
    return dy * t, dz * t, ny, nz


def _surf(x, th, off=0.0):
    y, z, ny, nz = _ray(x, th)
    return Vector((x, y + ny * off, z + nz * off))


def _nrm(x, th):
    _y, _z, ny, nz = _ray(x, th)
    return Vector((0.0, ny, nz))


def _frame(x, th):
    n = _nrm(x, th)
    p0 = _surf(x - 0.05, th)
    p1 = _surf(x + 0.05, th)
    tx = (p1 - p0).normalized()
    tth = n.cross(tx).normalized()
    return n, tx, tth


def _plate(name, x0, x1, th0, th1, out=OUT_ARMOR, thick=TH_ARMOR, nx=6, nt=6,
           mat=None, col=None, shrink=0.0, bw=0.0032):
    """贴合壳面的曲面板（hull.plate 的同构实现，采样走本模块 _surf）"""
    if shrink:
        dx = (x0 - x1) * shrink
        x0 -= dx
        x1 += dx
        dth = (th1 - th0) * shrink
        th0 += dth
        th1 -= dth
    nx, nt = max(2, nx), max(1, nt)
    outer, inner = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * (i / nx)
        ro, ri = [], []
        for j in range(nt + 1):
            th = th0 + (th1 - th0) * (j / nt)
            ro.append(_surf(x, th, out))
            ri.append(_surf(x, th, out - thick))
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
        kit.finish(ob, bw, 1, 42.0)
    return ob


# ================================================================ 通用件
def _boxw(name, center, u, v, w, du, dv, dw, mat=None, col=None, bw=0.0008, seg=1):
    """任意朝向盒件：局部 u/v/w 三轴 + 三向尺寸（负行列式自动翻面，左右舷通用）"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((du, dv, dw)), verts=bm.verts)
    M4 = kit.mat_from_axes(Vector(u), Vector(v), Vector(w), Vector(center))
    if M4.to_3x3().determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.transform(M4)
    ob = kit.obj_from_bm(name, bm, mat, col)
    if bw:
        kit.finish(ob, bw, seg, 40.0)
    return ob


def _cylw(name, center, axis, r, depth, mat=None, col=None, seg=12, bw=0.0006, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=(r if r2 is None else r2), depth=depth)
    q = Vector(axis).normalized().to_track_quat('Z', 'Y')
    bm.transform(q.to_matrix().to_4x4())
    bm.transform(Matrix.Translation(Vector(center)))
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.finish(ob, bw, 1, 36.0)
    return ob


def _dome(name, center, axis, r, h, mat=None, col=None, seg=14):
    """鼓包 / 整流罩（压扁半球）"""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(4, seg // 2), radius=r)
    for v in bm.verts:
        if v.co.z < 0:
            v.co.z *= 0.05
        v.co.z *= h / max(r, 1e-6)
    q = Vector(axis).normalized().to_track_quat('Z', 'Y')
    bm.transform(q.to_matrix().to_4x4())
    bm.transform(Matrix.Translation(Vector(center)))
    return kit.obj_from_bm(name, bm, mat, col, smooth=True)


def _dth_for_arc(x, th0, arc):
    """从 th0 出发，找使表面弧长 ≈ arc 的 th（用来把平直长度换成贴面角度区间）"""
    sgn = 1.0 if arc >= 0 else -1.0
    need = abs(arc)
    tot, th, dt = 0.0, th0, sgn * 0.006
    prev = _surf(x, th0)
    while tot < need - 1e-6 and abs(th - th0) < math.pi:
        th2 = th + dt
        cur = _surf(x, th2)
        tot += (cur - prev).length
        prev, th = cur, th2
    return th


def M_ALU():
    """_rack 内部的铝件材质（延迟取，避免模块级依赖 mats.M 的构造顺序）"""
    return bpy.data.materials.get("S_Alu")


def _deck_pt(x, y, dz=0.0):
    """甲板平面上的点（平甲区 z 恒为 deck_z(x)，无需射线求交）"""
    return Vector((x, y, hull.deck_z(x) + dz))


def _text(name, body, loc, xax, yax, zax, size, mat, col, extrude=0.0005):
    """文字摆到任意平面：局部 +X=阅读方向 / +Y=上 / +Z=法线（外）"""
    xax = Vector(xax).normalized()
    zax = Vector(zax).normalized()
    xax = (xax - zax * xax.dot(zax)).normalized()
    yax = zax.cross(xax).normalized()
    M4 = kit.mat_from_axes(xax, yax, zax)
    return kit.text_mesh(name, body, size=size, loc=tuple(Vector(loc)),
                         rot=tuple(M4.to_euler()), mat=mat, col=col, extrude=extrude)


def _label(name, body, x, a, size, sgn, mat, col, out=OUT_TEXT):
    """舷侧文字：逐字贴各自法线，沿 X 阅读方向、正立"""
    th = _th(a, sgn)
    n, tx, _tth = _frame(x, th)
    read = -tx if sgn > 0 else tx
    up = n.cross(read).normalized()
    m = len(body)
    step = size * 0.76
    obs = []
    for i, ch in enumerate(body):
        if ch == " ":
            continue
        xo = x + (i - (m - 1) / 2.0) * step * (1.0 if read.x >= 0 else -1.0)
        nn, _t1, _t2 = _frame(xo, th)
        obs.append(_text("%s_%d" % (name, i), ch, _surf(xo, th, out), read, up, nn,
                         size, mat, col))
    return kit.join(obs, name) if len(obs) > 1 else obs[0]


def _rack(name, xc, th, L, seed, mat, pad_mat, col, depth=0.20):
    """一排装机件：**贴曲面的**长条底座 + 沿 X 排列的短模块（读作设备架，不是撒石子）

    底座必须用 _plate：0.5–1.0 m 的平板搭在 R≈1.9 m 的壳上会中间凸、两端陷，
    远看就是一道黑色"矛"。模块本身短（≤0.12 m）才可以用平板。
    """
    rnd = random.Random(seed)
    n, tx, tth = _frame(xc, th)
    th_a = _dth_for_arc(xc, th, -depth * 0.5)
    th_b = _dth_for_arc(xc, th, depth * 0.5)
    obs = [_plate("%s_pad" % name, xc + L * 0.5, xc - L * 0.5, th_a, th_b,
                  out=OUT_ARMOR + 0.014, thick=0.013, nx=5, nt=3,
                  mat=pad_mat, col=col, bw=0.0016)]
    x = -L * 0.5 + 0.03
    i = 0
    while x < L * 0.5 - 0.06:
        du = rnd.uniform(0.045, 0.115)
        if x + du > L * 0.5 - 0.02:
            break
        xm = xc - (x + du * 0.5)                 # 沿 -X 排（x 从舰首往舰尾）
        thm = th + rnd.uniform(-0.25, 0.25) * (th_b - th_a)
        nn, txm, tthm = _frame(xm, thm)
        p = _surf(xm, thm, OUT_ARMOR + 0.014 + 0.013)
        dv = depth * rnd.uniform(0.42, 0.72)
        dw = rnd.uniform(0.024, 0.090)
        obs.append(_boxw("%s_b%d" % (name, i), p + nn * (dw * 0.5), txm, tthm, nn,
                         du, dv, dw, mat=mat, col=col, bw=0.0))
        if i % 2 == 1:
            obs.append(_cylw("%s_c%d" % (name, i), p + nn * (dw + 0.012), nn,
                             min(du, dv) * 0.30, 0.024, mat=M_ALU(), col=col, seg=6, bw=0))
        x += du + rnd.uniform(0.010, 0.030)
        i += 1
    return obs


def _greeble_racks(name, x0, x1, th0, th1, racks, seed, mat, pad_mat, col,
                   Lmin=0.42, Lmax=0.92, depth=0.20):
    """一条带上排若干设备架（每架 4–8 件），整体仍随机但成组"""
    rnd = random.Random(seed)
    lo, hi = (th0, th1) if th0 < th1 else (th1, th0)
    obs = []
    for k in range(racks):
        xc = x0 + (x1 - x0) * (k + 0.5) / racks + rnd.uniform(-0.16, 0.16)
        th = rnd.uniform(lo, hi)
        L = rnd.uniform(Lmin, Lmax)
        obs += _rack("%s_k%d" % (name, k), xc, th, L, seed * 131 + k, mat, pad_mat, col,
                     depth=depth)
    return kit.join(obs, name)


# ================================================================ 1. 背脊骨架
def _build_keel(M, col, out):
    x0, x1, yh, h = 3.14, -8.96, 0.150, 0.115
    n = 28
    rings, cap = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        zb = hull.deck_z(x) - 0.006
        zt = hull.deck_z(x) + h
        rings.append((x, [(-yh, zb), (yh, zb), (yh, zt), (-yh, zt)]))
        cap.append((x, [(-0.085, zt - 0.004), (0.085, zt - 0.004),
                        (0.085, zt + 0.022), (-0.085, zt + 0.022)]))
    beam = kit.loft("mid_keel_beam", rings, mat=M['frame'], col=col)
    kit.finish(beam, 0.004, 2, 40.0)
    strip = kit.loft("mid_keel_cap", cap, mat=M['alu'], col=col)
    kit.finish(strip, 0.0025, 2, 40.0)
    keel = kit.join([beam, strip], "mid_dorsal_keel")
    kit.part(keel, "mid_dorsal_keel", "背脊主梁", "Dorsal Spine Beam", "hull_mid",
             (0, 0, 1), order=70,
             note="沿甲板起伏放样的箱形加强梁 300×115 mm，顶面铝盖条；x 3.14→-8.96")
    out.append(keel)

    ribs, k = [], 0
    x = 3.02
    while x >= -8.90:
        ribs.append(_boxw("mid_keel_rib%d" % k, (x, 0, hull.deck_z(x) + 0.055),
                          (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.062, 0.430, 0.190,
                          mat=M['alu'], col=col, bw=0.0032, seg=2))
        k += 1
        x -= 1.2
    ribob = kit.join(ribs, "mid_dorsal_ribs")
    kit.part(ribob, "mid_dorsal_ribs", "背脊肋骨框", "Dorsal Rib Frames", "hull_mid",
             (0, 0, 1), order=71,
             note="%d 道横向肋，间距 1.2 m，厚 62 mm、倒角 R3.2" % k)
    out.append(ribob)

    cros, k = [], 0
    x = 3.02
    while x >= -8.90:
        if not (-3.98 < x < -3.02):                  # 让开气闸舱门
            cros.append(_boxw("mid_cross_rib%d" % k, (x, 0, hull.deck_z(x) + 0.011),
                              (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.078, 1.290, 0.052,
                              mat=M['frame'], col=col, bw=0.0028, seg=1))
            k += 1
        x -= 1.2
    crob = kit.join(cros, "mid_deck_crossribs")
    kit.part(crob, "mid_deck_crossribs", "甲板横梁", "Deck Cross Ribs", "hull_mid",
             (0, 0, 1), order=72, note="%d 根横梁压在甲板上，跨 y±0.645" % k)
    out.append(crob)

    rails = []
    for sgn in (1, -1):
        rr = []
        m = 22
        for i in range(m + 1):
            x = 3.16 + (-8.94 - 3.16) * i / m
            w, _ht, _hb = hull.sect(x)
            y = sgn * (DECK_HALF * w - 0.045)
            dz = hull.deck_z(x)
            rr.append((x, [(y - 0.055, dz - 0.010), (y + 0.055, dz - 0.010),
                           (y + 0.048, dz + 0.042), (y - 0.048, dz + 0.042)]))
        rail = kit.loft("mid_deck_rail%d" % sgn, rr, mat=M['alu'], col=col)
        kit.finish(rail, 0.003, 2, 40.0)
        rails.append(rail)
    railob = kit.join(rails, "mid_deck_rails")
    kit.part(railob, "mid_deck_rails", "甲板边梁", "Deck Edge Rails", "hull_mid",
             (0, 0, 1), order=73, note="左右舷甲板边缘收口梁，随站位宽度走")
    out.append(railob)


def _deck_panel(name, x0, x1, y0, y1, out=0.008, thick=0.009, nx=3, mat=None, col=None):
    """平甲面上的方形铺设板：沿 X 采样贴合甲板微坡，Y 向平直（甲板本来就是平面）"""
    outer, inner = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        z = hull.deck_z(x)
        outer.append([Vector((x, y0, z + out)), Vector((x, y1, z + out))])
        inner.append([Vector((x, y0, z + out - thick)), Vector((x, y1, z + out - thick))])
    bm = bmesh.new()
    vo = [[bm.verts.new(p) for p in row] for row in outer]
    vi = [[bm.verts.new(p) for p in row] for row in inner]
    for i in range(nx):
        bm.faces.new((vo[i][0], vo[i + 1][0], vo[i + 1][1], vo[i][1]))
        bm.faces.new((vi[i][0], vi[i][1], vi[i + 1][1], vi[i + 1][0]))
    bm.faces.new((vo[0][0], vo[0][1], vi[0][1], vi[0][0]))
    bm.faces.new((vo[nx][0], vi[nx][0], vi[nx][1], vo[nx][1]))
    for i in range(nx):
        bm.faces.new((vo[i][0], vi[i][0], vi[i + 1][0], vo[i + 1][0]))
        bm.faces.new((vo[i][1], vo[i + 1][1], vi[i + 1][1], vi[i][1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=False)
    kit.finish(ob, 0.0022, 1, 42.0)
    return ob


def _build_deck_plating(M, col, out, A):
    """甲板铺设板：主梁两侧各 5 块，交错排布，给顶视图"分块"读感"""
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        obs = []
        cyc = [M['hull'], A['mid_armor'], M['hull'], M['hull'], A['mid_armor']]
        for i, (a, b) in enumerate(_spans(3.16, -8.90, 5, 0.42 * sgn)):
            y0 = sgn * 0.185
            y1 = sgn * (0.505 * hull.sect(0.5 * (a + b))[0])
            obs.append(_deck_panel("mid_deckpl_%s_%d" % (tag, i), a, b,
                                   min(y0, y1) + 0.004, max(y0, y1) - 0.004,
                                   out=0.009, thick=0.009,
                                   mat=cyc[i % len(cyc)], col=col))
        ob = kit.join(obs, "mid_deck_plating_" + tag)
        kit.part(ob, "mid_deck_plating_" + tag,
                 "%s舷甲板铺设板" % ("右" if sgn > 0 else "左"),
                 "Deck Plating (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "hull_mid", (0, 0, 1), order=82,
                 note="5 块交错铺设板，主梁与甲板边梁之间，缝 5 mm")
        out.append(ob)


# ================================================================ 2. 装甲分块
def _spans(x0, x1, n, shift=0.0):
    L = (x0 - x1) / n
    out = []
    for i in range(n):
        a = min(x0 - i * L - shift, x0)
        b = max(a - L, x1 - 0.02)
        if a - b > 0.25:
            out.append((a, b))
    return out


def _band(name, x0, x1, a0, a1, n, shift, mats_cycle, col, sgn,
          nx=6, nt=6, thick=TH_ARMOR, deep=OUT_ARMOR, backing=None):
    """一条装甲带（角度按右舷书写，内部镜像到指定舷）+ 板下深色衬底（缝里读作阴影）"""
    obs = []
    if backing:
        # 衬底压在装甲板**底面以下**（0.0045–0.0075；装甲板 4–14 mm），th 两端内缩 ~3 mm，
        # 保证任何视角都不会从板边露出来 → 只在 5 mm 的板缝里读作阴影
        t0, t1 = _th(a0, sgn), _th(a1, sgn)
        sd = 1.0 if t1 > t0 else -1.0
        dth = 0.003 / 1.9
        obs.append(_plate(name + "_back", x0 - 0.004, x1 + 0.004, t0 + sd * dth,
                          t1 - sd * dth, out=0.0075, thick=0.003, nx=5, nt=4,
                          mat=backing, col=col, bw=0.0))
    for i, (a, b) in enumerate(_spans(x0, x1, n, shift)):
        m = mats_cycle[i % len(mats_cycle)]
        obs.append(_plate("%s_%d" % (name, i), a, b, _th(a0, sgn), _th(a1, sgn),
                          out=deep, thick=thick, nx=nx, nt=nt, mat=m, col=col,
                          shrink=GAP))
    return kit.join(obs, name)


def _build_armor(M, col, out, A):
    for sgn in (1, -1):
        sd_zh = "右" if sgn > 0 else "左"
        sd_en = "Stbd" if sgn > 0 else "Port"
        tag = "stbd" if sgn > 0 else "port"

        up_mats = [M['hull'], A['mid_armor'], M['hull'], A['mid_armor'],
                   M['hull'], M['hull_dark'], M['accent']]
        ob = _band("mid_armor_up_" + tag, X_F, X_A, BAND_UP[0], BAND_UP[1], 7, 0.0,
                   up_mats, col, sgn, nx=6, nt=7)
        kit.part(ob, "mid_armor_up_" + tag, "%s舷上舷装甲板" % sd_zh,
                 "Upper Flank Armor (%s)" % sd_en, "hull_mid", (sgn, 0, 0), order=74,
                 note="th %.3fπ–%.3fπ，7 块交错，缝 5 mm，末块红警示" %
                      (BAND_UP[0] / PI, BAND_UP[1] / PI))
        out.append(ob)

        ch_mats = [A['mid_armor'], M['stripe'], A['mid_armor'], M['hull'],
                   A['mid_armor']]
        ob = _band("mid_armor_chine_" + tag, X_F, X_A, BAND_CH[0], BAND_CH[1], 5, 1.15,
                   ch_mats, col, sgn, nx=6, nt=5, deep=OUT_ARMOR + 0.001)
        kit.part(ob, "mid_armor_chine_" + tag, "%s舷舷线装甲带" % sd_zh,
                 "Chine Strake (%s)" % sd_en, "hull_mid", (sgn, 0, 0), order=75,
                 note="骑在硬舷线上（z≈±0.2 的竖直面），中间一块橙黄腰线")
        out.append(ob)

        lo_mats = [A['mid_armor'], M['hull'], A['mid_armor'], M['hull'],
                   M['hull_dark'], M['hull'], A['mid_armor']]
        ob = _band("mid_armor_low_" + tag, X_F, X_A, BAND_LO[0], BAND_LO[1], 7, 0.62,
                   lo_mats, col, sgn, nx=6, nt=7)
        kit.part(ob, "mid_armor_low_" + tag, "%s舷下舷装甲板" % sd_zh,
                 "Lower Flank Armor (%s)" % sd_en, "hull_mid", (sgn, 0, 0), order=76,
                 note="th %.3fπ–%.3fπ，7 块交错" % (BAND_LO[0] / PI, BAND_LO[1] / PI))
        out.append(ob)

        trims = [_plate("mid_stripe_" + tag, 2.55, -6.15,
                        _th(-0.054 * PI, sgn), _th(-0.038 * PI, sgn),
                        out=OUT_TRIM, thick=0.0026, nx=12, nt=2,
                        mat=M['stripe'], col=col)]
        for j, xa in enumerate((1.82, -4.05)):
            trims.append(_plate("mid_warn_%s_%d" % (tag, j), xa, xa - 0.58,
                                _th(0.150 * PI, sgn), _th(0.196 * PI, sgn),
                                out=OUT_TRIM, thick=0.0024, nx=3, nt=4,
                                mat=M['accent'], col=col))
        ob = kit.join(trims, "mid_trim_" + tag)
        kit.part(ob, "mid_trim_" + tag, "%s舷涂装条" % sd_zh,
                 "Livery Trim (%s)" % sd_en, "hull_mid", (sgn, 0, 0), order=77,
                 note="橙黄腰线 1 条（x 2.55→-6.15）+ 红警示条 2 条")
        out.append(ob)


def _build_access_panels(M, col, out, A):
    """舷侧小检修盖板：上舷空区里成排的方形盖板 + 铝压边，专治"大片空壳" """
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        obs = []
        for i, xa in enumerate((2.35, 1.05, -0.45, -1.95, -4.55, -6.05, -7.55)):
            a0 = (0.062 + 0.004 * (i % 3)) * PI
            a1 = a0 + 0.036 * PI
            x1 = xa - 0.34
            x0 = xa + 0.34
            obs.append(_plate("mid_acc_%s_%d" % (tag, i), x0, x1,
                              _th(a0, sgn), _th(a1, sgn),
                              out=OUT_ARMOR + 0.007, thick=0.005, nx=3, nt=3,
                              mat=A['mid_armor'], col=col))
            obs.append(_plate("mid_acc_f_%s_%d" % (tag, i), x0 + 0.030, x1 - 0.030,
                              _th(a0 - 0.004 * PI, sgn), _th(a1 + 0.004 * PI, sgn),
                              out=OUT_ARMOR + 0.010, thick=0.003, nx=2, nt=2,
                              mat=M['alu'], col=col, bw=0.0012))
        ob = kit.join(obs, "mid_access_" + tag)
        kit.part(ob, "mid_access_" + tag, "%s舷检修盖板" % ("右" if sgn > 0 else "左"),
                 "Access Panels (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "hull_mid", (sgn, 0, 0), order=83,
                 note="7 块 680×160 mm 方形盖板 + 铝压边，交错分布在上舷")
        out.append(ob)


# ================================================================ 3. 散热辐射板
def _build_radiator(M, col, out, xc, tag, sgn):
    TH_H = 0.118 * PI          # 铰链所在角度（上舷）
    W, L = 0.72, 1.84          # 面板宽 / 长
    DEP = math.radians(26.0)   # 展开角
    T = 0.026                  # 板厚
    th = _th(TH_H, sgn)

    n, tx, tth = _frame(xc, th)
    v_down = tth if tth.z < 0 else -tth              # 两侧都朝下
    d = (v_down * math.cos(DEP) + n * math.sin(DEP)).normalized()
    e = (n * math.cos(DEP) - v_down * math.sin(DEP)).normalized()
    ph = _surf(xc, th, OUT_ARMOR + 0.026)

    obs = []
    for i in range(3):                                # 铰链座（贴壳）
        xh = xc + (i - 1) * L * 0.40
        obs.append(_plate("mid_rad_seat_%s_%d" % (tag, i), xh + 0.075, xh - 0.075,
                          _th(TH_H - 0.020 * PI, sgn), _th(TH_H + 0.020 * PI, sgn),
                          out=OUT_ARMOR + 0.030, thick=0.012, nx=2, nt=3,
                          mat=M['frame'], col=col))
    obs.append(_cylw("mid_rad_barrel_%s" % tag, ph, tx, 0.042, L * 1.02,
                     mat=M['alu'], col=col, seg=12))
    for i in range(3):
        obs.append(_cylw("mid_rad_knk_%s_%d" % (tag, i), ph + tx * ((i - 1) * L * 0.42),
                         tx, 0.062, 0.13, mat=M['gunmetal'], col=col, seg=8))

    pc = ph + d * (W * 0.5 + 0.02)
    obs.append(_boxw("mid_rad_panel_%s" % tag, pc, tx, d, e, L, W, T,
                     mat=M['radiator'], col=col, bw=0.0028, seg=2))
    for i in range(4):
        rc = ph + d * (W * (0.10 + 0.235 * i) + 0.02) + e * (T * 0.5 + 0.008)
        obs.append(_boxw("mid_rad_rib_%s_%d" % (tag, i), rc, tx, d, e,
                         L * 0.965, 0.026, 0.020, mat=M['alu'], col=col, bw=0))
    for s in (-1, 1):
        obs.append(_boxw("mid_rad_edge_%s_%d" % (tag, s),
                         ph + d * (W * 0.5 + 0.02) + tx * (s * L * 0.485), tx, d, e,
                         0.036, W + 0.01, T + 0.012, mat=M['frame'], col=col, bw=0))
    grp = kit.join(obs, "mid_radiator_" + tag)
    kit.part(grp, "mid_radiator_" + tag,
             "%s舷散热辐射板（%s）" % ("右" if sgn > 0 else "左",
                                 "前" if xc > -1.2 else "后"),
             "Deployable Radiator %s" % tag.upper(), "hull_mid", (sgn, 0, 0.2), order=78,
             note="铰链沿 X，展开 26°；板 + 4 肋 + 3 关节 + 3 个铰链座")
    out.append(grp)

    xa = xc + L * 0.28
    tha = _th(TH_H - 0.085 * PI, sgn)
    n2, tx2, tth2 = _frame(xa, tha)
    anchor = _surf(xa, tha, OUT_ARMOR + 0.020)
    tip = ph + d * (W * 0.62) + e * (T * 0.5 + 0.012) + tx * (L * 0.28)
    mid = anchor + (tip - anchor) * 0.56
    acts = [
        kit.pipe_run("mid_rad_cyl_%s" % tag, [tuple(anchor), tuple(mid)], 0.040,
                     mat=M['gunmetal'], col=col, seg=10, elbow=False),
        kit.pipe_run("mid_rad_rod_%s" % tag, [tuple(mid), tuple(tip)], 0.022,
                     mat=M['alu'], col=col, seg=10, elbow=False),
        _boxw("mid_rad_ear0_%s" % tag, anchor, tx2, tth2, n2, 0.10, 0.10, 0.05,
              mat=M['frame'], col=col, bw=0.002),
        _boxw("mid_rad_ear1_%s" % tag, tip, tx, d, e, 0.09, 0.09, 0.045,
              mat=M['frame'], col=col, bw=0.002),
    ]
    asm = kit.join(acts, "mid_rad_act_" + tag)
    kit.part(asm, "mid_rad_act_" + tag,
             "%s舷散热板液压作动筒（%s）" % ("右" if sgn > 0 else "左",
                                     "前" if xc > -1.2 else "后"),
             "Radiator Hydraulic Actuator %s" % tag.upper(), "detail", (sgn, -0.3, -0.4),
             order=90, note="缸筒 φ80 + 活塞杆 φ44，两端耳座分别贴壳 / 贴板")
    out.append(asm)


# ================================================================ 4. 舱门
def _build_airlock(M, col, out):
    xc, yc = -3.50, 0.58
    base = hull.deck_z(xc) - 0.006
    r_out, r_in, rise = 0.400, 0.332, 0.075

    parts = [kit.tube("mid_airlock_coaming", r_out, r_in, rise, axis='Z',
                      loc=(xc, yc, base + rise / 2.0), mat=M['frame'], col=col, seg=36)]
    for i in range(4):
        a = TAU * i / 4 + PI / 4
        parts.append(_boxw("mid_airlock_dog%d" % i,
                           (xc + (r_out + 0.026) * math.cos(a),
                            yc + (r_out + 0.026) * math.sin(a), base + rise * 0.55),
                           (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.072, 0.072, 0.088,
                           mat=M['gunmetal'], col=col, bw=0.002))
    coam = kit.join(parts, "mid_airlock_coaming")
    kit.part(coam, "mid_airlock_coaming", "气闸围板", "Airlock Coaming", "hull_mid",
             (0, 0, 1), order=79, note="环板 φ800/φ664、高 75 mm，外侧 4 个锁扣座")
    out.append(coam)

    door = [kit.cyl("mid_airlock_door", 0.315, 0.030, axis='Z',
                    loc=(xc, yc, base + 0.015), mat=M['hull_dark'], col=col,
                    seg=32, bw=0.0018, segs=1),
            kit.tube("mid_airlock_seal", 0.322, 0.300, 0.014, axis='Z',
                     loc=(xc, yc, base + 0.034), mat=M['rubber'], col=col, seg=32)]
    for i in (-1, 1):
        door.append(_boxw("mid_airlock_hinge%d" % (i + 2),
                          (xc + i * 0.22, yc - r_out - 0.010, base + rise * 0.42),
                          (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.11, 0.055, 0.105,
                          mat=M['alu'], col=col, bw=0.002))
    dr = kit.join(door, "mid_airlock_door")
    kit.part(dr, "mid_airlock_door", "气闸门板", "Airlock Door Leaf", "hull_mid",
             (0, 0, 1), order=80,
             note="φ630 门板沉在围板下 43 mm + 氟橡胶密封圈 φ644/φ600 + 2 副铰链")
    out.append(dr)

    win = [kit.cyl("mid_airlock_win_glass", 0.082, 0.016, axis='Z',
                   loc=(xc, yc, base + 0.040), mat=M['lens'], col=col, seg=20,
                   bw=0.0012, segs=1),
           kit.tube("mid_airlock_win_ring", 0.104, 0.082, 0.024, axis='Z',
                    loc=(xc, yc, base + 0.043), mat=M['alu'], col=col, seg=20)]
    wob = kit.join(win, "mid_airlock_window")
    kit.part(wob, "mid_airlock_window", "气闸观察窗", "Airlock Viewport", "detail",
             (0, 0, 1), order=91, note="φ164 双层镀膜玻璃，外压铝环")
    out.append(wob)

    wheel = [kit.tube("mid_wheel_rim", 0.168, 0.146, 0.026, axis='Z',
                      loc=(xc, yc, base + 0.062), mat=M['alu'], col=col, seg=24)]
    for i in range(3):
        a = TAU * i / 3 + 0.3
        wheel.append(_boxw("mid_wheel_spoke%d" % i,
                           (xc + 0.083 * math.cos(a), yc + 0.083 * math.sin(a),
                            base + 0.062),
                           (math.cos(a), math.sin(a), 0), (-math.sin(a), math.cos(a), 0),
                           (0, 0, 1), 0.115, 0.030, 0.020,
                           mat=M['alu'], col=col, bw=0.0016))
    wheel.append(kit.cyl("mid_wheel_hub", 0.048, 0.034, axis='Z',
                         loc=(xc, yc, base + 0.064), mat=M['gunmetal'], col=col,
                         seg=14, bw=0.0015, segs=1))
    wh = kit.join(wheel, "mid_airlock_wheel")
    kit.part(wh, "mid_airlock_wheel", "气闸手轮", "Airlock Handwheel", "detail",
             (0, 0, 1), order=92, note="φ336 轮缘 + 3 辐条 + 轮毂，环绕观察窗")
    out.append(wh)


def _build_service_hatch(M, col, out, sgn):
    xc = -6.80
    a = -0.105 * PI
    th = _th(a, sgn)
    half_l, dth = 0.52, 0.048 * PI
    obs = [_plate("mid_hatch_frame%d" % sgn, xc + half_l + 0.06, xc - half_l - 0.06,
                  th - dth, th + dth, out=OUT_ARMOR + 0.010, thick=0.006,
                  nx=4, nt=4, mat=M['frame'], col=col),
           _plate("mid_hatch_leaf%d" % sgn, xc + half_l, xc - half_l,
                  th - dth * 0.84, th + dth * 0.84,
                  out=OUT_ARMOR + 0.030, thick=0.014, nx=4, nt=4,
                  mat=M['hull_dark'], col=col)]
    n, tx, tth = _frame(xc, th)
    for i in (-1, 1):
        obs.append(_cylw("mid_hatch_hinge%d_%d" % (sgn, i),
                         _surf(xc - half_l + 0.02, th + i * dth * 0.5, OUT_ARMOR + 0.036),
                         tx, 0.020, 0.16, mat=M['alu'], col=col, seg=8))
    for i in (-1, 0, 1):
        obs.append(_boxw("mid_hatch_grip%d_%d" % (sgn, i),
                         _surf(xc + half_l - 0.12, th + i * 0.020 * PI, OUT_ARMOR + 0.048),
                         tx, tth, n, 0.05, 0.024, 0.036,
                         mat=M['gunmetal'], col=col, bw=0.0016))
    ob = kit.join(obs, "mid_hatch_%d" % sgn)
    kit.part(ob, "mid_hatch_%d" % sgn, "%s舷检修门" % ("右" if sgn > 0 else "左"),
             "Service Access Hatch (%s)" % ("Stbd" if sgn > 0 else "Port"),
             "hull_mid", (sgn, 0, -0.3), order=81,
             note="1040×400 mm 门叶抬起 16 mm，2 副铰链 + 3 个拉手")
    out.append(ob)


# ================================================================ 5. 细节层
def _build_detail(M, col, out, M2):
    # ---- 甲板碎件（平甲面，kit.greeble）
    g = kit.greeble("mid_greeble_deck_p", (-8.50, 0.30, -0.86, -0.20,
                                           hull.deck_z(-4.0), hull.deck_z(-4.0)),
                    44, seed=12, mat=M2['mid_greeble'], col=col, scale=0.80)
    kit.part(g, "mid_greeble_deck_p", "甲板碎件（左）", "Deck Machinery (Port)",
             "detail", (0, 0, 1), order=93, note="44 件，主梁与甲板边梁之间")
    out.append(g)
    g = kit.greeble("mid_greeble_deck_s", (0.30, -8.50, 0.20, 0.86,
                                           hull.deck_z(-4.0), hull.deck_z(-4.0)),
                    28, seed=21, mat=M2['mid_greeble'], col=col, scale=0.72)
    kit.part(g, "mid_greeble_deck_s", "甲板碎件（右）", "Deck Machinery (Stbd)",
             "detail", (0, 0, 1), order=94, note="28 件，避开气闸围板")
    out.append(g)

    # ---- 舷侧碎件（贴壳，按法线摆）
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        g = _greeble_racks("mid_greeble_flank_" + tag, -8.60, 2.90,
                           _th(0.042 * PI, sgn), _th(0.100 * PI, sgn), 8, seed=31 + sgn,
                           mat=M2['mid_greeble'], pad_mat=M2['mid_pad'], col=col,
                           Lmin=0.46, Lmax=0.98, depth=0.21)
        kit.part(g, "mid_greeble_flank_" + tag, "%s舷舷线碎件" % ("右" if sgn > 0 else "左"),
                 "Flank Machinery (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=95, note="30 组装机件（含安装底板），舷线上方走线区")
        out.append(g)

    # ---- 翼根前后碎件（肩部倒角带）
    g = _greeble_racks("mid_greeble_shoulder", -6.30, -1.90, 0.150 * PI, 0.224 * PI,
                       5, seed=47, mat=M2['mid_greeble'], pad_mat=M2['mid_pad'], col=col,
                       Lmin=0.50, Lmax=0.96, depth=0.24)
    kit.part(g, "mid_greeble_shoulder", "翼根肩部碎件", "Shoulder Machinery",
             "detail", (0, 0, 1), order=96, note="24 组装机件，右舷肩部倒角带")
    out.append(g)
    g = _greeble_racks("mid_greeble_shoulder_p", -6.30, -1.90,
                       _th(0.150 * PI, -1), _th(0.224 * PI, -1),
                       5, seed=53, mat=M2['mid_greeble'], pad_mat=M2['mid_pad'], col=col,
                       Lmin=0.50, Lmax=0.96, depth=0.24)
    kit.part(g, "mid_greeble_shoulder_p", "翼根肩部碎件（左）", "Shoulder Machinery (Port)",
             "detail", (0, 0, 1), order=97, note="24 组装机件，左舷肩部倒角带")
    out.append(g)

    # ---- 电缆束（沿舷线贴壳折线）
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        runs = []
        for k, (a, r) in enumerate(((0.028 * PI, 0.020), (0.016 * PI, 0.013))):
            pts = []
            for i in range(7):
                x = 2.95 - i * 1.92
                th = _th(a + 0.006 * PI * math.sin(i * 1.7), sgn)
                pts.append(tuple(_surf(x, th, OUT_ARMOR + 0.012 + r)))
            runs.append(kit.pipe_run("mid_cable_%s_%d" % (tag, k), pts, r,
                                     mat=(M['black'] if k == 0 else M['alu']),
                                     col=col, seg=6, elbow=False))
        ob = kit.join(runs, "mid_cable_" + tag)
        kit.part(ob, "mid_cable_" + tag, "%s舷电缆束" % ("右" if sgn > 0 else "左"),
                 "Cable Harness (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=98, note="2 条沿舷线走线，φ40 / φ26")
        out.append(ob)

    # ---- 天线 ×3（不同长度）
    ants = []
    for i, (ax, ay, ln, rr) in enumerate(((-6.90, -0.62, 0.86, 0.012),
                                          (1.90, 0.66, 0.56, 0.010),
                                          (-8.35, 0.52, 0.36, 0.009))):
        dz = hull.deck_z(ax)
        ants.append(kit.cyl("mid_ant_base%d" % i, 0.055, 0.045, axis='Z',
                            loc=(ax, ay, dz + 0.014), mat=M['gunmetal'], col=col,
                            seg=12, bw=0.0015, segs=1))
        ants.append(kit.cyl("mid_ant_rod%d" % i, rr, ln, axis='Z',
                            loc=(ax, ay, dz + 0.028 + ln / 2), mat=M['alu'], col=col,
                            seg=6, bw=0, r2=rr * 0.45))
        ants.append(kit.cyl("mid_ant_tip%d" % i, rr * 0.55, 0.022, axis='Z',
                            loc=(ax, ay, dz + 0.028 + ln + 0.008), mat=M['led_red'],
                            col=col, seg=6, bw=0))
    an = kit.join(ants, "mid_antenna")
    kit.part(an, "mid_antenna", "天线组", "Antenna Array", "detail", (0, 0, 1),
             order=99, note="3 根（860 / 560 / 360 mm），锥形振子 + 红色顶灯")
    out.append(an)

    # ---- 传感器鼓包 ×4
    sens = []
    for i, (sx, sy) in enumerate(((2.42, -0.70), (-2.15, -0.70), (-5.25, 0.74))):
        dz = hull.deck_z(sx)
        sens.append(_dome("mid_sensor_body%d" % i, (sx, sy, dz - 0.004), (0, 0, 1),
                          0.115, 0.072, mat=M2['mid_dome'], col=col))
        sens.append(kit.tube("mid_sensor_ring%d" % i, 0.128, 0.112, 0.020, axis='Z',
                             loc=(sx, sy, dz + 0.006), mat=M['alu'], col=col, seg=18))
    px, pth = -7.30, _th(0.170 * PI, 1)
    n, tx, tth = _frame(px, pth)
    sens.append(_dome("mid_sensor_body3", tuple(_surf(px, pth, OUT_ARMOR + 0.002)), n,
                      0.105, 0.062, mat=M2['mid_dome'], col=col))
    sens.append(_cylw("mid_sensor_ring3", _surf(px, pth, OUT_ARMOR + 0.001), n,
                      0.118, 0.016, mat=M['alu'], col=col, seg=16))
    se = kit.join(sens, "mid_sensor")
    kit.part(se, "mid_sensor", "传感器鼓包", "Sensor Blisters", "detail", (0, 0, 1),
             order=100, note="4 个：甲板 3 个 φ230 + 右舷肩部 1 个 φ210")
    out.append(se)

    # ---- 加油口盖 ×2（舷侧圆盖 + 4 螺栓）
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        xc, thc = 2.62, _th(0.088 * PI, sgn)
        n, tx, tth = _frame(xc, thc)
        caps = [_cylw("mid_fuel_cap_%s" % tag, _surf(xc, thc, OUT_ARMOR + 0.008), n,
                      0.120, 0.022, mat=M['hull_dark'], col=col, seg=18),
                _cylw("mid_fuel_ring_%s" % tag, _surf(xc, thc, OUT_ARMOR + 0.004), n,
                      0.138, 0.014, mat=M['alu'], col=col, seg=18)]
        for i in range(4):
            a2 = TAU * i / 4 + 0.4
            c = (_surf(xc, thc, OUT_ARMOR + 0.018)
                 + tth * (0.092 * math.cos(a2)) + tx * (0.092 * math.sin(a2)))
            caps.append(_cylw("mid_fuel_bolt_%s_%d" % (tag, i), tuple(c), n,
                              0.014, 0.016, mat=M['gunmetal'], col=col, seg=6, bw=0))
        ob = kit.join(caps, "mid_fuel_" + tag)
        kit.part(ob, "mid_fuel_" + tag, "%s舷加油口盖" % ("右" if sgn > 0 else "左"),
                 "Fuel Filler Cap (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=101, note="φ240 盖 + φ276 压环 + 4 螺栓")
        out.append(ob)

    # ---- 散热格栅 ×4：底板走贴面 _plate，百叶做短件（长平板搭曲面会陷进壳里）
    vents = []
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        for j, vx in enumerate((0.10, -5.15)):
            th = _th(-0.082 * PI, sgn)
            vents.append(_plate("mid_vent_%s_%d_base" % (tag, j), vx + 0.20, vx - 0.20,
                                _dth_for_arc(vx, th, -0.15), _dth_for_arc(vx, th, 0.15),
                                out=OUT_ARMOR + 0.026, thick=0.024, nx=3, nt=3,
                                mat=M['gunmetal'], col=col))
            n, tx, tth = _frame(vx, th)
            p0 = _surf(vx, th, OUT_ARMOR + 0.026)
            for k in range(6):
                vents.append(_boxw("mid_vent_%s_%d_s%d" % (tag, j, k),
                                   p0 + tth * (-0.098 + k * 0.039) + n * 0.010,
                                   tx, (tth * 0.86 + n * 0.51).normalized(), n,
                                   0.32, 0.018, 0.026, mat=M['black'], col=col, bw=0))
            for e in (-1, 1):
                vents.append(_boxw("mid_vent_%s_%d_e%d" % (tag, j, e + 2),
                                   p0 + tx * (e * 0.170) + n * 0.008,
                                   tx, tth, n, 0.022, 0.26, 0.026,
                                   mat=M['alu'], col=col, bw=0))
    ob = kit.join(vents, "mid_vent")
    kit.part(ob, "mid_vent", "散热格栅", "Vent Grilles", "detail", (0, 0, 0), order=102,
             note="4 组 440×300（底板 + 6 片斜百叶 + 铝压边），按贴壳法线摆")
    out.append(ob)


# ================================================================ 6. 涂装与灯带
def _build_marks(M, col, out):
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        ob = _label("mid_name_" + tag, "AEGIS-7", -5.35, 0.150 * PI, 0.135, sgn,
                    M['decal'], col)
        kit.part(ob, "mid_name_" + tag, "%s舷舰名" % ("右" if sgn > 0 else "左"),
                 "Ship Name AEGIS-7 (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=103, note="逐字各贴自己那点的法线，外推 7.5 mm")
        out.append(ob)

        ob = _label("mid_num_" + tag, "KV-07", 1.06, 0.010 * PI, 0.180, sgn,
                    M['decal'], col)
        kit.part(ob, "mid_num_" + tag, "%s舷舷号" % ("右" if sgn > 0 else "左"),
                 "Hull Number KV-07 (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=104, note="舷线装甲带上，白色漆 180 mm 高")
        out.append(ob)

    ob = _text("mid_no_step", "NO STEP", _deck_pt(-2.30, -0.62, 0.004),
               (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.085, M['decal_dark'], col)
    kit.part(ob, "mid_no_step", "禁止踩踏标识", "NO STEP Marking", "detail",
             (0, 0, 1), order=105, note="甲板平贴，标出承力区禁踩范围")
    out.append(ob)

    dan = []
    for sgn in (1, -1):
        xc, thc = 1.86, _th(0.182 * PI, sgn)
        n, tx, _t = _frame(xc, thc)
        read = -tx if sgn > 0 else tx
        dan.append(_text("mid_danger_%d" % sgn, "DANGER", _surf(xc, thc, OUT_TRIM + 0.004),
                         read, n.cross(read).normalized(), n, 0.062, M['decal'], col))
    ob = kit.join(dan, "mid_danger")
    kit.part(ob, "mid_danger", "高压警示标识", "DANGER Marking", "detail", (0, 0, 0),
             order=106, note="两舷肩部，压在红色警示条上")
    out.append(ob)

    res = []
    for sgn in (1, -1):
        xc, thc = -6.80, _th(-0.058 * PI, sgn)
        n, tx, _t = _frame(xc, thc)
        read = -tx if sgn > 0 else tx
        res.append(_text("mid_rescue_%d" % sgn, "RESCUE", _surf(xc, thc, OUT_TRIM + 0.004),
                         read, n.cross(read).normalized(), n, 0.070, M['decal'], col))
    ob = kit.join(res, "mid_rescue")
    kit.part(ob, "mid_rescue", "救援标识", "RESCUE Marking", "detail", (0, 0, 0),
             order=107, note="检修门上缘，两舷")
    out.append(ob)

    # ---- 舷线断续灯带（段 0.40 m / 间隔 0.25 m）
    for sgn in (1, -1):
        tag = "stbd" if sgn > 0 else "port"
        segs, x, i = [], 3.02, 0
        while x - 0.40 > X_A + 0.1:
            segs.append(_plate("mid_led_%s_%d" % (tag, i), x, x - 0.40,
                               _th(0.030 * PI, sgn), _th(0.043 * PI, sgn),
                               out=OUT_LED, thick=0.004, nx=2, nt=2,
                               mat=M['led'], col=col, bw=0.0012))
            x -= 0.65
            i += 1
        ob = kit.join(segs, "mid_led_" + tag)
        kit.part(ob, "mid_led_" + tag, "%s舷灯带" % ("右" if sgn > 0 else "左"),
                 "Chine LED Strip (%s)" % ("Stbd" if sgn > 0 else "Port"),
                 "detail", (sgn, 0, 0), order=108,
                 note="%d 段，段长 0.40 m / 间隔 0.25 m，冷白" % i)
        out.append(ob)


# ================================================================ 材质
def _extra_mats():
    M2 = {}
    M2['mid_greeble'] = mats._principled("S_Mid_Greeble", (0.255, 0.262, 0.278),
                                         0.35, 0.46,
                                         normal=mats.tex_metal_normal(),
                                         orm=mats.tex_orm_metal(name="orm_mid_greeble"),
                                         spec=0.5, nrm_str=0.30, uv_scale=1.9)
    # 中灰装甲板：深浅两色里的"深"，与 S_Hull 只差 2.3 倍，远看是分块而不是补丁
    M2['mid_armor'] = mats._principled("S_Mid_Armor", (0.150, 0.156, 0.170),
                                       0.14, 0.44, normal=mats.tex_paint_normal(),
                                       orm=mats.tex_paint_orm(name="orm_mid_armor"),
                                       spec=0.5, nrm_str=0.28, coat=0.30, uv_scale=0.55)
    # 安装底板：深色，让碎件看起来"装在板上"而不是浮在壳面
    M2['mid_pad'] = mats._principled("S_Mid_Pad", (0.075, 0.078, 0.088), 0.30, 0.55,
                                     normal=mats.tex_metal_normal(), nrm_str=0.25,
                                     uv_scale=2.4)
    M2['mid_dome'] = mats._principled("S_Mid_Dome", (0.028, 0.033, 0.042),
                                      0.25, 0.22, coat=0.6, clearcoat_rough=0.08,
                                      spec=0.7)
    return M2


# ================================================================ 装配
def build(M, col):
    out = []
    M2 = _extra_mats()

    _build_keel(M, col, out)                       # 背脊主梁 / 肋骨 / 横梁 / 甲板边梁
    _build_armor(M, col, out, M2)                  # 三条带装甲 + 涂装条
    _build_deck_plating(M, col, out, M2)           # 甲板铺设板
    _build_access_panels(M, col, out, M2)          # 舷侧检修盖板
    for sgn in (1, -1):
        for tag, xc in (("f", 0.10), ("a", -2.30)):
            _build_radiator(M, col, out, xc, tag if sgn > 0 else tag + "p", sgn)
    _build_airlock(M, col, out)                    # 上表面气闸
    for sgn in (1, -1):
        _build_service_hatch(M, col, out, sgn)
    _build_detail(M, col, out, M2)                 # 碎件 / 电缆 / 天线 / 传感器 / 口盖 / 格栅
    _build_marks(M, col, out)                      # 涂装文字 + 灯带

    return [o for o in out if o is not None]
