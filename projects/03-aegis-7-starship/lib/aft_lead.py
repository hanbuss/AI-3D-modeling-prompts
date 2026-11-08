"""starship/lib/aft_lead.py — 动力段「保底实现」（Lead 兜底，aft.py/fx.py 到位后自动让位）

build.py 的规则：
  lib/aft.py 存在 → 用 aft.py；否则用本文件 aft_lead.build()
  lib/fx.py  存在 → 用 fx.py ；否则用本文件 fx_lead.build()

所以这里必须自成体系：三台主引擎 + 喷管内部（叶片环/中心锥）+ 挂架 + 尾部装甲 + 尾焰 + 激光。
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix

import kit
import hull
import spec as S

TAU = math.tau


# ------------------------------------------------------------------ 回转体
def lathe(name, prof, x_axis_center, seg=48, mat=None, col=None, close=True, smooth=True, bw=0.004):
    """沿 X 轴回转：prof = [(x, r), ...]（r>0 外壳，r<0 内壳由调用方给）"""
    bm = bmesh.new()
    rings = []
    cy, cz = x_axis_center
    for (x, r) in prof:
        ring = []
        for i in range(seg):
            a = TAU * i / seg
            ring.append(bm.verts.new((x, cy + r * math.cos(a), cz + r * math.sin(a))))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    if close:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=smooth)
    if bw:
        kit.bevel(ob, bw, 1, 45)
        kit.apply_modifiers(ob)
    return ob


def shell_ring(name, y, z, x0, x1, r, seg=40, mat=None, col=None):
    """把 [x0,x1] 区间的回转外壳（用于吊舱筒体）"""
    return lathe(name, [(x0, r), (x1, r)], (y, z), seg=seg, mat=mat, col=col, close=False)


# ------------------------------------------------------------------ 引擎
def engine(eid, M, col):
    y, z, r_body, xs, xe, br_out, br_in, exit_x, flen = S.ENGINES[eid]
    tag = eid.replace("engine_", "")
    out = []
    # 1) 吊舱主体：进气唇（前）→ 等直段 → 收敛段
    prof = [
        (xs + 0.55, r_body * 0.62),
        (xs + 0.30, r_body * 0.94),
        (xs, r_body * 1.00),
        (xs - 0.9, r_body * 1.04),
        (xs - 2.2, r_body * 1.02),
        (xe + 1.1, r_body * 0.99),
        (xe + 0.35, r_body * 0.92),
        (xe, r_body * 0.86),
    ]
    body = lathe("%s_nacelle" % eid, prof, (y, z), seg=44, mat=M['hull'], col=col,
                 close=True, bw=0.006)
    kit.part(body, "eng_%s_nacelle" % tag, "%s引擎吊舱" % tag.upper(), "Engine Nacelle " + tag,
             "engines", (-1, 0, 0), note="主引擎筒体：进气唇 + 等直段 + 收敛段")
    out.append(body)

    # 2) 环形加强箍
    ribs = []
    n_rib = 7
    for i in range(n_rib):
        t = i / (n_rib - 1)
        x = xs - 0.35 - t * (abs(xe - xs) - 1.0)
        rr = r_body * (1.03 if t < 0.7 else 0.98)
        ribs.append(lathe("%s_rib%d" % (eid, i),
                          [(x - 0.045, rr + 0.012), (x + 0.045, rr + 0.012)],
                          (y, z), seg=40, mat=M['frame'], col=col, close=False, bw=0.002))
    rib = kit.join(ribs, "eng_%s_ribs" % tag)
    kit.part(rib, "eng_%s_ribs" % tag, "%s引擎加强箍" % tag.upper(), "Engine Ribs " + tag,
             "engines", (-1, 0, 0), note="7 道环形加强箍")
    out.append(rib)

    # 3) 喷管：收敛-扩张（bell），外壁
    bell_prof = [
        (xe, br_out * 0.70),
        (xe - 0.30, br_out * 0.86),
        (exit_x + 0.55, br_out * 0.99),
        (exit_x + 0.18, br_out * 1.00),
        (exit_x, br_out * 0.99),
    ]
    bell = lathe("eng_%s_bell" % tag, bell_prof, (y, z), seg=48, mat=M['heat_steel'],
                 col=col, close=False, bw=0.004)
    kit.part(bell, "eng_%s_bell" % tag, "%s喷管外壁" % tag.upper(), "Nozzle Shell " + tag,
             "engines", (-1, 0, 0), note="收敛-扩张喷管外壁，热区钢")
    out.append(bell)

    # 4) 喷管内壁（陶瓷）+ 出口唇缘
    inner = lathe("eng_%s_bell_in" % tag,
                  [(xe - 0.05, br_in * 0.72), (exit_x + 0.5, br_in * 0.97), (exit_x, br_in * 1.0)],
                  (y, z), seg=44, mat=M['ceramic'], col=col, close=False, bw=0.002)
    lip = lathe("eng_%s_lip" % tag,
                [(exit_x + 0.03, br_out * 0.995), (exit_x - 0.02, br_in * 1.0)],
                (y, z), seg=48, mat=M['black'], col=col, close=True, bw=0.002)
    inner = kit.join([inner, lip], "eng_%s_nozzle_in" % tag)
    kit.part(inner, "eng_%s_nozzle_in" % tag, "%s喷管内壁" % tag.upper(), "Nozzle Liner " + tag,
             "engines", (-1, 0, 0), note="陶瓷内衬 + 黑色出口唇缘")
    out.append(inner)

    # 5) 涡轮静子叶片环 ×2（每环 24 片真实叶片）
    blades = []
    for k, xb in enumerate((xe - 0.55, xe - 1.05)):
        rr = br_in * (0.86 if k == 0 else 0.92)
        for i in range(24):
            a = TAU * i / 24
            b = kit.box("eng_%s_bl%d_%d" % (tag, k, i), (0.075, 0.016, rr * 0.30),
                        loc=(xb, y + (rr * 0.62) * math.cos(a), z + (rr * 0.62) * math.sin(a)),
                        mat=M['alu'], col=col, bw=0.0012, seg=1)
            b.rotation_euler = (a, math.radians(22), 0)
            blades.append(b)
    blade = kit.join(blades, "eng_%s_blades" % tag)
    kit.part(blade, "eng_%s_blades" % tag, "%s涡轮静子叶片" % tag.upper(), "Turbine Stators " + tag,
             "engines", (-1, 0, 0), note="2 级静子 × 24 片，加力燃烧室前")
    out.append(blade)

    # 6) 中心锥（加力燃烧室火焰稳定器 + 尾锥）
    cone = lathe("eng_%s_cone" % tag,
                 [(xe - 0.75, br_in * 0.30), (xe - 0.25, br_in * 0.26),
                  (exit_x + 0.35, br_in * 0.12), (exit_x - 0.02, br_in * 0.02)],
                 (y, z), seg=32, mat=M['heat_steel'], col=col, close=True, bw=0.003)
    kit.part(cone, "eng_%s_cone" % tag, "%s中心锥" % tag.upper(), "Center Cone " + tag,
             "engines", (-1, 0, 0), note="加力燃烧室中心锥")
    out.append(cone)

    # 7) 挂架：吊舱顶部 → 船体（3 根）
    pyl = []
    for i, (dx, h) in enumerate(((-0.5, 1.0), (-2.0, 1.0), (-3.4, 0.9))):
        x = xs + 0.2 + dx * 1.6
        _, ztop = hull.surface_yz(x, math.pi / 2) if False else (None, None)
        w, ht, hb = hull.sect(x)
        p = kit.box("eng_%s_pyl%d" % (tag, i), (0.30, 0.16, max(0.25, h)),
                    loc=(x, y * 0.86, z + r_body * 0.72), mat=M['frame'], col=col, bw=0.004, seg=1)
        p.rotation_euler = (0, math.radians(-6), 0)
        pyl.append(p)
    pylons = kit.join(pyl, "eng_%s_pylons" % tag)
    kit.part(pylons, "eng_%s_pylons" % tag, "%s引擎挂架" % tag.upper(), "Engine Pylons " + tag,
             "engines", (-1, 0, 0), note="3 根承力挂架连接船体")
    out.append(pylons)

    # 8) 隔热瓦（局部块）
    tiles = []
    for i in range(9):
        a = TAU * i / 9 + 0.2
        tiles.append(kit.box("eng_%s_tile%d" % (tag, i), (0.42, 0.05, 0.20),
                             loc=(xe + 0.9, y + (r_body * 1.01) * math.cos(a),
                                  z + (r_body * 1.01) * math.sin(a)),
                             mat=M['foil'], col=col, bw=0.002, seg=1))
        tiles[-1].rotation_euler = (a, 0, 0)
    tile = kit.join(tiles, "eng_%s_tiles" % tag)
    kit.part(tile, "eng_%s_tiles" % tag, "%s隔热瓦" % tag.upper(), "Heat Tiles " + tag,
             "engines", (-1, 0, 0), note="喷口前的多层隔热瓦")
    out.append(tile)
    return out


def aft_hull(M, col):
    """尾段装甲 + 尾框 + RCS + 尾灯"""
    out = []
    # 尾框环
    w, ht, hb = hull.sect(S.TAIL_X + 0.15)
    frame = lathe("aft_frame",
                  [(S.TAIL_X + 0.28, 1.0), (S.TAIL_X + 0.06, 0.995)],
                  (0, (ht - hb) / 2), seg=48, mat=M['frame'], col=col, close=False, bw=0.004)
    # 尾框是椭圆近似：按船体剖面重新做一段"尾段端面加强环"
    bpy.data.objects.remove(frame, do_unlink=True)
    rings = []
    for x in (S.TAIL_X + 0.30, S.TAIL_X + 0.10):
        rings.append((x, hull.ring(x)))
    fr = kit.loft("aft_frame", rings, mat=M['frame'], col=col, close_start=False, close_end=False)
    kit.bevel(fr, 0.006, 1, 45)
    kit.apply_modifiers(fr)
    kit.part(fr, "aft_frame", "尾段承力框", "Aft Bulkhead Frame", "hull_aft", (-1, 0, 0),
             note="尾框：三台引擎的安装基准")
    out.append(fr)

    # 尾部装甲板（左右舷 + 腹部）
    plates = []
    for i, (x0, x1) in enumerate([(-9.45, -11.2), (-11.3, -13.0), (-13.1, -14.2)]):
        zc = -0.05 - 0.02 * i
        for th, sgn in ((0.0, 1), (math.pi, -1)):
            plates.append(hull.plate("aft_pl_%d_%d" % (i, sgn), x0, x1,
                                     th + sgn * 0.05, th + sgn * 0.30,
                                     out=0.014, thick=0.010, nx=5, nt=3,
                                     mat=(M['hull'] if i % 2 == 0 else M['hull_dark']),
                                     col=col, shrink=0.008))
    pl = kit.join(plates, "aft_plates")
    kit.part(pl, "aft_plates", "尾段装甲板", "Aft Armor Plating", "hull_aft", (-1, 0, 0),
             note="尾段分块装甲：3 段 × 左右舷")
    out.append(pl)

    # 尾部 RCS（4 个）
    rcs = []
    for (x, yy, zz, d, r) in S.RCS_PORTS[2:]:
        c = kit.cyl("aft_rcs_%d" % len(rcs), r, 0.16, axis='Z', loc=(x, yy, zz),
                    mat=M['black'], col=col, seg=16, bw=0.002, segs=1, r2=r * 0.72)
        c.rotation_euler = Vector(d).to_track_quat('Z', 'Y').to_euler()
        rcs.append(c)
    rc = kit.join(rcs, "aft_rcs")
    kit.part(rc, "aft_rcs", "尾部姿控喷口", "Aft RCS Cluster", "hull_aft", (-1, 0, 0),
             note="4 个 RCS 姿控喷口")
    out.append(rc)

    # 尾灯
    lights = []
    for i, (yy, zz) in enumerate(((1.05, 0.62), (-1.05, 0.62))):
        lights.append(kit.cyl("aft_nav_%d" % i, 0.075, 0.07, axis='X',
                              loc=(S.TAIL_X - 0.02, yy, zz), mat=M['led_red'], col=col,
                              seg=12, bw=0.001, segs=1))
    ln = kit.join(lights, "aft_nav")
    kit.part(ln, "aft_nav", "尾部航行灯", "Aft Nav Lights", "hull_aft", (-1, 0, 0),
             note="尾部红色航行灯")
    out.append(ln)
    return out


def build(M, col):
    out = []
    for eid in S.ENGINE_IDS:
        out += engine(eid, M, col)
    out += aft_hull(M, col)
    print("AFT_LEAD parts=%d" % len(out))
    return out


# ------------------------------------------------------------------ 尾焰 / 激光
def cone_fx(name, x0, x1, r0, r1, mat, col, seg=28, smooth=True):
    return lathe(name, [(x0, r0), (x1, r1)], (0, 0), seg=seg, mat=mat, col=col,
                 close=False, smooth=smooth, bw=0)


def build_fx(M, col):
    out = []
    for eid in S.ENGINE_IDS:
        y, z, r_body, xs, xe, br_out, br_in, exit_x, flen = S.ENGINES[eid]
        tag = eid.replace("engine_", "")
        layers = [
            ("core", br_in * 0.52, flen * 0.62, M['engine_core'], 0.55),
            ("mid", br_in * 0.80, flen * 0.85, M['engine_ring'], 0.38),
            ("outer", br_in * 1.02, flen * 1.00, M['laser_glow'], 0.22),
        ]
        for nm, r0, ln, mat, taper in layers:
            prof = [
                (exit_x + 0.02, r0),
                (exit_x - ln * 0.18, r0 * 1.06),
                (exit_x - ln * 0.55, r0 * 0.72),
                (exit_x - ln, r0 * taper * 0.25),
            ]
            ob = lathe("fx_%s_flame_%s" % (tag, nm), prof, (y, z), seg=26, mat=mat,
                       col=col, close=False, smooth=True, bw=0)
            kit.part(ob, "fx_flame_%s_%s" % (tag, nm),
                     "%s尾焰·%s" % (tag.upper(), {"core": "内芯", "mid": "中层", "outer": "外焰"}[nm]),
                     "Plume %s %s" % (tag, nm), "detail", (-1, 0, 0),
                     note="尾焰网格（Three.js 侧会用 shader 重建，Blender 侧用于出图）")
            out.append(ob)

    # 激光束：从炮塔沿 +X
    t = S.TURRET_DORSAL
    p0 = (t['x'] + 0.9, t['y'], t['z'] + 0.55)
    for nm, r, mat in (("core", 0.030, M['laser']), ("glow", 0.105, M['laser_glow'])):
        prof = [(p0[0], r), (p0[0] + 60.0, r)]
        ob = lathe("fx_laser_%s" % nm, prof, (p0[1], p0[2]), seg=16, mat=mat, col=col,
                   close=True, smooth=True, bw=0)
        kit.part(ob, "fx_laser_%s" % nm, "激光束·%s" % ("内芯" if nm == "core" else "外层"),
                 "Laser Beam %s" % nm, "detail", (1, 0, 0),
                 note="从背脊炮塔射出的激光束（60 m）")
        out.append(ob)
    print("FX_LEAD parts=%d" % len(out))
    return out
