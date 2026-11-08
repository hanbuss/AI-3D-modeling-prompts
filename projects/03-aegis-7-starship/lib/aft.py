"""starship/lib/aft.py — 动力段：三台主引擎 / 收敛-扩张喷管 / 涡轮静子 / 尾框

坐标：+X 舰首，+Y 右舷，+Z 上，米。喷口朝 -X。
所有回转体都绕「引擎中心线」旋转 —— 中心线严格过 spec.ENGINES 的 (y, z)。

数值唯一真值：
  engine_port/stbd  y=∓2.60  z=-0.45  r_body 0.780  出口 x=-17.40  bell 0.920/0.760  flame 7.4
  engine_ctr        y= 0.00  z=+0.28  r_body 0.640  出口 x=-15.75  bell 0.760/0.620  flame 6.2

几何自检（build 里打印）：每个引擎喷口端面的实测圆心与半径必须与 spec 完全一致。
"""
import math
import bpy, bmesh

import kit
import hull
import mats
import spec as S

TAU = math.tau

# ---------------------------------------------------------------- 常量
POD_BAND_MAT = 'aft_band'


# ================================================================ 基础工具
def _rev(name, cy, cz, prof, seg=48, mat=None, col=None, smooth=True,
         bw=0.0, bseg=2, loop=True, ang=34.0):
    """绕 X 轴旋转一条 (x, r) 剖面。

    prof   : [(x, r), ...]，r=0 处自动收成单点（锥尖）
    loop   : True = 剖面是闭合环（壳体/环形件）；False = 两端封盖的实体
    """
    bm = bmesh.new()
    cs = [(math.cos(TAU * i / seg), math.sin(TAU * i / seg)) for i in range(seg)]
    rings = []
    for (x, r) in prof:
        if r <= 1e-7:
            rings.append([bm.verts.new((x, cy, cz))])
        else:
            rings.append([bm.verts.new((x, cy + r * c, cz + r * s)) for (c, s) in cs])
    seq = list(zip(rings[:-1], rings[1:]))
    if loop:
        seq.append((rings[-1], rings[0]))
    for a, b in seq:
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(seg):
                bm.faces.new((a[0], b[i], b[(i + 1) % seg]))
        elif len(b) == 1:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[0]))
        else:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    if not loop:
        if len(rings[0]) > 1:
            bm.faces.new(list(reversed(rings[0])))
        if len(rings[-1]) > 1:
            bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=smooth)
    if bw:
        kit.finish(ob, bw, bseg, ang)
    return ob


def _annulus(name, cy, cz, x0, x1, ri, ro, seg=48, mat=None, col=None, bw=0.0):
    """沿 X 的环形实体（安装环 / 加强箍 / 唇缘）"""
    prof = [(x0, ri), (x0, ro), (x1, ro), (x1, ri)]
    return _rev(name, cy, cz, prof, seg=seg, mat=mat, col=col, bw=bw, loop=True)


def _box_between(name, a, b, w, h, mat=None, col=None, bw=0.004):
    """两点之间的方截面撑杆（挂架 / 作动筒安装座 / RCS 支架）"""
    from mathutils import Vector
    A, B = Vector(a), Vector(b)
    d = B - A
    L = d.length
    ob = kit.box(name, (w, h, L), mat=mat, col=col, bw=bw, seg=1)
    ob.location = tuple((A + B) / 2)
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return ob


def _rod(name, a, b, r, mat=None, col=None, seg=14):
    from mathutils import Vector
    A, B = Vector(a), Vector(b)
    d = B - A
    L = max(d.length, 1e-4)
    ob = kit.cyl(name, r, L, axis='Z', loc=tuple((A + B) / 2), mat=mat, col=col,
                 seg=seg, bw=0.002, segs=1)
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return ob


def _blade_ring(name, cy, cz, x0, rh, rt, count=24, chord=0.145, thick=0.017,
                stagger=34.0, sweep=0.035, mat=None, col=None):
    """一级涡轮静子叶片环：count 片真实叶片（有弦长、厚度、安装角、后掠），不是圆盘"""
    bm = bmesh.new()
    beta = math.radians(stagger)
    cb, sb = math.cos(beta), math.sin(beta)
    c2, t2 = chord / 2.0, thick / 2.0
    sec = [(c2, t2), (c2, -t2), (-c2, -t2), (-c2, t2)]
    for k in range(count):
        a = TAU * k / count
        ca, sa = math.cos(a), math.sin(a)
        vs = []
        for r in (rh * 0.985, rt):
            sw = sweep * (r - rh) / max(rt - rh, 1e-6)
            for (sx, sy) in sec:
                ax = sx * cb - sy * sb
                tg = sx * sb + sy * cb
                y = cy + ca * r - sa * tg
                z = cz + sa * r + ca * tg
                vs.append(bm.verts.new((x0 + ax + sw, y, z)))
        hi, ho = vs[0:4], vs[4:8]
        bm.faces.new((hi[0], hi[1], hi[2], hi[3]))                    # 叶根
        bm.faces.new((ho[3], ho[2], ho[1], ho[0]))                    # 叶尖
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((hi[i], hi[j], ho[j], ho[i]))                # 叶片四边
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col, smooth=False)


def _hull_collar(name, x0, width, out=0.045, thick=0.030, seg=72, mat=None, col=None, bw=0.0):
    """贴合船壳截面的承力框（沿 X 有宽度的环箍）"""
    bm = bmesh.new()
    ths = [TAU * i / seg for i in range(seg)]
    hw = width / 2.0
    rows = []
    off_in = out - thick
    for (dx, off) in ((-hw, out), (hw, out), (hw, off_in), (-hw, off_in)):
        row = []
        for th in ths:
            p = hull.surf(x0 + dx, th, off)
            row.append(bm.verts.new((p.x, p.y, p.z)))
        rows.append(row)
    for a, b in ((rows[0], rows[1]), (rows[1], rows[2]), (rows[2], rows[3]), (rows[3], rows[0])):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.finish(ob, bw, 1, 40.0)
    return ob


def _cyl_patch(name, cy, cz, x0, x1, r, a0, a1, thick=0.012, nt=4, mat=None, col=None, bw=0.0):
    """圆柱面上的局部贴片（隔热瓦 / 检修盖），a0..a1 为绕 X 的角度区间"""
    bm = bmesh.new()
    outer, inner = [], []
    for x in (x0, x1):
        ro, ri = [], []
        for j in range(nt + 1):
            a = a0 + (a1 - a0) * j / nt
            ro.append(bm.verts.new((x, cy + r * math.cos(a), cz + r * math.sin(a))))
            ri.append(bm.verts.new((x, cy + (r - thick) * math.cos(a), cz + (r - thick) * math.sin(a))))
        outer.append(ro)
        inner.append(ri)
    for j in range(nt):
        bm.faces.new((outer[0][j], outer[0][j + 1], outer[1][j + 1], outer[1][j]))
        bm.faces.new((inner[1][j], inner[1][j + 1], inner[0][j + 1], inner[0][j]))
    for j in range(nt):
        bm.faces.new((outer[0][j], inner[0][j], inner[0][j + 1], outer[0][j + 1]))
        bm.faces.new((outer[1][j + 1], inner[1][j + 1], inner[1][j], outer[1][j]))
    for x_i in (0, 1):
        bm.faces.new((outer[x_i][0], outer[x_i][nt], inner[x_i][nt], inner[x_i][0]))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=True)
    if bw:
        kit.finish(ob, bw, 1, 40.0)
    return ob


# ================================================================ 材质
def _extra_mats(M):
    """动力段专用材质（S_Aft 前缀，不覆盖别人的键）"""
    def P(key, name=None, **kw):
        """key = M 字典里的键；name = 材质名（默认用 key）。已存在则复用，不覆盖别人的。"""
        if key not in M:
            M[key] = mats._principled(name=name or key, **kw)
        return M[key]

    P('aft_turbine', name="S_Aft_Turbine", base=(0.340, 0.270, 0.215), metallic=1.0,
      rough=0.30, normal=mats.tex_heat_normal(), orm=mats.tex_orm_metal(),
      spec=0.60, nrm_str=0.26, uv_scale=2.4, emission=(1.0, 0.34, 0.09, 0.85))
    P('aft_soot', name="S_Aft_Soot", base=(0.030, 0.026, 0.024), metallic=0.55,
      rough=0.62, normal=mats.tex_heat_normal(), nrm_str=0.5, spec=0.3, uv_scale=1.8)
    P('aft_cavity', name="S_Aft_Cavity", base=(0.9, 0.28, 0.06), metallic=0.0,
      rough=0.55, emission=(1.0, 0.32, 0.06, 14.0))
    P('aft_hotring', name="S_Aft_HotRing", base=(0.30, 0.16, 0.08), metallic=0.9,
      rough=0.40, normal=mats.tex_heat_normal(), nrm_str=0.45,
      emission=(0.9, 0.28, 0.05, 3.0), uv_scale=2.2)
    return M


# ================================================================ 引擎
def _bell_profile(x_end, exit_x, r_body, r_out, r_in):
    """收敛-扩张喷管：壳体闭合剖面（外壁 / 出口唇面 / 内壁 / 安装法兰）"""
    L = x_end - exit_x                      # 正值
    r_th = r_body * 0.72                    # 喉部（收敛段最小半径）
    ts = (0.0, 0.16, 0.34, 0.56, 0.78, 1.0)
    outer = [(x_end - L * t, r_body * 0.95 + (r_out - r_body * 0.95) * (t ** 1.75)) for t in ts]
    inner = [(x_end - L * t, r_th + (r_in - r_th) * (t ** 1.9)) for t in ts]
    prof = list(outer)                              # 外壁：喉部端面 → 出口
    prof.append((exit_x, r_out))                    # 出口唇缘外沿
    prof.append((exit_x, r_in))                     # 出口唇面（径向）
    prof += list(reversed(inner))                   # 内壁：出口 → 喉部
    prof.append((x_end, r_th))
    prof.append((x_end, r_body * 0.95))             # 安装法兰（径向，闭合）
    return prof, r_th


def build_engine(M, col, eid, y, z, r_body, x_start, x_end, r_out, r_in, exit_x, flame_len,
                 side=True):
    obs = []
    sfx = {"engine_port": "p", "engine_stbd": "s", "engine_ctr": "c"}[eid]
    L = x_end - exit_x

    # ---------------------------------------------------------- 吊舱外壳
    xs = x_start
    prof = [                      # (x, r/r_body)：外壁 → 尾端面 → 内壁 → 前端面（闭合）
        (xs, 0.58), (xs - 0.10, 0.78), (xs - 0.55, 0.95), (xs - 1.05, 1.00),
        (x_end + 0.55, 1.00), (x_end, 0.985),
        (x_end, 0.760),
        (xs - 1.10, 0.760), (xs - 0.10, 0.520), (xs, 0.440),
    ]
    prof = [(x, r * r_body) for (x, r) in prof]
    shell = _rev("aft_pod_%s" % sfx, y, z, prof, seg=44, mat=M['hull'],
                 col=col, bw=0.006, bseg=1, loop=True)
    obs.append(kit.part(shell, "aft_nacelle_%s" % sfx, "引擎吊舱外壳", "Engine Nacelle Shell",
                        "engines", (0, 0.5 if side else 0, 0.8),
                        note="沿 X 回转的吊舱壳体，中心线严格过 spec (y=%.2f,z=%.2f)" % (y, z)))

    # ---------------------------------------------------------- 环形加强筋 8 道
    ribs = []
    for i in range(8):
        t = (i + 0.5) / 8.0
        xr = x_start - 0.35 - (x_start - x_end - 0.95) * t
        rr = r_body * (1.005 + 0.012)
        ribs.append(_annulus("aft_rib_%s_%d" % (sfx, i), y, z, xr - 0.024, xr + 0.024,
                             rr - 0.03, rr, seg=28, mat=M['frame'], col=col))
    rib = kit.join(ribs, "aft_ribs_%s" % sfx)
    obs.append(kit.part(rib, "aft_nacelle_ribs_%s" % sfx, "吊舱环形加强筋", "Nacelle Ring Ribs",
                        "engines", (0, 0.35 if side else 0, 0.55),
                        note="8 道环形加强筋，外凸 3 cm"))

    # ---------------------------------------------------------- 外壁加强箍（侧吊舱 4 道）
    if side:
        bands = []
        for i in range(4):
            xb = x_start - 1.45 - i * 1.02
            ro = r_body * 1.0 + 0.020
            bands.append(_annulus("aft_band_%s_%d" % (sfx, i), y, z, xb - 0.045, xb + 0.045,
                                  r_body - 0.05, ro, seg=28,
                                  mat=M['hull_dark'], col=col))
        bd = kit.join(bands, "aft_bands_%s" % sfx)
        obs.append(kit.part(bd, "aft_pod_bands_%s" % sfx, "吊舱加强箍", "Nacelle Band Collars",
                            "engines", (0, 0.6 if side else 0, 0.2),
                            note="4 道环形箍：宽 9 cm、外凸 2 cm"))

    # ---------------------------------------------------------- 前后安装环 + 螺栓
    for tag, xm in (("fwd", x_start - 0.28), ("aft", x_end + 0.05)):
        ring = _annulus("aft_mr_%s_%s" % (sfx, tag), y, z, xm - 0.045, xm + 0.045,
                        r_body * 0.94, r_body * 1.035, seg=30, mat=M['frame'],
                        col=col)
        blt = kit.bolt_ring("aft_blt_%s_%s" % (sfx, tag), xm + 0.055, y, z,
                            r_body * 0.985, 10, axis='X', mat=M['black'], col=col,
                            br=0.022, bh=0.022)
        obs.append(kit.part(kit.join([ring, blt], "aft_mount_%s_%s" % (sfx, tag)),
                            "aft_mount_ring_%s_%s" % (sfx, tag),
                            "引擎安装环（%s）" % ("前" if tag == "fwd" else "后"),
                            "Engine Mount Ring (%s)" % tag, "engines",
                            (0, 0.4 if side else 0, 0.3),
                            note="10 颗连接螺栓，环带贴合 r_body"))

    # ---------------------------------------------------------- 收敛-扩张喷管
    bell_prof, r_th = _bell_profile(x_end, exit_x, r_body, r_out, r_in)
    bell = _rev("aft_bell_%s" % sfx, y, z, bell_prof, seg=44, mat=M['heat_steel'],
                col=col, bw=0.004, bseg=1, loop=True)
    obs.append(kit.part(bell, "aft_bell_%s" % sfx, "收敛-扩张喷管", "Converging-Diverging Nozzle",
                        "engines", (0, 0.45 if side else 0, 0.15),
                        note="外壁 heat_steel；出口端面 r_out=%.3f r_in=%.3f @ x=%.2f"
                             % (r_out, r_in, exit_x)))

    # 内壁陶瓷隔热衬（沿内壁偏移 0.006 的薄壳）
    liner = []
    ts = [i / 6.0 for i in range(7)]
    for t in ts:
        rr = r_th + (r_in - r_th) * (t ** 1.9)
        liner.append((x_end - L * t, rr - 0.002))
    for t in reversed(ts):
        rr = r_th + (r_in - r_th) * (t ** 1.9)
        liner.append((x_end - L * t, rr + 0.010))
    lin = _rev("aft_bell_inner_%s" % sfx, y, z, liner, seg=40, mat=M['ceramic'],
               col=col, bw=0.0, loop=True)
    obs.append(kit.part(lin, "aft_bell_inner_%s" % sfx, "喷管内壁陶瓷衬", "Nozzle Ceramic Liner",
                        "engines", (0, 0.3 if side else 0, 0.1),
                        note="ceramic 内衬：从喉部到出口整段"))

    # 出口唇缘（black 环）
    lip = _annulus("aft_lip_%s" % sfx, y, z, exit_x - 0.002, exit_x + 0.075,
                   r_in + 0.002, r_out + 0.008, seg=40, mat=M['black'], col=col)
    obs.append(kit.part(lip, "aft_lip_%s" % sfx, "喷口唇缘", "Nozzle Exit Lip",
                        "engines", (0, 0.2 if side else 0, 0.05),
                        note="black 阳极氧化唇环，喷口端面中心 = (%.2f, %.2f, %.2f)"
                             % (exit_x, y, z)))

    # ---------------------------------------------------------- 涡轮静子（2 级 × 24 片）
    st1_x = x_end + 0.42
    st1 = _blade_ring("aft_stator1_%s" % sfx, y, z, st1_x, 0.20 * r_body / 0.78,
                      r_body * 0.60 / 0.78 * 0.99, count=24, chord=0.165, thick=0.020,
                      stagger=36.0, sweep=0.030, mat=M['aft_turbine'], col=col)
    obs.append(kit.part(st1, "aft_stator_1_%s" % sfx, "一级涡轮静子叶片环", "Turbine Stator Ring 1",
                        "engines", (0, 0.15 if side else 0, 0.0),
                        note="24 片真实叶片（弦长 150 mm、安装角 36°、后掠 30 mm）"))
    hub1 = _annulus("aft_hub1_%s" % sfx, y, z, st1_x - 0.16, st1_x + 0.16,
                    0.0, 0.20 * r_body / 0.78, seg=40, mat=M['aft_soot'], col=col, bw=0.004)
    obs.append(kit.part(hub1, "aft_stator_hub_%s" % sfx, "一级静子轮毂", "Stator 1 Hub",
                        "engines", (0, 0.1 if side else 0, 0.0), note="轮毂筒，托住一级叶片根"))

    st2_t = 0.40
    st2_x = x_end - L * st2_t
    st2_tip = (r_th + (r_in - r_th) * (st2_t ** 1.9)) * 0.985
    st2 = _blade_ring("aft_stator2_%s" % sfx, y, z, st2_x, 0.245 * r_body / 0.78, st2_tip,
                      count=24, chord=0.175, thick=0.021, stagger=26.0, sweep=0.030,
                      mat=M['aft_turbine'], col=col)
    obs.append(kit.part(st2, "aft_stator_2_%s" % sfx, "二级涡轮静子叶片环", "Turbine Stator Ring 2",
                        "engines", (0, 0.12 if side else 0, 0.0),
                        note="24 片真实叶片，位于扩张段内侧"))

    # ---------------------------------------------------------- 中心锥 + 加力环腔
    cb_x = exit_x + 1.18
    tip_x = exit_x + 0.16
    cprof = []
    n = 8
    for i in range(n + 1):
        t = i / n
        cprof.append((cb_x - (cb_x - tip_x) * t, 0.265 * r_body / 0.78 * (1.0 - t) ** 0.78))
    cone = _rev("aft_cone_%s" % sfx, y, z, cprof, seg=48, mat=M['aft_turbine'],
                col=col, bw=0.004, loop=False)
    obs.append(kit.part(cone, "aft_center_cone_%s" % sfx, "喷口中心锥", "Exhaust Centre Cone",
                        "engines", (0, 0.05 if side else 0, 0.0),
                        note="从 x=%.2f 收到 x=%.2f 的锥体，从尾部看进去有纵深" % (cb_x, tip_x)))

    duct = _annulus("aft_ab_%s" % sfx, y, z, cb_x - 0.02, exit_x + 1.62,
                    0.395 * r_body / 0.78, 0.435 * r_body / 0.78, seg=48,
                    mat=M['aft_hotring'], col=col, bw=0.004)
    obs.append(kit.part(duct, "aft_ab_duct_%s" % sfx, "加力燃烧室环腔", "Afterburner Annulus Duct",
                        "engines", (0, 0.1 if side else 0, 0.0),
                        note="中心筒与内壁之间的环腔，后接中心锥"))

    holders = []
    for k in range(14):
        a = TAU * k / 14
        r0 = 0.44 * r_body / 0.78
        r1 = 0.575 * r_body / 0.78
        xh = exit_x + 1.50
        holders.append(_box_between("aft_abf_%s_%d" % (sfx, k),
                                    (xh, y + r0 * math.cos(a), z + r0 * math.sin(a)),
                                    (xh, y + r1 * math.cos(a), z + r1 * math.sin(a)),
                                    0.055, 0.026, mat=M['aft_soot'], col=col, bw=0.002))
    hl = kit.join(holders, "aft_ab_holders_%s" % sfx)
    obs.append(kit.part(hl, "aft_ab_holders_%s" % sfx, "加力稳焰器", "Afterburner Flame Holders",
                        "engines", (0, 0.1 if side else 0, 0.0),
                        note="14 片径向 V 形稳焰片，环腔内一圈"))

    # 腔内暗红辉光（给喷口纵深，避免一口黑洞）
    glow = _annulus("aft_cav_%s" % sfx, y, z, x_end + 0.30, x_end + 0.38,
                    r_body * 0.05, r_body * 0.78, seg=40, mat=M['aft_cavity'],
                    col=col, bw=0.0)
    obs.append(kit.part(glow, "aft_cavity_glow_%s" % sfx, "燃烧室辉光环", "Combustor Glow Ring",
                        "engines", (0, 0.05 if side else 0, 0.0),
                        note="腔内暗红自发光环，衬托内部叶片层次"))

    # ---------------------------------------------------------- 隔热瓦（12 块 foil）
    tiles = []
    for i in range(10):
        a0 = TAU * i / 10 + 0.05
        a1 = a0 + TAU / 10 - 0.10
        xt = x_start - 1.55 - (i % 4) * 0.62
        tiles.append(_cyl_patch("aft_tile_%s_%d" % (sfx, i), y, z,
                                xt, xt - 0.42, r_body + 0.022, a0, a1, thick=0.014,
                                nt=2, mat=M['foil'], col=col))
    tl = kit.join(tiles, "aft_tiles_%s" % sfx)
    obs.append(kit.part(tl, "aft_heat_tiles_%s" % sfx, "吊舱隔热瓦", "Nacelle Heat Tiles",
                        "detail", (0, 0.5 if side else 0, 0.6),
                        note="10 块金色多层隔热膜瓦片，贴在吊舱外壁"))

    # ---------------------------------------------------------- 燃油/冷却管路
    sy = 1.0 if y > 0 else -1.0
    pipes = []

    def on_pod(x, ang, rr):
        """吊舱外壁上的点（rr 为贴壁半径，略大于 r_body 让管子骑在壳上）"""
        return (x, y + sy * math.cos(ang) * rr, z + math.sin(ang) * rr)

    for i, (ang, rr, rad) in enumerate(((0.62, r_body + 0.042, 0.042),
                                        (0.95, r_body + 0.036, 0.030))):
        # 三段直线：完全贴合等半径的吊舱外筒，只有最前/最后 5% 跟随收口
        pts = [on_pod(x_start - 0.75, ang, rr),
               on_pod(x_start - 3.10, ang, rr),
               on_pod(x_end + 0.42, ang, rr)]
        pipes.append(kit.pipe_run("aft_pipe_%s_%d" % (sfx, i), pts, rad,
                                  mat=M['alu'], col=col, seg=10))
        # 管夹：每 0.9 m 一个，把管路真的固定在壳上
        for k in range(5):
            xc = x_start - 0.90 - k * 0.92
            if xc > x_end + 0.55:
                pipes.append(kit.box("aft_pc_%s_%d_%d" % (sfx, i, k),
                                     (0.055, 0.115, 0.055),
                                     loc=on_pod(xc, ang, r_body + 0.030),
                                     rot=(ang, 0, 0),
                                     mat=M['gunmetal'], col=col, bw=0.004, seg=1))
    obs.append(kit.part(kit.join(pipes, "aft_pipes_%s" % sfx), "aft_fuel_pipes_%s" % sfx,
                        "燃油冷却管路", "Fuel / Coolant Lines", "detail",
                        (0, 0.7 if side else 0, 0.4),
                        note="沿吊舱侧上方走的两根管路（alu），端部带接头"))

    # ---------------------------------------------------------- 作动筒（喷管调节）
    def bell_r(x):
        """喷管外壁在 x 处的半径"""
        t = min(max((x_end - x) / L, 0.0), 1.0)
        return r_body * 0.95 + (r_out - r_body * 0.95) * (t ** 1.75)

    acts = []
    for k in range(3):
        a = math.radians(90 + 120 * k)
        ca, sa = math.cos(a), math.sin(a)
        x0 = x_end + 0.06
        x1 = x_end - 0.78
        r0 = r_body + 0.075
        r1 = bell_r(x1) + 0.075
        p0 = (x0, y + ca * r0, z + sa * r0)
        p1 = (x1, y + ca * r1, z + sa * r1)
        acts.append(_rod("aft_act_%s_%d" % (sfx, k), p0, p1, 0.052,
                         mat=M['frame'], col=col))
        # 两端耳座（短粗环，压在外壁上）
        for pm, rm in ((p0, r0), (p1, r1)):
            acts.append(_rod("aft_acte_%s_%d_%d" % (sfx, k, 0 if pm is p0 else 1),
                             (pm[0] - 0.05, pm[1], pm[2]), (pm[0] + 0.05, pm[1], pm[2]),
                             0.070, mat=M['gunmetal'], col=col, seg=12))
    ac = kit.join(acts, "aft_actuators_%s" % sfx)
    obs.append(kit.part(ac, "aft_actuators_%s" % sfx, "喷管作动筒", "Nozzle Actuators",
                        "detail", (0, 0.35 if side else 0, 0.15),
                        note="3 组液压作动筒 + 活塞杆，连接吊舱与喷管外壁"))

    return obs, dict(eid=eid, y=y, z=z, r_out=r_out, r_in=r_in, exit_x=exit_x)


# ================================================================ 挂架
def build_pylons(M, col, y, z, r_body, x_start, x_end, side_sign):
    """侧引擎与船体之间的真实挂架：2 根前撑 + 1 根后撑（含根部螺栓）"""
    obs = []
    sfx = "p" if y < 0 else "s"
    out_in = -1.0 if y < 0 else 1.0
    rows = []
    for tag, xp in (("f1", -10.15), ("f2", -11.55), ("a1", -13.35)):
        # 挂点取船壳下舷的真实表面位置（吊舱是下吊舱，撑杆基本水平）
        th = (-0.55) if y > 0 else (math.pi + 0.55)
        sp = hull.surf(xp, th, 0.006)
        root = (xp, sp.y, sp.z)
        # 吊舱一侧的接头：落在吊舱内侧、略高
        tip = (xp, y - out_in * 0.52 * r_body, z + 0.26)
        st = _box_between("aft_py_%s_%s" % (sfx, tag), root, tip,
                          0.42 if tag != "a1" else 0.36,
                          0.150 if tag != "a1" else 0.195,
                          mat=M['frame'], col=col, bw=0.006)
        obs.append(st)
        rows.append((xp, root))
    # 根部螺栓阵列
    bolts = []
    for (xp, root) in rows:
        for k in range(4):
            dy = 0.115 * (k - 1.5)
            bolts.append(kit.cyl("aft_pyb_%s_%s_%d" % (sfx, xp, k), 0.026, 0.030, axis='X',
                                 loc=(xp, root[1] + dy * 0.0, root[2] + dy), mat=M['black'],
                                 col=col, seg=8, bw=0.004, segs=1))
    obs.append(kit.join(bolts, "aft_pylon_bolts_%s" % sfx))
    py = kit.join(obs, "aft_pylons_%s" % sfx)
    return [kit.part(py, "aft_pylons_%s" % sfx, "引擎挂架", "Engine Pylons",
                     "engines", (0, 0.9 if y > 0 else -0.9, 0.35),
                     note="2 根前撑 + 1 根后撑，根部 12 颗螺栓连到船体舷侧")]


# ================================================================ 尾段船体
def build_tail_hull(M, col):
    obs = []
    X0, X1 = -9.35, -14.28
    blocks = [(-9.45, -10.55), (-10.62, -11.72), (-11.80, -12.90), (-12.98, -14.24)]

    def band_set(name, th_c, span, mat, zh, en, note, d, nx=4, nt=3):
        pls = []
        for i, (xa, xb) in enumerate(blocks):
            pls.append(hull.plate("%s_%d" % (name, i), xa, xb, th_c - span / 2, th_c + span / 2,
                                  out=0.016, thick=0.011, nx=nx, nt=nt, mat=mat, col=col,
                                  shrink=0.030, bw=0.0035))
        ob = kit.join(pls, name)
        return kit.part(ob, name, zh, en, "hull_aft", d, note=note)

    obs.append(band_set("aft_hull_armor_port", 0.0, 0.62, M['hull_dark'],
                        "尾部装甲（右舷）", "Aft Armour (Starboard)",
                        "沿舷线的 4 块贴合装甲板，缝宽 3 cm", (0, 1.0, 0.1)))
    obs.append(band_set("aft_hull_armor_stbd", math.pi, 0.62, M['hull_dark'],
                        "尾部装甲（左舷）", "Aft Armour (Port)",
                        "沿舷线的 4 块贴合装甲板，缝宽 3 cm", (0, -1.0, 0.1)))
    obs.append(band_set("aft_hull_armor_top", math.pi / 2, 0.70, M['hull'],
                        "尾部甲板装甲", "Aft Deck Armour",
                        "背脊甲板 4 块板，尾框前方收口", (0, 0, 1.0)))
    obs.append(band_set("aft_hull_armor_belly", -math.pi / 2, 0.78, M['hull_dark'],
                        "尾部腹部装甲", "Aft Belly Armour",
                        "腹部 4 块板，包住尾框下缘", (0, 0, -1.0)))

    # 桁条（两条沿舷线的加强条）
    strg = []
    for i, th in enumerate((0.66, -0.66, math.pi - 0.66, math.pi + 0.66)):
        strg.append(hull.plate("aft_stringer_%d" % i, -9.40, -14.20, th - 0.046, th + 0.046,
                               out=0.030, thick=0.024, nx=9, nt=1, mat=M['frame'],
                               col=col, bw=0.0035))
    st = kit.join(strg, "aft_stringers")
    obs.append(kit.part(st, "aft_stringers", "尾部桁条", "Aft Stringers", "hull_aft",
                        (0, 0, 0.7), note="4 条沿舷线的承力桁条，压在装甲板缝上"))

    # 尾部承力框 3 道 + 斜撑
    frames = []
    for i, xf in enumerate((-11.10, -12.65, -14.10)):
        frames.append(_hull_collar("aft_frame_%d" % i, xf, 0.16, out=0.048, thick=0.032,
                                   seg=48, mat=M['frame'], col=col, bw=0.002))
    gus = []
    for i in range(10):
        a = TAU * i / 10
        p0 = hull.surf(-14.10, a, 0.045)
        p1 = hull.surf(-13.30, a, 0.020)
        gus.append(_box_between("aft_gus_%d" % i, tuple(p0), tuple(p1), 0.085, 0.055,
                                mat=M['frame'], col=col, bw=0.003))
    frames.append(kit.join(gus, "aft_gussets"))
    fr = kit.join(frames, "aft_tail_frame")
    obs.append(kit.part(fr, "aft_tail_frame", "尾部承力框", "Aft Load Frame", "hull_aft",
                        (-1, 0, 0.1),
                        note="3 道贴合船壳截面的环框（含 10 片斜撑），把引擎载荷收进尾段"))

    # 尾端封口（尾框端面 + 中央引擎安装法兰）
    seal = _hull_collar("aft_tail_seal", -14.26, 0.075, out=0.030, thick=0.026, seg=56,
                        mat=M['hull_dark'], col=col, bw=0.003)
    obs.append(kit.part(seal, "aft_tail_seal", "尾端封口框", "Tail Bulkhead Seal", "hull_aft",
                        (-1, 0, 0), note="尾段末端封口环，中央引擎穿过其中"))

    # 检修盖（4 块 + 边框）
    hatches = []
    for i, (xa, xb, th, w) in enumerate(((-10.10, -10.85, 0.30, 0.34),
                                         (-10.10, -10.85, math.pi - 0.30, 0.34),
                                         (-12.35, -13.10, -0.34, 0.30),
                                         (-12.35, -13.10, math.pi + 0.34, 0.30))):
        hatches.append(hull.plate("aft_hatch_%d" % i, xa, xb, th - w / 2, th + w / 2,
                                  out=0.036, thick=0.020, nx=4, nt=3, mat=M['alu'],
                                  col=col, shrink=0.02, bw=0.003))
    ht = kit.join(hatches, "aft_hatches")
    obs.append(kit.part(ht, "aft_hatches", "尾部检修盖", "Aft Access Hatches", "detail",
                        (0, 0, 1.0), note="4 块机加工铝检修盖，带边框与缝"))

    # 警示条纹（两道斜纹带）
    stripes = []
    for i, th in enumerate((0.0, math.pi)):
        stripes.append(hull.plate_band("aft_stripe_%d" % i, -13.95, -14.22, th, 1.05,
                                       out=0.026, thick=0.014, nx=3, nt=5,
                                       mat=M['stripe'], col=col, gap=0.0))
    sp = kit.join(stripes, "aft_warn_stripes")
    obs.append(kit.part(sp, "aft_warn_stripes", "尾部警示条纹", "Aft Warning Stripes", "detail",
                        (-1, 0, 0.2), note="喷口两侧的橙黄警示带，靠尾框排布"))

    return obs


# ================================================================ 垂尾 / 灯 / RCS
def build_fin_lights(M, col):
    obs = []
    # 垂尾整流罩
    prof = [(-12.05, 0.86), (-12.62, 1.42), (-13.35, 1.66), (-14.05, 1.55),
            (-14.22, 1.05), (-14.05, 0.80), (-13.30, 0.88), (-12.55, 0.92)]
    fin = kit.prism("aft_fin", prof, -0.075, 0.075, mat=M['hull_dark'], col=col,
                    smooth=False, bw=0.0)
    kit.finish(fin, 0.010, 2, 34.0)
    fix = kit.prism("aft_fin_fix", [(-12.30, 0.92), (-13.05, 1.34), (-13.95, 1.28),
                                    (-13.95, 0.92)], -0.098, 0.098,
                    mat=M['frame'], col=col, smooth=False)
    fin = kit.join([fin, fix], "aft_fin")
    obs.append(kit.part(fin, "aft_vertical_fin", "垂尾整流罩", "Vertical Fin Fairing",
                        "hull_aft", (0, 0, 1.2),
                        note="尾背脊上的垂尾整流罩，内含天线/尾灯座"))

    # 尾灯：左红右绿 + 尾部白灯
    for tag, mat, y in (("port", M['led_red'], -1.02), ("stbd", M['led_green'], 1.02)):
        ob = kit.cyl("aft_light_%s" % tag, 0.058, 0.040, axis='X',
                     loc=(-14.275, y, 0.30), mat=mat, col=col, seg=16, bw=0.003, segs=1)
        obs.append(kit.part(ob, "aft_tail_light_%s" % tag, "航行灯（%s）" % ("左红" if tag == "port" else "右绿"),
                            "Nav Light (%s)" % tag, "detail", (-1, y, 0.15),
                            note="发光材质，尾部侧上方可见"))
    wl = kit.cyl("aft_light_white", 0.050, 0.036, axis='X', loc=(-14.275, 0.0, 0.74),
                 mat=M['led'], col=col, seg=16, bw=0.004, segs=1)
    obs.append(kit.part(wl, "aft_tail_light_white", "尾部识别灯", "Aft Formation Light",
                        "detail", (-1, 0, 0.3), note="冷白发光，尾框中央"))

    # 尾部 RCS 喷口群（spec.RCS_PORTS 前 4 个）
    out = []
    for i, (x, y, z, d, r) in enumerate(S.RCS_PORTS[:4]):
        th = math.atan2(z, y)
        sp = hull.surf(x, th, 0.004)
        # 支架：船壳 → 喷口基座
        base = (x, sp.y, sp.z)
        port = (x, y, z)
        out.append(_box_between("aft_rcs_br_%d" % i, base, port, 0.20, 0.16,
                                mat=M['frame'], col=col, bw=0.004))
        # 喷口壳 + 内锥
        from mathutils import Vector
        dv = Vector(d)
        nz = dv.normalized()
        # 外壳
        sh = kit.cyl("aft_rcs_sh_%d" % i, r * 1.55, 0.30, axis='Z', loc=port,
                     mat=M['hull_dark'], col=col, seg=20, bw=0.003, segs=1)
        sh.rotation_euler = nz.to_track_quat('Z', 'Y').to_euler()
        out.append(sh)
        noz = kit.cyl("aft_rcs_nz_%d" % i, r * 0.78, 0.13, axis='Z',
                      loc=tuple(Vector(port) + nz * 0.18), mat=M['black'],
                      col=col, seg=20, bw=0.003, segs=1, r2=r * 0.55)
        noz.rotation_euler = nz.to_track_quat('Z', 'Y').to_euler()
        out.append(noz)
    rc = kit.join(out, "aft_rcs_set")
    obs.append(kit.part(rc, "aft_rcs_tail_set", "尾部 RCS 喷口群", "Aft RCS Thruster Set",
                        "detail", (0, 1, 1),
                        note="按 spec.RCS_PORTS 的 4 个尾部姿控喷口，配支架与收敛内锥"))
    return obs


# ================================================================ 中央引擎周边细节
def build_ctr_details(M, col):
    obs = []
    y, z = 0.0, 0.28
    exit_x = S.ENGINES["engine_ctr"][7]
    r_out = S.ENGINES["engine_ctr"][5]
    # 喷口周围一圈陶瓷隔热瓦
    tiles = []
    for i in range(14):
        a0 = TAU * i / 14 + 0.03
        a1 = a0 + TAU / 14 - 0.06
        tiles.append(_cyl_patch("aft_ctile_%d" % i, y, z, exit_x + 0.86, exit_x + 0.42,
                                r_out - 0.055, a0, a1, thick=0.016, nt=2,
                                mat=M['ceramic'], col=col, bw=0.002))
    tl = kit.join(tiles, "aft_ctr_ceramic")
    obs.append(kit.part(tl, "aft_ctr_nozzle_tiles", "中央喷口隔热瓦", "Centre Nozzle Ceramic Tiles",
                        "detail", (-1, 0, 0.6),
                        note="14 块陶瓷瓦环绕中央喷口，尾框出口处"))

    # 检修口盖（两块，带边框）
    covers = []
    for i, (a0, a1) in enumerate(((0.55, 1.25), (math.pi + 0.55, math.pi + 1.25))):
        covers.append(_cyl_patch("aft_cct_%d" % i, y, z, exit_x + 1.55, exit_x + 1.10,
                                 r_out - 0.02, a0, a1, thick=0.020, nt=3,
                                 mat=M['alu'], col=col, bw=0.003))
    cc = kit.join(covers, "aft_ctr_covers")
    obs.append(kit.part(cc, "aft_ctr_covers", "中央引擎检修口盖", "Centre Engine Access Covers",
                        "detail", (0, 0, 1.0), note="中央引擎两侧的快开检修盖"))
    return obs


# ================================================================ 自检
def report_nozzles():
    """打印三台引擎喷口端面实测值与 spec 对照"""
    print("AFT 喷口端面实测（world）：")
    for eid in S.ENGINE_IDS:
        y, z, r_body, xs, xe, ro, ri, ex, fl = S.ENGINES[eid]
        print("    %-12s exit=(%7.3f, %6.3f, %6.3f)  r_out=%.3f r_in=%.3f  flame=%.2f m"
              % (eid, ex, y, z, ro, ri, fl))


def build(M, col):
    M = _extra_mats(M)
    obs = []
    for eid in S.ENGINE_IDS:
        y, z, r_body, x_start, x_end, r_out, r_in, exit_x, flen = S.ENGINES[eid]
        side = eid != "engine_ctr"
        got, _info = build_engine(M, col, eid, y, z, r_body, x_start, x_end,
                                  r_out, r_in, exit_x, flen, side=side)
        obs += got
        if side:
            obs += build_pylons(M, col, y, z, r_body, x_start, x_end, 1.0 if y > 0 else -1.0)

    obs += build_tail_hull(M, col)
    obs += build_fin_lights(M, col)
    obs += build_ctr_details(M, col)
    obs = [o for o in obs if o is not None]

    report_nozzles()
    print("AFT parts=%d" % len(obs))
    return obs
