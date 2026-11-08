"""starship/lib/weapons.py — 背脊双联激光炮塔 / 腹部 6 管转管炮 / 翼下挂架 + 4 枚导弹

坐标系：+X 舰首、+Y 右舷、+Z 上。
关键对位（红线，别改）：
  TURRET_DORSAL  base 圆心 = (2.60, 0.00, 1.42)，炮管沿 +X 前指；
  GATLING_VENTRAL base = (4.20, 0.00, -1.30)，6 管转管炮前指；
  PYLONS 的 y 是右舷站位，左舷镜像；导弹挂在翼面下方，位置由 wings.skin() 反算，不会浮空。
"""
import math
import bpy, bmesh
from mathutils import Vector

import kit
import hull
import wings as WG
import spec as S

TAU = math.tau


# ---------------------------------------------------------------- 通用小件
def _ring_profile(n, r, cx=0.0, cy=0.0, plane='xy'):
    pts = []
    for i in range(n):
        a = TAU * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _loft(name, rings, mat=None, col=None, smooth=True, cap=True):
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(vr[0])
    for a, b in zip(vr[:-1], vr[1:]):
        for i in range(n):
            try:
                bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            except ValueError:
                pass
    if cap:
        for ring in (list(reversed(vr[0])), vr[-1]):
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col, smooth=smooth)


def _ring_x(name, x, r, cy, cz, n=20, mat=None, col=None):
    return [Vector((x, cy + r * math.cos(TAU * i / n), cz + r * math.sin(TAU * i / n)))
            for i in range(n)]


def _plate(name, q, nrm, t, mat=None, col=None):
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


def _bolt(name, p, r=0.020, h=0.016, axis='Z', mat=None, col=None, seg=6):
    return kit.cyl(name, r, h, axis=axis, loc=(p[0], p[1], p[2]), mat=mat, col=col,
                   seg=seg, bw=0, segs=1)


def _superellipse(L, W, n=14, p=2.6):
    """平面流线外形（长 L、宽 W），返回 [(x,y)]，用于挂架平面"""
    pts = []
    for i in range(n):
        a = TAU * i / n
        c, s = math.cos(a), math.sin(a)
        x = L * 0.5 * math.copysign(abs(c) ** (2.0 / p), c)
        y = W * 0.5 * math.copysign(abs(s) ** (2.0 / p), s)
        pts.append((x, y))
    return pts


# ================================================================ 背脊双联激光炮塔
def _turret(M, col):
    T = S.TURRET_DORSAL
    x0, y0, z0 = T['x'], T['y'], T['z']
    Rb, Rh = T['base_r'], T['ring_h']
    deck = hull.deck_z(x0)
    base, head = [], []

    # ---- 环形基座（固定环 + 齿圈 + 螺栓 + 装甲裙）
    # 基座法兰：底面压进甲板 1 cm（deck = 1.4033），外缘再补一圈焊环，杜绝"悬空缝"
    base.append(kit.cyl("tb_floor", Rb * 1.02, 0.11, axis='Z',
                        loc=(x0, y0, deck - 0.01 + 0.055), mat=M['gunmetal'], col=col,
                        seg=40, bw=0.004, segs=2))
    base.append(kit.tube("tb_weld", Rb * 1.03, Rb * 0.90, 0.030, axis='Z',
                         loc=(x0, y0, deck + 0.008), mat=M['frame'], col=col, seg=40))
    base.append(kit.tube("tb_race", Rb, Rb * 0.80, Rh * 0.72, axis='Z',
                         loc=(x0, y0, z0 + Rh * 0.40), mat=M['frame'], col=col, seg=40))
    # 齿圈（一圈小齿，读起来像回转驱动）
    for i in range(36):
        a = TAU * i / 36
        base.append(kit.box("tb_tooth%d" % i, (0.042, 0.030, 0.045),
                            loc=(x0 + (Rb * 0.885) * math.cos(a),
                                 y0 + (Rb * 0.885) * math.sin(a), z0 + Rh * 0.40),
                            rot=(0, 0, a), mat=M['frame'], col=col, bw=0.0012, seg=1))
    # 固定部装甲裙（4 段弧形板）
    for i in range(4):
        a = TAU * i / 4 + math.pi / 4
        base.append(kit.box("tb_skirt%d" % i, (0.10, 0.46, 0.20),
                            loc=(x0 + Rb * 0.92 * math.cos(a),
                                 y0 + Rb * 0.92 * math.sin(a), z0 + 0.10),
                            rot=(0, 0, a), mat=M['hull_dark'], col=col, bw=0.003, seg=1))
    # 基座地脚 + 螺栓 16 颗
    for i in range(16):
        a = TAU * i / 16
        base.append(_bolt("tb_bolt%d" % i,
                          (x0 + Rb * 0.95 * math.cos(a), y0 + Rb * 0.95 * math.sin(a),
                           z0 + 0.005), 0.020, 0.018, 'Z', M['alu'], col))
    # 走线护罩（从基座后方下到甲板）
    base.append(kit.box("tb_conduit", (0.22, 0.16, 0.16),
                        loc=(x0 - Rb * 0.72, y0, z0 - 0.06),
                        mat=M['black'], col=col, bw=0.004, seg=1))

    # ---- 转动塔身（俯仰轴 + 伺服 + 护罩 + 双炮管 + 激光透镜）
    zt = z0 + Rh * 0.86                     # 回转体底面
    body_h = 0.34
    head.append(kit.cyl("th_body", 0.46, body_h, axis='Z',
                        loc=(x0, y0, zt + body_h / 2), mat=M['gunmetal'], col=col,
                        seg=32, bw=0.006, segs=2))
    head.append(kit.cyl("th_cap", 0.40, 0.07, axis='Z',
                        loc=(x0, y0, zt + body_h + 0.03), mat=M['frame'], col=col,
                        seg=32, bw=0.004, segs=2))
    # 炮塔正面装甲护罩（斜板 + 侧颊）
    head.append(_plate("th_shield",
                       [Vector((x0 + 0.44, -0.34, zt + body_h - 0.02)),
                        Vector((x0 + 0.44, 0.34, zt + body_h - 0.02)),
                        Vector((x0 + 0.30, 0.30, zt - 0.02)),
                        Vector((x0 + 0.30, -0.30, zt - 0.02))],
                       Vector((1, 0, 0.55)), 0.05, M['hull_dark'], col))
    for sgn in (-1, 1):
        head.append(_plate("th_cheek%d" % sgn,
                           [Vector((x0 + 0.40, sgn * 0.36, zt + body_h - 0.04)),
                            Vector((x0 - 0.26, sgn * 0.36, zt + body_h - 0.04)),
                            Vector((x0 - 0.26, sgn * 0.32, zt + 0.02)),
                            Vector((x0 + 0.36, sgn * 0.32, zt + 0.02))],
                           Vector((0, sgn, 0)), 0.035, M['hull_dark'], col))

    zc = zt + body_h * 0.58                  # 俯仰轴高度
    # 俯仰轴（左右耳轴）+ 伺服电机
    for sgn in (-1, 1):
        head.append(kit.cyl("th_trunnion%d" % sgn, 0.075, 0.20, axis='Y',
                            loc=(x0 + 0.10, sgn * 0.46, zc), mat=M['alu'], col=col,
                            seg=16, bw=0.003, segs=2))
        head.append(kit.cyl("th_servo%d" % sgn, 0.105, 0.22, axis='Y',
                            loc=(x0 - 0.14, sgn * 0.50, zc), mat=M['black'], col=col,
                            seg=16, bw=0.003, segs=2))
        head.append(kit.box("th_servomnt%d" % sgn, (0.26, 0.10, 0.26),
                            loc=(x0 - 0.14, sgn * 0.40, zc),
                            mat=M['gunmetal'], col=col, bw=0.002, seg=1))
    # 俯仰体（炮管安装座）+ 后部配重/供弹包
    head.append(kit.box("th_cradle", (0.52, 0.42, 0.30),
                        loc=(x0 + 0.20, y0, zc),
                        mat=M['gunmetal'], col=col, bw=0.006, seg=2))
    head.append(kit.cyl("th_feed", 0.13, 0.42, axis='X',
                        loc=(x0 - 0.16, y0, zc + 0.02), mat=M['black'], col=col,
                        seg=16, bw=0.003, segs=1))

    # 双炮管
    for sgn in (-1, 1):
        by = y0 + sgn * 0.125
        head.append(kit.cyl("th_jacket%d" % sgn, 0.082, 0.42, axis='X',
                            loc=(x0 + 0.44, by, zc), mat=M['frame'], col=col,
                            seg=18, bw=0.004, segs=2))
        for k in range(4):                    # 散热环
            head.append(kit.cyl("th_ring%d_%d" % (sgn, k), 0.094, 0.030, axis='X',
                                loc=(x0 + 0.32 + 0.055 * k, by, zc), mat=M['alu'], col=col,
                                seg=18, bw=0.002, segs=1))
        head.append(kit.cyl("th_barrel%d" % sgn, 0.052, 0.92, axis='X',
                            loc=(x0 + 1.10, by, zc), mat=M['gunmetal'], col=col,
                            seg=18, bw=0.003, segs=2))
        head.append(kit.tube("th_muzzle%d" % sgn, 0.070, 0.050, 0.09, axis='X',
                             loc=(x0 + 1.53, by, zc), mat=M['black'], col=col, seg=18))
        # 发光透镜（凹进炮口）
        head.append(kit.cyl("th_lens%d" % sgn, 0.044, 0.020, axis='X',
                            loc=(x0 + 1.545, by, zc), mat=M['laser'], col=col,
                            seg=18, bw=0.0015, segs=1))
        head.append(kit.tube("th_lensring%d" % sgn, 0.060, 0.046, 0.014, axis='X',
                             loc=(x0 + 1.552, by, zc), mat=M['laser_glow'], col=col, seg=18))
        # 炮管支撑卡箍（连到俯仰体）
        head.append(kit.box("th_clamp%d" % sgn, (0.07, 0.10, 0.12),
                            loc=(x0 + 0.60, by, zc - 0.08),
                            mat=M['gunmetal'], col=col, bw=0.002, seg=1))

    # 顶部光电球 + 激光测距窗
    head.append(kit.cyl("th_eo", 0.10, 0.10, axis='Z',
                        loc=(x0 - 0.02, y0, zt + body_h + 0.10), mat=M['black'], col=col,
                        seg=14, bw=0.003, segs=2))
    head.append(kit.cyl("th_eolens", 0.072, 0.05, axis='X',
                        loc=(x0 + 0.06, y0, zt + body_h + 0.11), mat=M['lens'], col=col,
                        seg=14, bw=0.002, segs=1, r2=0.04))
    return [o for o in base], [o for o in head]


# ================================================================ 腹部 6 管转管炮
def _gatling(M, col):
    G = S.GATLING_VENTRAL
    x0, y0, z0 = G['x'], G['y'], G['z']
    Rb = G['base_r']
    keel = hull.keel_z(x0)
    mount, drum, barrels = [], [], []

    # ---- 炮架（贴腹部龙骨 + 挂耳 + 俯仰作动筒）
    mount.append(kit.box("gm_plate", (0.92, 0.60, 0.14),
                         loc=(x0, y0, z0 + 0.05), mat=M['gunmetal'], col=col,
                         bw=0.006, seg=2))
    # 贴龙骨的整流垫（把炮架与船底接顺，不出现悬空平板）
    mount.append(kit.cyl("gm_pad", 0.46, 0.10, axis='Z',
                         loc=(x0, y0, z0 + 0.14), mat=M['hull_dark'], col=col,
                         seg=24, bw=0.004, segs=2, r2=0.30))
    for sgn in (-1, 1):                        # 两个上挂耳（插进龙骨）
        mount.append(kit.box("gm_lug%d" % sgn, (0.30, 0.10, 0.34),
                             loc=(x0 - 0.06, sgn * 0.26, keel - 0.02),
                             mat=M['frame'], col=col, bw=0.004, seg=1))
    for sgn in (-1, 1):                        # 两根下伸支臂（炮架）
        mount.append(kit.box("gm_arm%d" % sgn, (0.34, 0.09, 0.56),
                             loc=(x0 - 0.02, sgn * 0.33, z0 - 0.24),
                             mat=M['gunmetal'], col=col, bw=0.005, seg=2))
        mount.append(_bolt("gm_armbolt%d" % sgn, (x0 - 0.02, sgn * 0.33, z0 - 0.02),
                           0.028, 0.03, 'Z', M['alu'], col))
        mount.append(kit.cyl("gm_trun%d" % sgn, 0.055, 0.10, axis='Y',
                             loc=(x0 + 0.02, sgn * 0.38, z0 - 0.42),
                             mat=M['alu'], col=col, seg=14, bw=0.002, segs=1))
    mount.append(kit.cyl("gm_elevact", 0.055, 0.34, axis='X',
                         loc=(x0 - 0.42, y0 + 0.30, z0 - 0.20), mat=M['black'], col=col,
                         seg=12, bw=0.002, segs=1))
    mount.append(kit.cyl("gm_elevrod", 0.030, 0.30, axis='X',
                         loc=(x0 - 0.16, y0 + 0.30, z0 - 0.20), mat=M['alu'], col=col,
                         seg=12, bw=0.0015, segs=1))
    # 后部机匣
    mount.append(kit.cyl("gm_housing", 0.20, 0.46, axis='X',
                         loc=(x0 - 0.18, y0, z0 - 0.44), mat=M['gunmetal'], col=col,
                         seg=24, bw=0.005, segs=2))
    mount.append(kit.cyl("gm_reardisc", 0.23, 0.05, axis='X',
                         loc=(x0 - 0.42, y0, z0 - 0.44), mat=M['frame'], col=col,
                         seg=24, bw=0.003, segs=1))

    # ---- 供弹鼓（圆柱弹鼓 + 输弹槽 + 支架）
    drum.append(kit.cyl("gd_body", 0.27, 0.40, axis='Y',
                        loc=(x0 - 0.34, y0 + 0.54, z0 - 0.46), mat=M['gunmetal'], col=col,
                        seg=24, bw=0.006, segs=2))
    drum.append(kit.cyl("gd_lid", 0.24, 0.06, axis='Y',
                        loc=(x0 - 0.34, y0 + 0.76, z0 - 0.46), mat=M['frame'], col=col,
                        seg=24, bw=0.004, segs=1))
    for i in range(8):                          # 弹鼓加强筋（绕弹鼓轴 Y 排布）
        a = TAU * i / 8
        drum.append(kit.box("gd_rib%d" % i, (0.05, 0.38, 0.032),
                            loc=(x0 - 0.34 + 0.265 * math.cos(a), y0 + 0.54,
                                 z0 - 0.46 + 0.265 * math.sin(a)),
                            rot=(0, -a, 0), mat=M['frame'], col=col, bw=0.0015, seg=1))
    drum.append(kit.pipe_run("gd_chute",
                             [(x0 - 0.34, y0 + 0.50, z0 - 0.46),
                              (x0 - 0.30, y0 + 0.30, z0 - 0.44),
                              (x0 - 0.22, y0 + 0.12, z0 - 0.44)],
                             0.075, mat=M['gunmetal'], col=col, seg=10))
    drum.append(kit.box("gd_bracket", (0.10, 0.16, 0.30),
                        loc=(x0 - 0.34, y0 + 0.40, z0 - 0.28),
                        mat=M['frame'], col=col, bw=0.003, seg=1))

    # ---- 6 管炮管束（旋转体）
    gz = z0 - 0.44
    barrels.append(kit.cyl("gb_rotor", 0.19, 0.12, axis='X',
                           loc=(x0 + 0.12, y0, gz), mat=M['frame'], col=col,
                           seg=24, bw=0.004, segs=2))
    for i in range(6):
        a = TAU * i / 6
        by = y0 + 0.115 * math.cos(a)
        bz = gz + 0.115 * math.sin(a)
        barrels.append(kit.cyl("gb_barrel%d" % i, 0.043, 1.42, axis='X',
                               loc=(x0 + 0.90, by, bz), mat=M['gunmetal'], col=col,
                               seg=12, bw=0.002, segs=2))
    # 炮口夹箍 + 中段夹箍
    for (bx, rr) in ((x0 + 1.58, 0.185), (x0 + 0.10, 0.20)):
        barrels.append(kit.tube("gb_clamp%.0f" % (bx * 10), rr, rr - 0.045, 0.075, axis='X',
                                loc=(bx, y0, gz), mat=M['frame'], col=col, seg=24))
    # 炮口端面挡圈 + 中心轴
    barrels.append(kit.cyl("gb_hub", 0.055, 1.55, axis='X',
                           loc=(x0 + 0.90, y0, gz), mat=M['black'], col=col,
                           seg=12, bw=0.002, segs=1))
    barrels.append(kit.cyl("gb_bore", 0.045, 0.05, axis='X',
                           loc=(x0 + 1.63, y0, gz), mat=M['heat_steel'], col=col,
                           seg=12, bw=0.0015, segs=1))
    # 后部供弹入口
    barrels.append(kit.box("gb_feedport", (0.16, 0.14, 0.16),
                           loc=(x0 + 0.02, y0 + 0.16, gz + 0.10),
                           mat=M['black'], col=col, bw=0.002, seg=1))
    return mount, drum, barrels


# ================================================================ 翼下挂架 + 导弹
def _pylon(name, y_world, x_le, x_te, M, col):
    """挂在翼面下方的挂架（本体 + 挂钩 + 保险销 + 导轨）"""
    s = WG.span_at_y(abs(y_world))
    sgn = 1 if y_world > 0 else -1
    p_lo = WG.skin(s, 0.5, False, sgn)          # 翼面下表面中点
    ch = WG.chord_at(s)
    # 挂架平面中线对齐 PYLONS 给出的 x_le/x_te
    cx = 0.5 * (x_le + x_te)
    L = abs(x_le - x_te) * 0.92
    z_top = p_lo.z + 0.02
    obs = []
    rings = []
    for (dz, scale) in ((0.00, 1.00), (0.10, 0.96), (0.26, 0.80), (0.36, 0.58)):
        prof = _superellipse(L * scale, 0.16 * scale + 0.02, n=14, p=2.4)
        rings.append([Vector((cx + px, y_world + py, z_top - dz)) for (px, py) in prof])
    obs.append(_loft(name + "_body", rings, mat=M['gunmetal'], col=col, smooth=False))
    # 与翼面的整流过渡
    obs.append(kit.box(name + "_root", (L * 0.62, 0.20, 0.06),
                       loc=(cx, y_world, z_top + 0.015), mat=M['hull_dark'], col=col,
                       bw=0.003, seg=1))
    # 挂钩 ×2 + 保险销
    for k, dx in ((0, -0.34), (1, 0.34)):
        obs.append(kit.box("%s_hook%d" % (name, k), (0.09, 0.09, 0.14),
                           loc=(cx + dx, y_world, z_top - 0.36),
                           mat=M['frame'], col=col, bw=0.0018, seg=1))
        obs.append(kit.cyl("%s_pin%d" % (name, k), 0.014, 0.20, axis='Y',
                           loc=(cx + dx, y_world, z_top - 0.40), mat=M['alu'], col=col,
                           seg=8, bw=0.001, segs=1))
    # 导轨（导弹挂轨）+ 前后限位块
    obs.append(kit.box(name + "_rail", (L * 0.86, 0.045, 0.05),
                       loc=(cx, y_world, z_top - 0.42), mat=M['frame'], col=col,
                       bw=0.0018, seg=1))
    for k, dx in ((0, -0.30), (1, 0.30)):
        obs.append(kit.box("%s_stop%d" % (name, k), (0.05, 0.07, 0.09),
                           loc=(cx + dx, y_world, z_top - 0.40),
                           mat=M['alu'], col=col, bw=0.0014, seg=1))
    # 挂架侧面编号板（薄板，深色）
    obs.append(_plate(name + "_tag",
                      [Vector((cx - 0.22, y_world + 0.085, z_top - 0.06)),
                       Vector((cx + 0.22, y_world + 0.085, z_top - 0.06)),
                       Vector((cx + 0.22, y_world + 0.085, z_top - 0.20)),
                       Vector((cx - 0.22, y_world + 0.085, z_top - 0.20))],
                      Vector((0, 1, 0)), 0.006, M['accent'], col))
    return obs, z_top - 0.44, cx, sgn


def _missile(name, cx, y, z, sgn, M, col):
    """导弹：前锥 + 弹身 + 4 尾翼 + 尾喷口（长 3.4 m / 径 0.22 m）"""
    R = 0.11
    L = 3.4
    x_nose = cx + L * 0.5                     # 弹尖朝 +X
    obs = []
    # 前锥（ogive，6 环）
    rings = []
    for i in range(8):
        t = i / 7.0
        x = x_nose - 0.70 * t
        rr = R * max(0.0, 1.0 - t ** 1.55) ** 0.62
        rings.append(_ring_x("%s_nose%d" % (name, i), x, max(rr, 0.006), y, z, 18))
    obs.append(_loft(name + "_nose", rings, mat=M['hull'], col=col))
    # 弹身
    obs.append(kit.cyl(name + "_body", R, 2.22, axis='X',
                       loc=(x_nose - 0.70 - 1.11, y, z), mat=M['hull'], col=col,
                       seg=20, bw=0.003, segs=2))
    # 尾段收口
    obs.append(kit.cyl(name + "_aft", R * 0.94, 0.30, axis='X',
                       loc=(x_nose - 2.92 - 0.15, y, z), mat=M['hull'], col=col,
                       seg=20, bw=0.002, segs=2, r2=R * 0.82))
    # 尾喷口（内壁热钢 + 深色凹口）
    obs.append(kit.tube(name + "_nozzle", R * 0.84, R * 0.66, 0.16, axis='X',
                        loc=(x_nose - 3.30, y, z), mat=M['heat_steel'], col=col, seg=20))
    obs.append(kit.cyl(name + "_nozzlein", R * 0.66, 0.06, axis='X',
                       loc=(x_nose - 3.34, y, z), mat=M['black'], col=col,
                       seg=20, bw=0.0015, segs=1))
    # 弹体环带（2 道）
    for k, dx in ((0, 0.62), (1, 2.05)):
        obs.append(kit.tube("%s_band%d" % (name, k), R * 1.02, R * 0.94, 0.05, axis='X',
                            loc=(x_nose - dx, y, z), mat=M['hull_dark'], col=col, seg=20))
    # 4 片尾翼（十字形，后掠）
    for i in range(4):
        a = TAU * i / 4 + math.pi / 4
        ca, sa = math.cos(a), math.sin(a)
        q = [Vector((x_nose - 2.62, y + R * 0.9 * ca, z + R * 0.9 * sa)),
             Vector((x_nose - 3.22, y + R * 0.9 * ca, z + R * 0.9 * sa)),
             Vector((x_nose - 3.34, y + 0.34 * ca, z + 0.34 * sa)),
             Vector((x_nose - 2.94, y + 0.34 * ca, z + 0.34 * sa))]
        nrm = Vector((0, -sa, ca))
        obs.append(_plate("%s_fin%d" % (name, i), q, nrm, 0.014, M['hull_dark'], col))
    # 导引头窗口 + 弹体吊挂耳 + 气动舵面小翼
    obs.append(kit.cyl(name + "_seek", 0.042, 0.03, axis='X',
                       loc=(x_nose - 0.02, y, z), mat=M['lens'], col=col,
                       seg=12, bw=0.001, segs=1, r2=0.026))
    for k, dx in ((0, 0.75), (1, 1.55)):
        obs.append(kit.box("%s_lug%d" % (name, k), (0.10, 0.07, 0.035),
                           loc=(x_nose - dx, y, z + R * 0.96),
                           mat=M['frame'], col=col, bw=0.0014, seg=1))
    for i in range(4):
        a = TAU * i / 4
        q = [Vector((x_nose - 1.06, y + R * 0.9 * math.cos(a), z + R * 0.9 * math.sin(a))),
             Vector((x_nose - 1.30, y + R * 0.9 * math.cos(a), z + R * 0.9 * math.sin(a))),
             Vector((x_nose - 1.26, y + 0.20 * math.cos(a), z + 0.20 * math.sin(a))),
             Vector((x_nose - 1.10, y + 0.20 * math.cos(a), z + 0.20 * math.sin(a)))]
        obs.append(_plate("%s_strake%d" % (name, i), q,
                          Vector((0, -math.sin(a), math.cos(a))), 0.008,
                          M['hull_dark'], col))
    return obs


# ================================================================ build
def build(M, col):
    out = []

    base, head = _turret(M, col)
    ob = kit.join(base, "wpn_turret_base")
    kit.part(ob, "wpn_turret_base", "炮塔基座", "Turret Ring Base", "weapons", (0, 0, 1),
             order=10, note="回转齿圈 r=0.62 + 16 颗地脚螺栓 + 4 段装甲裙；圆心 (2.60, 0, 1.42)")
    out.append(ob)

    ob = kit.join(head, "wpn_turret_head")
    kit.part(ob, "wpn_turret_head", "双联激光炮塔", "Twin Laser Turret", "weapons", (0, 0, 1),
             order=11, note="转动塔身 + 俯仰耳轴 + 双侧伺服 + 双炮管（1.55 m）+ 激光透镜/辉光环")
    out.append(ob)

    mount, drum, barrels = _gatling(M, col)
    ob = kit.join(mount, "wpn_gatling_mount")
    kit.part(ob, "wpn_gatling_mount", "转管炮炮架", "Gatling Cradle", "weapons", (0, 0, -1),
             order=12, note="腹部炮架：龙骨挂耳 + 双支臂 + 俯仰作动筒 + 机匣 (4.20, 0, -1.30)")
    out.append(ob)

    ob = kit.join(drum, "wpn_gatling_drum")
    kit.part(ob, "wpn_gatling_drum", "供弹鼓", "Ammo Drum", "weapons", (0, 0.35, -1),
             order=13, note="r=0.27 弹鼓 + 8 道加强筋 + 输弹槽，挂在炮架右侧")
    out.append(ob)

    ob = kit.join(barrels, "wpn_gatling_barrels")
    kit.part(ob, "wpn_gatling_barrels", "六管炮管束", "Six-Barrel Cluster", "weapons", (0, 0, -1),
             order=14, note="6 × r=0.043 炮管（1.42 m）+ 前后夹箍 + 中心轴 + 炮口热钢")
    out.append(ob)

    num = 0
    for i, (py, x_le, x_te, _n) in enumerate(S.PYLONS):
        for sgn, side in ((1, "s"), (-1, "p")):
            num += 1
            y = py * sgn
            pid = "wpn_pylon_%s%d" % (side, i + 1)
            obs, z_hang, cx, sg = _pylon("ply_%s%d" % (side, i + 1), y, x_le, x_te, M, col)
            ob = kit.join(obs, pid)
            kit.part(ob, pid, "%s%d 号挂架" % ("右舷" if sgn > 0 else "左舷", i + 1),
                     "Pylon %s%d" % (side.upper(), i + 1), "weapons",
                     (0, sgn, -0.35), order=15 + num,
                     note="翼下挂架 y=%.2f：流线本体 + 2 挂钩 + 2 保险销 + 挂轨 + 警示牌" % y)
            out.append(ob)

            mpid = "wpn_missile_%s%d" % (side, i + 1)
            print("CLEAR %s wing_lo=%.3f missile_top=%.3f fin_top=%.3f gap_body=%.3f gap_fin=%.3f"
                  % (mpid, z_hang + 0.44, z_hang - 0.13 + 0.11,
                     z_hang - 0.13 + 0.34,
                     (z_hang + 0.44) - (z_hang - 0.13 + 0.11),
                     (z_hang + 0.44) - (z_hang - 0.13 + 0.34)))
            mobs = _missile("msl_%s%d" % (side, i + 1), cx, y, z_hang - 0.13, sgn, M, col)
            ob = kit.join(mobs, mpid)
            kit.part(ob, mpid, "%s%d 号导弹" % ("右舷" if sgn > 0 else "左舷", i + 1),
                     "Missile %s%d" % (side.upper(), i + 1), "weapons",
                     (0, sgn, -0.6), order=21 + num,
                     note="长 3.4 m / 径 0.22 m：ogive 前锥 + 2 道环带 + 4 片后掠尾翼 + 尾喷口 + 导引头窗")
            out.append(ob)
    return out
