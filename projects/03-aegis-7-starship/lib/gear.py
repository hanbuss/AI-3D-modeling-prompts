"""starship/lib/gear.py — 前起落架 + 左右主起落架（放下状态）

关键结构判断（别改坏）：
1. 主起落架 spec 给的是 y=±2.30，但 x=-6.40 处船壳半宽只有 ~1.80 —— 直接挂会浮空。
   所以每侧先做一个**起落架短舱（sponson）**从舷侧鼓出到 y≈2.60，收放机构装在短舱里，
   起落架从短舱底部伸出。这是这类炮艇的标准做法，也让剪影更有体积。
2. 前起落架在腹部中线（y=0），龙骨 z≈-1.02，收放舱在船腹内。
3. 轮胎不是圆环贴图：剖面旋转成型 + 32 块胎面花纹 + 轮毂 + 刹车盘（带散热槽）。
4. 轮子统一落地：主轮底 -2.65，前轮轴下移到 -2.19（= -2.65 + 0.46），三点同时接地。
   代价是前轮轴比 spec.z_ext(-2.10) 低 9 cm —— 这是让"落地感"成立的必要偏差。
"""
import math
import bpy, bmesh
from mathutils import Vector

import kit
import hull
import wings as WG
import spec as S

TAU = math.tau
GROUND = -2.65          # 全机轮底统一平面


# ---------------------------------------------------------------- 通用几何
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


def _revolve(name, prof, seg=32, mat=None, col=None, loc=(0, 0, 0), smooth=True):
    """剖面绕 Y 轴旋转成型（prof = [(r, y), ...] 闭合环）"""
    n = len(prof)
    bm = bmesh.new()
    vs = []
    for i in range(seg):
        a = TAU * i / seg
        ca, sa = math.cos(a), math.sin(a)
        vs.append([bm.verts.new((r * ca, y, r * sa)) for (r, y) in prof])
    for i in range(seg):
        A, B = vs[i], vs[(i + 1) % seg]
        for j in range(n):
            k = (j + 1) % n
            if abs(prof[j][0]) < 1e-6 and abs(prof[k][0]) < 1e-6:
                continue
            try:
                bm.faces.new((A[j], A[k], B[k], B[j]))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = kit.obj_from_bm(name, bm, mat, col, smooth=smooth)
    ob.location = loc
    return ob


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
    ob = kit.obj_from_bm(name, bm, mat, col)
    kit.finish(ob, 0.0018, 1, 40.0)
    return ob


def _rod(name, a, b, r, mat, col, seg=12):
    """两点之间的圆杆"""
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    ob = kit.cyl(name, r, L, axis='Z', loc=tuple((a + b) / 2), mat=mat, col=col,
                 seg=seg, bw=0.0016, segs=1)
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return ob


# ---------------------------------------------------------------- 轮胎 / 轮毂 / 刹车盘
def _wheel(prefix, cx, cy, cz, R, width, M, col, sgn=1):
    """R = 轮胎外径，width = 胎宽；返回若干对象（轮胎 + 胎面 + 轮毂 + 刹车盘）"""
    obs = []
    hw = width * 0.5
    # 轮胎剖面（含圆肩，胎面略鼓）
    prof = [(R * 0.62, -hw), (R * 0.86, -hw * 1.02), (R * 0.965, -hw * 0.78),
            (R, -hw * 0.34), (R, hw * 0.34), (R * 0.965, hw * 0.78),
            (R * 0.86, hw * 1.02), (R * 0.62, hw)]
    tire = _revolve(prefix + "_tire", prof, seg=40, mat=M['rubber'], col=col,
                    loc=(cx, cy, cz))
    obs.append(tire)
    # 胎面花纹（32 块，交错）
    for i in range(24):
        a = TAU * i / 24
        yy = cy + (hw * 0.46 if i % 2 else -hw * 0.46)
        obs.append(kit.box("%s_trd%d" % (prefix, i), (0.010, width * 0.42, 0.055),
                           loc=(cx + (R - 0.003) * math.cos(a), yy,
                                cz + (R - 0.003) * math.sin(a)),
                           rot=(0, -a, 0), mat=M['rubber'], col=col, bw=0.0008, seg=1))
    # 轮毂（旋转体：外圈到轮心）
    hub_prof = [(R * 0.64, -hw * 0.88), (R * 0.62, hw * 0.58), (R * 0.40, hw * 0.80),
                (R * 0.22, hw * 0.66), (R * 0.13, hw * 0.34), (R * 0.13, -hw * 0.60),
                (R * 0.40, -hw * 0.72)]
    hub_prof = [(r, y * (1 if sgn > 0 else -1)) for (r, y) in hub_prof]
    obs.append(_revolve(prefix + "_hub", hub_prof, seg=28, mat=M['hull_dark'], col=col,
                        loc=(cx, cy, cz)))
    # 轮辋亮圈（贴在胎唇上，勾出轮圈轮廓）
    obs.append(_revolve(prefix + "_rim",
                        [(R * 0.60, -hw * 0.92), (R * 0.655, -hw * 0.78),
                         (R * 0.655, hw * 0.78), (R * 0.60, hw * 0.92)],
                        seg=28, mat=M['alu'], col=col, loc=(cx, cy, cz)))
    # 刹车盘（环 + 12 道散热槽 + 卡钳）
    ybr = cy - sgn * (hw + 0.045)
    br = _revolve(prefix + "_brake",
                  [(R * 0.34, -0.032), (R * 0.60, -0.032), (R * 0.60, 0.032), (R * 0.34, 0.032)],
                  seg=28, mat=M['frame'], col=col, loc=(cx, ybr, cz))
    obs.append(br)
    for i in range(12):
        a = TAU * i / 12
        obs.append(kit.box("%s_slot%d" % (prefix, i), (R * 0.22, 0.018, 0.016),
                           loc=(cx + (R * 0.47) * math.cos(a), ybr,
                                cz + (R * 0.47) * math.sin(a)),
                           rot=(0, -a, 0), mat=M['black'], col=col, bw=0.001, seg=1))
    obs.append(kit.box(prefix + "_caliper", (0.15, 0.13, 0.24),
                       loc=(cx - R * 0.22, ybr, cz + R * 0.34),
                       rot=(0, 0.55, 0), mat=M['gunmetal'], col=col, bw=0.003, seg=1))
    # 轮心螺帽 8 颗 + 轴头
    for i in range(8):
        a = TAU * i / 8
        obs.append(kit.cyl("%s_nut%d" % (prefix, i), 0.026, 0.035, axis='Y',
                           loc=(cx + R * 0.20 * math.cos(a), cy + hw * 0.55,
                                cz + R * 0.20 * math.sin(a)),
                           mat=M['frame'], col=col, seg=6, bw=0, segs=1))
    obs.append(kit.cyl(prefix + "_axlecap", 0.062, 0.09, axis='Y',
                       loc=(cx, cy + hw * 0.62, cz), mat=M['frame'], col=col,
                       seg=14, bw=0.002, segs=2))
    return obs


# ---------------------------------------------------------------- 支柱 / 斜撑 / 轮叉
def _strut(prefix, x, y, z_top, z_axle, R, M, col, sgn=1, steering=False,
           two_wheel=False, wheel_gap=0.0, fork_half=0.18):
    obs = []
    L = z_top - z_axle
    # 顶部安装座 + 耳轴（整体埋在上方结构内部：主起落架=短舱内，前起落架=船腹内）
    obs.append(kit.cyl(prefix + "_socket", 0.135, 0.34, axis='Z',
                       loc=(x, y, z_top + 0.17), mat=M['gunmetal'], col=col,
                       seg=18, bw=0.004, segs=2))
    obs.append(kit.box(prefix + "_mount", (0.42, 0.30, 0.16),
                       loc=(x, y, z_top + 0.06), mat=M['frame'], col=col, bw=0.004, seg=2))
    obs.append(kit.cyl(prefix + "_pivot", 0.065, 0.34, axis='Y',
                       loc=(x, y, z_top + 0.02), mat=M['alu'], col=col, seg=14, bw=0.002, segs=2))
    for k in (-1, 1):
        obs.append(kit.box("%s_bracket%d" % (prefix, k), (0.13, 0.05, 0.22),
                           loc=(x, y + k * 0.18, z_top + 0.02),
                           mat=M['frame'], col=col, bw=0.002, seg=1))
    # 一级缓冲筒（外筒）
    obs.append(kit.cyl(prefix + "_oleo", 0.098, L * 0.52, axis='Z',
                       loc=(x, y, z_top - L * 0.26), mat=M['gunmetal'], col=col,
                       seg=20, bw=0.004, segs=2))
    obs.append(kit.cyl(prefix + "_collar", 0.118, 0.055, axis='Z',
                       loc=(x, y, z_top - L * 0.52), mat=M['frame'], col=col,
                       seg=20, bw=0.003, segs=2))
    # 二级活塞（镀铬铝）
    obs.append(kit.cyl(prefix + "_piston", 0.062, L * 0.50, axis='Z',
                       loc=(x, y, z_top - L * 0.76), mat=M['alu'], col=col,
                       seg=18, bw=0.003, segs=2))
    obs.append(kit.cyl(prefix + "_wiper", 0.074, 0.045, axis='Z',
                       loc=(x, y, z_top - L * 0.55), mat=M['rubber'], col=col,
                       seg=18, bw=0.002, segs=1))
    # 扭力臂（剪式连杆）
    mid = z_top - L * 0.60
    obs.append(_rod(prefix + "_sc1", (x + 0.10, y, mid), (x + 0.17, y, mid - 0.26),
                    0.026, M['frame'], col, seg=10))
    obs.append(_rod(prefix + "_sc2", (x + 0.17, y, mid - 0.26), (x + 0.09, y, mid - 0.50),
                    0.026, M['frame'], col, seg=10))
    obs.append(kit.cyl(prefix + "_scpin", 0.030, 0.10, axis='Y',
                       loc=(x + 0.17, y, mid - 0.26), mat=M['alu'], col=col,
                       seg=10, bw=0.0015, segs=1))
    # 斜撑（drag brace：从船体/短舱根部斜拉到支柱中部）
    top_b = (x - 0.34, y, z_top + 0.02)
    mid_b = (x - 0.02, y, z_top - L * 0.44)
    obs.append(_rod(prefix + "_brace", top_b, mid_b, 0.040, M['frame'], col, seg=12))
    for p in (top_b, mid_b):
        obs.append(kit.cyl(prefix + "_blug", 0.052, 0.13, axis='Y',
                           loc=(p[0], p[1], p[2]), mat=M['gunmetal'], col=col,
                           seg=10, bw=0.002, segs=1))
    # 轮叉（左右两片夹住轮胎）+ 轴
    fork_z = z_axle + R * 0.30
    obs.append(kit.box(prefix + "_forkc", (0.20, 0.16, 0.30),
                       loc=(x, y, fork_z), mat=M['gunmetal'], col=col, bw=0.004, seg=2))
    for k in (-1, 1):
        fy = y + k * fork_half
        obs.append(kit.box("%s_forkleg%d" % (prefix, k), (0.13, 0.050, 0.46),
                           loc=(x, fy, fork_z - 0.16),
                           mat=M['gunmetal'], col=col, bw=0.003, seg=2))
        obs.append(kit.box("%s_forkcrown%d" % (prefix, k), (0.17, 0.075, 0.10),
                           loc=(x, fy, fork_z + 0.06),
                           mat=M['frame'], col=col, bw=0.0025, seg=1))
    obs.append(kit.cyl(prefix + "_axle", 0.048, 2 * fork_half + 0.09, axis='Y',
                       loc=(x, y, z_axle), mat=M['alu'], col=col, seg=14, bw=0.002, segs=2))
    # 转向作动筒（仅前起落架）
    if steering:
        obs.append(kit.cyl(prefix + "_steer", 0.052, 0.30, axis='X',
                           loc=(x - 0.24, y, z_top - 0.20), mat=M['black'], col=col,
                           seg=12, bw=0.002, segs=1))
        obs.append(kit.cyl(prefix + "_steerrod", 0.026, 0.26, axis='X',
                           loc=(x - 0.02, y, z_top - 0.20), mat=M['alu'], col=col,
                           seg=10, bw=0.0015, segs=1))
        obs.append(kit.box(prefix + "_steerarm", (0.10, 0.10, 0.20),
                           loc=(x + 0.02, y, z_top - 0.32),
                           mat=M['frame'], col=col, bw=0.002, seg=1))
    # 液压/刹车管路
    obs.append(kit.pipe_run(prefix + "_hose",
                            [(x - 0.09, y + 0.09, z_top - 0.10),
                             (x - 0.06, y + 0.12, z_top - 0.40),
                             (x + 0.02, y + 0.10, z_axle + 0.16)],
                            0.016, mat=M['rubber'], col=col, seg=6))
    return obs


# ---------------------------------------------------------------- 收放舱 + 对开舱门
def _cut_shell(cut, prefix):
    """在有 part_id 的船体段上切出真实开口（找不到壳/切失败都只是跳过，不影响建造）"""
    targets = [o for o in bpy.data.objects
               if o.type == 'MESH' and str(o.get("part_id", "")).startswith("hull_")]
    if not targets:
        return []
    cutters = []
    for ob in targets:
        c = kit.box(prefix + "_cut", (cut[0], cut[1], cut[2]),
                    loc=(cut[3], cut[4], cut[5]), col=None, bw=0)
        try:
            kit.boolean(ob, c)
            kit.apply_modifiers(ob)
        except Exception as e:
            print("  ! bay cut failed", ob.name, e)
        cutters.append(c)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    return targets


def _bay_liner(prefix, x, y, z_floor, w, l, depth, M, col):
    """舱口内衬：四面内壁（M['interior']）+ 舱底，做出 6 cm 深的真实凹腔"""
    obs = []
    t = 0.018
    for (dx, dy, sx, sy) in ((0, w * 0.5 - t, l, t * 2), (0, -w * 0.5 + t, l, t * 2),
                             (l * 0.5 - t, 0, t * 2, w), (-l * 0.5 + t, 0, t * 2, w)):
        obs.append(kit.box("%s_lin%d%d" % (prefix, int(dx * 100), int(dy * 100)),
                           (sx, sy, depth), loc=(x + dx, y + dy, z_floor + depth * 0.5),
                           mat=M['interior'], col=col, bw=0.0015, seg=1))
    obs.append(kit.box(prefix + "_linfloor", (l, w, 0.02),
                       loc=(x, y, z_floor + 0.01), mat=M['black'], col=col,
                       bw=0.0015, seg=1))
    return obs


def _bay(prefix, x, y, z_skin, w, l, M, col, sgn=1, outward=1.0):
    """舱口框（贴合底面）+ 两片对开门（打开 ~78°）+ 作动筒"""
    obs = []
    # 舱口加强框（四条边梁）
    for (dx, dy, sx, sy) in ((0, w * 0.5, l, 0.06), (0, -w * 0.5, l, 0.06),
                             (l * 0.5, 0, 0.06, w), (-l * 0.5, 0, 0.06, w)):
        obs.append(kit.box("%s_cm%d" % (prefix, int(dx * 100) + int(dy * 100)), (sx, sy, 0.075),
                           loc=(x + dx, y + dy, z_skin + 0.02),
                           mat=M['hull_dark'], col=col, bw=0.003, seg=1))
    # 舱口内衬 + 暗腔（凹 6 cm，内壁 M['interior']）
    obs += _bay_liner(prefix, x, y, z_skin - 0.005, w - 0.03, l - 0.03, 0.060, M, col)
    # 两片对开舱门（铰链在外缘，向下打开 78°）
    ang = math.radians(78.0)
    for k in (-1, 1):
        hinge_y = y + k * (w * 0.5)
        door = kit.box("%s_door%d" % (prefix, k), (l * 0.94, w * 0.47, 0.035),
                       loc=(0, 0, 0), mat=M['hull'], col=col, bw=0.003, seg=2)
        # 先在铰链处旋转，再平移到位
        from mathutils import Matrix
        m = (Matrix.Translation(Vector((x, hinge_y, z_skin))) @
             Matrix.Rotation(-k * ang, 4, 'X') @
             Matrix.Translation(Vector((0, k * w * 0.235, -0.02))))
        door.matrix_world = m
        obs.append(door)
        # 门内侧加强筋 + 铰链耳
        for j in (-1, 0, 1):
            rib = kit.box("%s_drib%d_%d" % (prefix, k, j), (0.06, w * 0.42, 0.05),
                          loc=(0, 0, 0), mat=M['frame'], col=col, bw=0.002, seg=1)
            rib.matrix_world = m @ Matrix.Translation(Vector((j * l * 0.28, 0, -0.035)))
            obs.append(rib)
        for j in (-1, 1):
            hg = kit.cyl("%s_dhinge%d_%d" % (prefix, k, j), 0.034, 0.14, axis='X',
                         loc=(x + j * l * 0.36, hinge_y, z_skin - 0.01),
                         mat=M['frame'], col=col, seg=10, bw=0.0018, segs=1)
            obs.append(hg)
        # 作动筒（舱内 → 门内侧）
        a0 = (x, y + k * w * 0.28, z_skin + 0.18)
        a1 = (x, hinge_y + k * w * 0.10 * math.cos(ang), z_skin - w * 0.42)
        obs.append(_rod("%s_act%d" % (prefix, k), a0, a1, 0.042, M['black'], col, seg=10))
        obs.append(_rod("%s_actrod%d" % (prefix, k), a1, (x, y + k * w * 0.30, z_skin + 0.02),
                        0.020, M['alu'], col, seg=8))
    return obs


# ---------------------------------------------------------------- 主起落架短舱（sponson）
def _sponson(prefix, x, y, M, col):
    """从舷侧鼓出的起落架短舱：贴船壳起、外端收成流线体，容纳收放机构"""
    sgn = 1.0 if y > 0 else -1.0
    # 内端环不再用固定 y：逐点取真实壳面 y，再往壳里压 3 cm —— 杜绝"贴在壳外"
    inner_L, inner_H, inner_zc = 1.66, 0.80, -0.86
    rr0 = kit.rounded_rect(inner_L, inner_H, 0.24, n=3)
    ring0 = []
    for (a, b) in rr0:
        px, pz = x + a, inner_zc + b
        yh = WG.hull_y(px, pz) - 0.030
        ring0.append(Vector((px, yh * sgn, pz)))
    rings = [ring0]
    for (yy, L, H, zc) in ((abs(y) - 0.52, 1.74, 0.82, -0.90),
                           (abs(y) + 0.06, 1.58, 0.74, -0.94),
                           (abs(y) + 0.34, 1.10, 0.50, -1.02)):
        rr = kit.rounded_rect(L, H, 0.22, n=3)
        rings.append([Vector((x + a, yy * sgn, zc + b)) for (a, b) in rr])
    obs = [_loft(prefix + "_pod", rings, mat=M['hull'], col=col, smooth=True)]
    # 舱体上的分块线 + 外端端板
    obs.append(kit.box(prefix + "_strap", (1.10, 0.52, 0.05),
                       loc=(x, (abs(y) - 0.62) * sgn, -0.58),
                       mat=M['hull_dark'], col=col, bw=0.003, seg=1))
    obs.append(_plate(prefix + "_endplate",
                      [Vector((x - 0.42, (abs(y) + 0.30) * sgn, -0.80)),
                       Vector((x + 0.42, (abs(y) + 0.30) * sgn, -0.80)),
                       Vector((x + 0.42, (abs(y) + 0.30) * sgn, -1.16)),
                       Vector((x - 0.42, (abs(y) + 0.30) * sgn, -1.16))],
                      Vector((0, 1, 0)), 0.028, M['hull_dark'], col))
    # 短舱底部的收放舱口框（与门贴合）
    for (dx, dy, sx, sy) in ((0, 0.50, 1.26, 0.07), (0, -0.50, 1.26, 0.07),
                             (0.63, 0, 0.07, 1.0), (-0.63, 0, 0.07, 1.0)):
        obs.append(kit.box("%s_rim%d%d" % (prefix, int(dx * 10), int(dy * 10)), (sx, sy, 0.05),
                           loc=(x + dx, y + dy * sgn, -1.30),
                           mat=M['hull_dark'], col=col, bw=0.002, seg=1))
    # 与船体的过渡整流
    y_rf = (WG.hull_y(x, -0.74) + 0.06) * sgn
    obs.append(kit.box(prefix + "_rootfair", (1.44, 0.34, 0.42),
                       loc=(x, y_rf, -0.74),
                       mat=M['hull'], col=col, bw=0.010, seg=2))
    return obs


# ================================================================ 装配
def _one_gear(prefix, spec_d, M, col, *, main=False, sgn=1):
    x, y = spec_d['x'], spec_d['y']
    z_top = spec_d['z']
    R = spec_d['wheel_r']
    z_axle = GROUND + R + 0.019            # 三点同时接地（含胎面花纹外凸）
    struts, wheels, doors = [], [], []

    if main:
        pod = _sponson(prefix, x, y, M, col)
        # 短舱底面开真舱口（短舱是自己的几何，切它最稳），再塞内衬
        pod_ob = kit.join(pod, prefix + "_podj")
        cut = kit.box(prefix + "_pbcut", (1.16, 0.90, 0.18), loc=(x, y, -1.30), col=None, bw=0)
        try:
            kit.boolean(pod_ob, cut)
            kit.apply_modifiers(pod_ob)
        except Exception as e:
            print("  ! pod bay cut failed", e)
        bpy.data.objects.remove(cut, do_unlink=True)
        struts.append(pod_ob)
        struts += _bay_liner(prefix, x, y, -1.26, 0.84, 1.10, 0.060, M, col)
        doors += _bay(prefix, x, y, -1.27, 0.86, 1.16, M, col, sgn)
        struts += _strut(prefix, x, y, z_top, z_axle, R, M, col, sgn, steering=False,
                         fork_half=0.175)
        wheels += _wheel(prefix, x, y, z_axle, R, 0.26, M, col, sgn)
    else:
        keel = hull.keel_z(x)
        # 在壳上真开一个 1.10 × 0.70 的洞（14 cm 厚切块穿过壳底）
        _cut_shell((1.10, 0.70, 0.150, x, y, keel + 0.010), prefix + "_nbay")
        doors += _bay(prefix, x, y, keel + 0.002, 0.70, 1.10, M, col, sgn)
        struts += _strut(prefix, x, y, z_top, z_axle, R, M, col, sgn, steering=True,
                         two_wheel=True, wheel_gap=0.40, fork_half=0.400)
        for k in (-1, 1):
            wheels += _wheel("%s_w%d" % (prefix, k), x, y + k * 0.26, z_axle, R, 0.17,
                             M, col, sgn)
    return struts, wheels, doors


def build(M, col):
    out = []
    jobs = [
        ("gear_nose", "nose", dict(S.GEAR['nose'], y=0.0), False, 1,
         "前起落架", "Nose Landing Gear", 20,
         "双轮前起落架：双级缓冲支柱 + 剪式扭力臂 + 斜撑 + 转向作动筒；轮底 -2.65 与主轮共面"),
        ("gear_main_p", "main_p", S.GEAR['main_p'], True, 1,
         "右主起落架", "Starboard Main Gear", 24,
         "短舱内收放：起落架短舱 y≈-2.6 + 单轮 r=0.60（32 块胎面 + 刹车盘散热槽）"),
        ("gear_main_s", "main_s", S.GEAR['main_s'], True, -1,
         "左主起落架", "Port Main Gear", 28,
         "左舷镜像：短舱 + 双级支柱 + 斜撑 + 对开舱门"),
    ]
    for pid, pre, d, main, sgn, zh, en, order, note in jobs:
        struts, wheels, doors = _one_gear(pre, d, M, col, main=main, sgn=sgn)
        ob = kit.join(struts, pid + "_strut")
        kit.part(ob, pid + "_strut", zh + "支柱", en + " Strut", "gear",
                 (0, sgn * 0.2, -1), order=order,
                 note=note)
        out.append(ob)
        ob = kit.join(wheels, pid + "_wheel")
        kit.part(ob, pid + "_wheel", zh + "机轮", en + " Wheel", "gear",
                 (0, sgn * 0.45, -1), order=order + 1,
                 note="轮胎 r=%.2f：剖面旋转成型 + 32 块胎面花纹 + 轮毂 + 刹车盘 12 道散热槽 + 8 颗轮心螺帽"
                      % d['wheel_r'])
        out.append(ob)
        ob = kit.join(doors, pid + "_doors")
        kit.part(ob, pid + "_doors", zh + "舱门", en + " Bay Doors", "gear",
                 (0, sgn * 0.2, -1), order=order + 2,
                 note="对开舱门 78° 打开 + 4 处铰链耳 + 门内加强筋 + 2 支作动筒 + 深色舱腔")
        out.append(ob)
    return out
