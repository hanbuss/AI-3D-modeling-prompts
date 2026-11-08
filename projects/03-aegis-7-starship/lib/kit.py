"""mk18/lib/kit.py — 硬表面几何内核（bpy/bmesh，无上下文依赖）
坐标：X = 枪口方向(+)，Y = 上，Z = 右侧(+)。单位：米。
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

TAU = math.tau


# ---------------------------------------------------------------- scene
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


def new_col(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, col=None):
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


# ---------------------------------------------------------------- low level
def obj_from_bm(name, bm, mat=None, col=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    link(ob, col)
    return ob


def obj_from_pydata(name, verts, faces, mat=None, col=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    link(ob, col)
    return ob


# ---------------------------------------------------------------- bevel / apply
def apply_modifiers(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print("  ! modifier apply failed", ob.name, m.name, e)


def bevel(ob, width=0.0008, segments=2, angle=35.0, harden=True):
    m = ob.modifiers.new("bev", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.miter_outer = 'MITER_ARC'
    m.harden_normals = harden
    return m


def weighted_normal(ob):
    m = ob.modifiers.new("wn", 'WEIGHTED_NORMAL')
    m.keep_sharp = True
    return m


def finish(ob, bw=0.0008, seg=2, angle=35.0, smooth_angle=None):
    """bevel + apply; smooth_angle 给定时按角度标平滑面"""
    bevel(ob, bw, seg, angle)
    weighted_normal(ob)
    apply_modifiers(ob)
    if smooth_angle is not None:
        set_smooth_by_angle(ob, smooth_angle)
    return ob


def set_smooth_by_angle(ob, ang_deg=32.0):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    # 用 sharp edges 表示硬边（Blender 4.1+ 移除 auto smooth，需 sharp_edge + modifier 或直接 flat）
    me.update()
    # 5.x：靠 edge sharp + Smooth by Angle 节点；这里直接按角度把面标平
    th = math.radians(ang_deg)
    for e in me.edges:
        pass
    # 简洁可靠做法：按面法线夹角分组，用 auto_smooth 修改器（5.x 有 SMOOTH_BY_ANGLE）
    try:
        m = ob.modifiers.new("sba", 'SMOOTH_BY_ANGLE')
        m.angle = th
    except Exception:
        for p in me.polygons:
            p.use_smooth = False


# ---------------------------------------------------------------- primitives
def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, col=None, bw=0.0008, seg=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    bmesh.ops.scale(bm, vec=Vector((sx, sy, sz)), verts=bm.verts)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def cyl(name, r, depth, axis='Z', loc=(0, 0, 0), rot=(0, 0, 0), mat=None, col=None, seg=32,
        bw=0.0006, segs=2, r2=None):
    bm = bmesh.new()
    if r2 is None or abs(r2 - r) < 1e-9:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r, radius2=r, depth=depth)
    else:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r, radius2=r2, depth=depth)
    if axis == 'X':
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    elif axis == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    ob = obj_from_bm(name, bm, mat, col, smooth=True)
    ob.location = loc
    ob.rotation_euler = rot
    if bw:
        finish(ob, bw, segs)
    return ob


def tube(name, r_out, r_in, depth, axis='X', loc=(0, 0, 0), rot=(0, 0, 0), mat=None, col=None,
         seg=32, bw=0.0006):
    bm = bmesh.new()
    rings = []
    for (r, x) in ((r_out, -depth / 2), (r_out, depth / 2)):
        pass
    # 手工构造圆环壳体
    def ring(r, x, n):
        return [bm.verts.new((x, r * math.cos(TAU * i / n), r * math.sin(TAU * i / n))) for i in range(n)]
    o1 = ring(r_out, -depth / 2, seg)
    o2 = ring(r_out, depth / 2, seg)
    i1 = ring(r_in, -depth / 2, seg)
    i2 = ring(r_in, depth / 2, seg)
    for a, b in ((o1, o2), (i1, i2)):
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    for a, b, flip in ((o1, i1, True), (o2, i2, False)):
        for i in range(seg):
            f = bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
            if flip:
                f.normal_flip()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat, col, smooth=True)
    if axis == 'Y':
        ob.rotation_euler = (0, 0, math.pi / 2)
    elif axis == 'Z':
        ob.rotation_euler = (0, math.pi / 2, 0)
    if rot != (0, 0, 0):
        base = list(ob.rotation_euler)
        ob.rotation_euler = (base[0] + rot[0], base[1] + rot[1], base[2] + rot[2])
    ob.location = loc
    return ob


def loft(name, rings, mat=None, col=None, close_start=True, close_end=True, smooth=False):
    """rings: [(x, [(y,z), ...]) ...] 每环点数必须一致，沿 X 放样"""
    bm = bmesh.new()
    vr = []
    for (x, pts) in rings:
        vr.append([bm.verts.new((x, y, z)) for (y, z) in pts])
    n = len(vr[0])
    for a, b in zip(vr[:-1], vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            # 硬棱处剖面点是"重复顶点"（坐标相同），这类四边形是退化的零面积面：
            # 直接跳过（不建面），棱才既硬又不会让 glTF 报 mesh invalid
            if (a[i].co - a[j].co).length < 1e-9 or (b[i].co - b[j].co).length < 1e-9:
                continue
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if close_start:
        bm.faces.new(list(reversed(vr[0])))
    if close_end:
        bm.faces.new(vr[-1])
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, mat, col, smooth=smooth)


def prism(name, prof_xz, y0, y1, mat=None, col=None, smooth=False, bw=0.0):
    """prof_xz: [(x,z)...] 闭合 2D 剖面，沿 Y 挤出 [y0,y1]"""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for (x, z) in prof_xz]
    b = [bm.verts.new((x, y1, z)) for (x, z) in prof_xz]
    n = len(a)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat, col, smooth=smooth)
    if bw:
        finish(ob, bw, 2)
    return ob


def prism_xy(name, prof_xy, z0, z1, mat=None, col=None, smooth=False):
    """prof_xy: [(x,y)...] 闭合剖面（侧视轮廓），沿 Z 挤出 [z0,z1] —— 机匣类首选"""
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for (x, y) in prof_xy]
    b = [bm.verts.new((x, y, z1)) for (x, y) in prof_xy]
    n = len(a)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, mat, col, smooth=smooth)


def prism_zy(name, prof_yz, x0, x1, mat=None, col=None, smooth=False):
    """prof_yz: [(y,z)...] 沿 X 挤出"""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for (y, z) in prof_yz]
    b = [bm.verts.new((x1, y, z)) for (y, z) in prof_yz]
    n = len(a)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, mat, col, smooth=smooth)


def rounded_rect(w, h, r, n=4):
    """中心在原点、X 宽 h? -> 返回 (u,v) 环，用于剖面"""
    r = min(r, w / 2 - 1e-5, h / 2 - 1e-5)
    pts = []
    cx = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
          (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for (px, py, a0) in cx:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((px + r * math.cos(a), py + r * math.sin(a)))
    return pts


def boolean(target, cutter, op='DIFFERENCE'):
    m = target.modifiers.new("bool", 'BOOLEAN')
    m.object = cutter
    m.operation = op
    m.solver = 'EXACT'
    return m


def cut(target, cutter, delete_cutter=True):
    boolean(target, cutter)
    apply_modifiers(target)
    if delete_cutter:
        bpy.data.objects.remove(cutter, do_unlink=True)
    return target


# ---------------------------------------------------------------- gun specific
def picatinny(name, x0, x1, y_top, z_center=0.0, mat=None, col=None,
              pitch=0.010, slot=0.00535, top_w=0.0212, base_w=0.0158, h=0.0095):
    """MIL-STD-1913 皮卡汀尼导轨：底座楔形 + 横向肋（肋间槽 5.35mm、节距 10mm）"""
    bm = bmesh.new()
    w0 = base_w / 2
    w1 = top_w / 2
    pts = [(y_top - h, -w0), (y_top - h, w0), (y_top - h * 0.45, w1),
           (y_top, w1 - 0.0018), (y_top, -(w1 - 0.0018)), (y_top - h * 0.45, -w1)]
    a = [bm.verts.new((x0, y, z)) for (y, z) in pts]
    b = [bm.verts.new((x1, y, z)) for (y, z) in pts]
    n = len(a)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat, col)
    ribs = []
    x = x0 + 0.002
    i = 0
    while x + slot < x1 - 0.002:
        ra = x
        rb = min(x + pitch - slot, x1 - 0.002)
        if rb - ra > 0.0012:
            ribs.append(box(f"{name}_rib{i}", (rb - ra, 0.0022, top_w - 0.0006),
                            loc=((ra + rb) / 2, y_top + 0.0004, z_center),
                            mat=mat, col=col, bw=0.00025, seg=1))
            i += 1
        x += pitch
    if ribs:
        ob = join([ob] + ribs, name)
    finish(ob, 0.0004, 1, 40)
    return ob


def knurl_ring(name, r, depth, count, mat=None, col=None, h=0.0006, w=0.0008):
    """滚花/防滑齿环（径向小凸条，绕 X 轴）"""
    deselect_all()
    objs = []
    for i in range(count):
        a = TAU * i / count
        b = box(f"{name}_{i}", (depth, h, w), mat=mat, col=col, bw=0.00015, seg=1)
        b.location = (0, math.cos(a) * r, math.sin(a) * r)
        b.rotation_euler = (a, 0, 0)
        objs.append(b)
    # join
    base = objs[0]
    deselect_all()
    bpy.context.view_layer.objects.active = base
    for o in objs:
        try:
            o.select_set(True)
        except Exception:
            pass
    bpy.ops.object.join()
    base.select_set(False)
    base.name = name
    return base


def screw(name, r, depth, loc, axis='Z', mat=None, col=None, head=1.55, seg=12):
    """内六角螺钉：杆 + 头 + 六角孔（浅凹）"""
    shank = cyl(f"{name}_s", r, depth, axis=axis, loc=loc, mat=mat, col=col, seg=seg, bw=0.0002, segs=1)
    hloc = list(loc)
    idx = 'XYZ'.index(axis)
    hloc[idx] += depth / 2 + 0.0006
    hd = cyl(f"{name}_h", r * head, 0.0012, axis=axis, loc=tuple(hloc), mat=mat, col=col, seg=seg, bw=0.0002, segs=1)
    socket = cyl(f"{name}_k", r * 0.72, 0.0018, axis=axis, loc=tuple(hloc), mat=mat, col=col, seg=6, bw=0, segs=1)
    cut(hd, socket)
    return [shank, hd]


def text_mesh(name, body, size=0.006, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, col=None,
              extrude=0.00012, align='CENTER', space=1.0):
    cu = bpy.data.curves.new(name + "_c", 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = 'CENTER'
    cu.space_character = space
    ob = bpy.data.objects.new(name, cu)
    link(ob, col)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    # 关键：new_from_object 给的是**局部坐标**，必须把物体的世界变换烘进网格，否则刻字全堆在原点
    me.transform(ob.matrix_world)
    m2 = bpy.data.objects.new(name, me)
    m2.matrix_world.identity()
    link(m2, col)
    if mat:
        me.materials.append(mat)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu, do_unlink=True) if cu.users == 0 else None
    return m2


def deselect_all():
    for o in bpy.context.view_layer.objects:
        try:
            o.select_set(False)
        except Exception:
            pass


def join(objs, name=None):
    objs = [o for o in objs if o]
    base = objs[0]
    deselect_all()
    bpy.context.view_layer.objects.active = base
    for o in objs:
        try:
            o.select_set(True)
        except Exception:
            pass
    bpy.ops.object.join()
    base.select_set(False)
    if name:
        base.name = name
    return base


def shade_smooth(ob, angle=35.0):
    set_smooth_by_angle(ob, angle)


def set_origin(ob, world_point):
    """把原点移到世界坐标点（保持几何位置不变）"""
    p = Vector(world_point)
    mw = ob.matrix_world.copy()
    off = p - mw.translation
    me = ob.data
    for v in me.vertices:
        v.co -= ob.matrix_world.inverted() @ p * 0 + (ob.matrix_world.inverted().to_3x3() @ off)
    ob.location = p
    me.update()


def local_bbox(ob):
    xs = [v.co for v in ob.data.vertices]
    mn = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    mx = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    return mn, mx


def uv_box(ob, scale=1.0):
    """快速盒式 UV（按世界尺度平铺），无 ops 依赖"""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0]
    for poly in me.polygons:
        n = poly.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            if ax >= ay and ax >= az:
                u, w = v.y, v.z
            elif ay >= az:
                u, w = v.x, v.z
            else:
                u, w = v.x, v.y
            uvl.data[li].uv = (u * scale, w * scale)
    me.update()


# ================================================================ starship 追加
from mathutils import Matrix as _M


def mat_from_axes(x_axis, y_axis, z_axis, loc=(0, 0, 0)):
    """由三个轴向量构造 4x4 矩阵（列 = 轴），用于把零件摆到任意朝向上"""
    m = _M.Identity(4)
    for i in range(3):
        m[i][0] = x_axis[i]
        m[i][1] = y_axis[i]
        m[i][2] = z_axis[i]
        m[i][3] = loc[i]
    return m


def tag(ob, pid, zh, en, group, order=None, explode=None, note=""):
    """给零件打元数据：Three.js 侧一次点击就能按 order 拆、按 explode 飞"""
    ob["part_id"] = pid
    ob["label_zh"] = zh
    ob["label_en"] = en
    ob["group"] = group
    ob["order"] = int(order if order is not None else 0)
    ob["explode"] = [float(v) for v in (explode or (0, 0, 0))]
    ob["note"] = note
    return ob


def part(ob, pid, zh, en, group, direction, order=None, note="", explode=None):
    """打标签 + 自动按组换算爆炸位移（direction 只要给粗方向）"""
    import spec as _S
    if explode is None:
        explode = _S.explode_for(group, direction)
    return tag(ob, pid, zh, en, group, order=order, explode=explode, note=note)


def bolt_ring(name, cx, cy, cz, r, count, axis='X', mat=None, col=None, br=0.028, bh=0.016):
    """一圈螺栓（沿给定轴的法平面）"""
    obs = []
    for i in range(count):
        a = math.tau * i / count
        if axis == 'X':
            loc = (cx, cy + r * math.cos(a), cz + r * math.sin(a))
        elif axis == 'Y':
            loc = (cx + r * math.cos(a), cy, cz + r * math.sin(a))
        else:
            loc = (cx + r * math.cos(a), cy + r * math.sin(a), cz)
        obs.append(cyl("%s_b%d" % (name, i), br, bh, axis=axis, loc=loc, mat=mat, col=col,
                       seg=6, bw=0.0012, segs=1))
    return join(obs, name)


def vent_grill(name, w, h, slats, depth=0.02, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, col=None):
    """散热格栅：底板 + 一排斜百叶（飞船表面细节里性价比最高的件）"""
    base = box(name + "_base", (w, depth, h), loc=loc, rot=rot, mat=mat, col=col, bw=0.002, seg=1)
    obs = [base]
    n = max(2, slats)
    for i in range(n):
        t = (i + 0.5) / n
        z = loc[2] - h / 2 + h * t
        s = box("%s_s%d" % (name, i), (w * 0.94, depth * 1.6, h / n * 0.62),
                loc=(loc[0], loc[1], z), rot=(rot[0], rot[1] + math.radians(28), rot[2]),
                mat=mat, col=col, bw=0.0012, seg=1)
        obs.append(s)
    return join(obs, name)


def greeble(name, region, count=60, seed=1, mat=None, col=None, scale=1.0):
    """随机小方块/圆柱堆 —— region = (x0,x1,y0,y1,z0,z1)，一个平面区域上的机械碎件"""
    import random
    rnd = random.Random(seed)
    x0, x1, y0, y1, z0, z1 = region
    obs = []
    for i in range(count):
        w = rnd.uniform(0.05, 0.30) * scale
        d = rnd.uniform(0.05, 0.22) * scale
        h = rnd.uniform(0.02, 0.09) * scale
        x = rnd.uniform(x0 + w, x1 - w) if x1 - x0 > 2 * w else (x0 + x1) / 2
        y = rnd.uniform(y0 + d, y1 - d) if y1 - y0 > 2 * d else (y0 + y1) / 2
        z = rnd.choice([z0, z1])
        if rnd.random() < 0.30:
            o = cyl("%s_c%d" % (name, i), min(w, d) * 0.5, h * 1.6, axis='Z',
                    loc=(x, y, z), mat=mat, col=col, seg=8, bw=0.0015, segs=1)
        else:
            o = box("%s_b%d" % (name, i), (w, d, h), loc=(x, y, z), mat=mat, col=col,
                    bw=0.0015, seg=1)
        obs.append(o)
    return join(obs, name)


def pipe_run(name, pts, r, mat=None, col=None, seg=8, elbow=True):
    """沿折线走一圈管路（用圆柱段拼，拐角补球）"""
    obs = []
    for i in range(len(pts) - 1):
        a = Vector(pts[i])
        b = Vector(pts[i + 1])
        d = b - a
        L = d.length
        if L < 1e-5:
            continue
        o = cyl("%s_s%d" % (name, i), r, L, axis='Z', loc=tuple((a + b) / 2),
                mat=mat, col=col, seg=seg, bw=0.0015, segs=1)
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        obs.append(o)
        if elbow and i < len(pts) - 2:
            obs.append(cyl("%s_e%d" % (name, i), r * 1.12, r * 1.6, axis='Z',
                           loc=tuple(b), mat=mat, col=col, seg=seg, bw=0.001, segs=1))
    return join(obs, name)
