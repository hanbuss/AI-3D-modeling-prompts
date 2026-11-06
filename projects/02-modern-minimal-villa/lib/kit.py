"""几何内核：把大量细节压进少量 mesh 的累积式构建器。

设计原则
- 每个 object = 一个 GB 累积出来的多材质 mesh，避免上千个物体。
- 所有图元先在局部坐标生成，再用 self.M（可嵌套 frame）变换到世界。
- 面材质按名字登记，材质列表顺序与面材质索引一致，导出 glTF 时一一对应。
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler

TAU = math.tau
D = math.radians
I4 = Matrix.Identity(4)


# ---------------------------------------------------------------- 小工具
def lerp(a, b, t):
    return a + (b - a) * t


def c3(center):
    """中心点容错：允许 (x,y) 两元素。"""
    c = tuple(center)
    return c if len(c) == 3 else (c + (0.0, 0.0))[:3]


def vlerp(a, b, t):
    return tuple(lerp(a[i], b[i], t) for i in range(len(a)))


def bounds_center(b):
    (x0, x1), (y0, y1), (z0, z1) = b
    return ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def bounds_size(b):
    (x0, x1), (y0, y1), (z0, z1) = b
    return (x1 - x0, y1 - y0, z1 - z0)


class GB:
    """Geometry builder."""

    def __init__(self, name="gb", smooth_angle=35.0):
        self.name = name
        self.verts = []
        self.faces = []       # list[list[int]]
        self.face_mats = []   # parallel material name per face
        self.face_smooth = []
        self.materials = []   # ordered unique names
        self.M = I4.copy()
        self.smooth_angle = smooth_angle

    # -- 变换栈 --------------------------------------------------
    def frame(self, mat4):
        return _Frame(self, mat4)

    def xform(self, verts):
        M = self.M
        return [tuple(M @ Vector(v)) for v in verts]

    # -- 材质登记 --------------------------------------------------
    def mi(self, name):
        if name not in self.materials:
            self.materials.append(name)
        return self.materials.index(name)

    # -- 面登记 ----------------------------------------------------
    def _add_faces(self, verts, faces, mat, smooth=False):
        base = len(self.verts)
        self.verts.extend(self.xform(verts))
        mi = self.mi(mat)
        for f in faces:
            self.faces.append([base + i for i in f])
            self.face_mats.append(mat)
            self.face_smooth.append(smooth)
        return mi

    # ============================================================
    # 图元
    # ============================================================
    def box(self, size, center=(0, 0, 0), rot=None, mat="M_WallWhite", smooth=False):
        sx, sy, sz = size
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
             (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
        f = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
             [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
        if rot is not None:
            v = [tuple(rot @ Vector(p)) for p in v]
        v = [(p[0] + center[0], p[1] + center[1], p[2] + center[2]) for p in v]
        self._add_faces(v, f, mat, smooth)

    def boxb(self, b, mat="M_WallWhite", smooth=False):
        """由世界/局部边界 ((x0,x1),(y0,y1),(z0,z1)) 生成盒子。"""
        (x0, x1), (y0, y1), (z0, z1) = b
        self.box((x1 - x0, y1 - y0, z1 - z0), bounds_center(b), mat=mat, smooth=smooth)

    def plane(self, b, mat="M_Rug", z=None):
        """水平面（朝上），b=((x0,x1),(y0,y1))。"""
        (x0, x1), (y0, y1) = b
        zz = z if z is not None else 0.0
        v = [(x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz)]
        self._add_faces(v, [[0, 1, 2, 3]], mat)

    def quad(self, p0, p1, p2, p3, mat="M_WallWhite", smooth=False):
        self._add_faces([p0, p1, p2, p3], [[0, 1, 2, 3]], mat, smooth)

    def cyl(self, r, h, center=(0, 0, 0), axis="Z", seg=20, mat="M_Wood",
            r_top=None, caps=True, smooth=True, rot=None):
        center = c3(center)
        r_top = r if r_top is None else r_top
        ring = []
        for i in range(seg):
            a = TAU * i / seg
            ring.append((math.cos(a), math.sin(a)))
        v = []
        for (cx, cy) in ring:
            v.append((cx * r, cy * r, -h / 2))
        for (cx, cy) in ring:
            v.append((cx * r_top, cy * r_top, h / 2))
        f = []
        for i in range(seg):
            j = (i + 1) % seg
            f.append([i, j, seg + j, seg + i])
        if caps:
            f.append(list(range(seg - 1, -1, -1)))
            f.append(list(range(seg, seg * 2)))
        # 轴向
        if axis == "X":
            v = [(p[2], p[0], p[1]) for p in v]
        elif axis == "Y":
            v = [(p[1], p[2], p[0]) for p in v]
        if rot is not None:
            v = [tuple(rot @ Vector(p)) for p in v]
        v = [(p[0] + center[0], p[1] + center[1], p[2] + center[2]) for p in v]
        self._add_faces(v, f, mat, smooth=smooth)

    def sphere(self, r, center=(0, 0, 0), seg=18, rings=12, mat="M_LeafGreen",
               scale=(1, 1, 1), smooth=True):
        center = c3(center)
        v = []
        f = []
        for i in range(rings + 1):
            th = math.pi * i / rings
            z = math.cos(th)
            rr = math.sin(th)
            for j in range(seg):
                a = TAU * j / seg
                v.append((math.cos(a) * rr * r * scale[0],
                          math.sin(a) * rr * r * scale[1],
                          z * r * scale[2]))
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                a = i * seg + j
                b = i * seg + j2
                c = (i + 1) * seg + j2
                d = (i + 1) * seg + j
                f.append([a, b, c, d])
        v = [(p[0] + center[0], p[1] + center[1], p[2] + center[2]) for p in v]
        self._add_faces(v, f, mat, smooth=smooth)

    def prism(self, profile, thick, center=(0, 0, 0), axis="Z", mat="M_Wood",
              smooth=False, scale=(1, 1)):
        """profile: [(u,v)] 闭合多边形，沿 axis 挤 thick。"""
        center = c3(center)
        n = len(profile)
        v = []
        for s in (-thick / 2, thick / 2):
            for (u, vv) in profile:
                v.append((u * scale[0], vv * scale[1], s))
        f = [[i for i in range(n - 1, -1, -1)], [n + i for i in range(n)]]
        for i in range(n):
            j = (i + 1) % n
            f.append([i, j, n + j, n + i])
        if axis == "X":
            v = [(p[2], p[0], p[1]) for p in v]
        elif axis == "Y":
            v = [(p[1], p[2], p[0]) for p in v]
        v = [(p[0] + center[0], p[1] + center[1], p[2] + center[2]) for p in v]
        self._add_faces(v, f, mat, smooth=smooth)

    def lathe(self, profile, seg=24, center=(0, 0, 0), mat="M_Porcelain", smooth=True):
        """profile: [(r,z)] 由下到上，绕 Z 旋转。"""
        center = c3(center)
        v = []
        for (r, z) in profile:
            for j in range(seg):
                a = TAU * j / seg
                v.append((math.cos(a) * r, math.sin(a) * r, z))
        f = []
        n = len(profile)
        for i in range(n - 1):
            for j in range(seg):
                j2 = (j + 1) % seg
                a = i * seg + j
                b = i * seg + j2
                c = (i + 1) * seg + j2
                d = (i + 1) * seg + j
                f.append([a, b, c, d])
        v = [(p[0] + center[0], p[1] + center[1], p[2] + center[2]) for p in v]
        self._add_faces(v, f, mat, smooth=smooth)

    def grid_panel(self, b, cols, rows, bar=0.03, depth=0.03, mat="M_WoodDark",
                   frame=0.05):
        """木格栅：b=((x0,x1),(y0,y1),(z0,z1))，在 z0~z1 立面内做井字格。"""
        (x0, x1), (y0, y1), (z0, z1) = b
        yc = (y0 + y1) / 2
        w = x1 - x0
        h = z1 - z0
        # 外框
        if frame > 0:
            self.box((w, depth, frame), (x0 + w / 2, yc, z0 + frame / 2), mat=mat)
            self.box((w, depth, frame), (x0 + w / 2, yc, z1 - frame / 2), mat=mat)
            self.box((frame, depth, h), (x0 + frame / 2, yc, z0 + h / 2), mat=mat)
            self.box((frame, depth, h), (x1 - frame / 2, yc, z0 + h / 2), mat=mat)
        ix0, ix1 = x0 + frame, x1 - frame
        iz0, iz1 = z0 + frame, z1 - frame
        for i in range(1, cols):
            x = lerp(ix0, ix1, i / cols)
            self.box((bar, depth, iz1 - iz0), (x, yc, (iz0 + iz1) / 2), mat=mat)
        for j in range(1, rows):
            z = lerp(iz0, iz1, j / rows)
            self.box((ix1 - ix0, depth, bar), ((ix0 + ix1) / 2, yc, z), mat=mat)

    # ============================================================
    def stats(self):
        return len(self.verts), len(self.faces), len(self.materials)


def box_uv(me, scale=2.0):
    """三向 box 投影生成 UV（按面法线取主轴），保证任意物体贴图密度一致。"""
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    inv = 1.0 / scale
    loops = me.loops
    uvl = uv.data
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y, co.z
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            uvl[li].uv = (u * inv, v * inv)


class _Frame:
    def __init__(self, gb, mat4):
        self.gb = gb
        self.mat4 = mat4
        self.old = None

    def __enter__(self):
        self.old = self.gb.M
        self.gb.M = self.old @ self.mat4
        return self.gb

    def __exit__(self, *a):
        self.gb.M = self.old
        return False


# ---------------------------------------------------------------- 材质
def principled(mat):
    """按节点类型取 Principled（中文界面的 Blender 会把节点名本地化成「原理化 BSDF」，不能按名字找）。"""
    if not mat or not mat.node_tree:
        return None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _set_in(node, name, val):
    if name in node.inputs:
        try:
            node.inputs[name].default_value = val
            return True
        except Exception:
            return False
    return False


def make_material(name, base=(0.8, 0.8, 0.8, 1.0), rough=0.6, metal=0.0,
                  alpha=1.0, emit=None, emit_strength=0.0, metallic_map=None,
                  noise=None, sheen=0.0):
    """noise=(scale, detail, bump_strength) 只用于 Blender 渲染观感，不导出。"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = principled(m)
    _set_in(bsdf, "Base Color", base)
    _set_in(bsdf, "Roughness", rough)
    _set_in(bsdf, "Metallic", metal)
    _set_in(bsdf, "Alpha", alpha)
    if emit is not None:
        _set_in(bsdf, "Emission Color", emit)
        _set_in(bsdf, "Emission Strength", emit_strength)
    if sheen:
        _set_in(bsdf, "Sheen Weight", sheen)
    if noise:
        sc, det, bs = noise
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = sc
        tex.inputs["Detail"].default_value = det
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bs
        nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if alpha < 1.0:
        m.blend_method = "BLEND"
        try:
            m.show_transparent_back = False
        except Exception:
            pass
    m.diffuse_color = (base[0], base[1], base[2], max(alpha, 0.35))
    m.roughness = rough
    m.metallic = metal
    return m


# ---------------------------------------------------------------- 场景装配
class Ctx:
    """收集 object、按层归集、导出。"""

    def __init__(self):
        self.colls = {}
        self.empties = {}
        self.layer_of = {}
        self.objects = []
        self.rooms = []
        self.layer = "SITE"

    def coll(self, name):
        if name in self.colls:
            return self.colls[name]
        c = bpy.data.collections.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(c)
        self.colls[name] = c
        # 该层的空物体（GLB 里的分层节点）
        e = bpy.data.objects.get(name)
        if e is None:
            e = bpy.data.objects.new(name, None)
            c.objects.link(e)
            e.empty_display_size = 0.6
            e.empty_display_type = "PLAIN_AXES"
        self.empties[name] = e
        return c

    def use(self, layer):
        self.coll(layer)
        self.layer = layer

    def mesh(self, gb, name, matnames=None, parent=None, smooth=None, uv_scale=2.0):
        """uv_scale: 一张贴图覆盖的真实米数；UV = 世界坐标 / uv_scale。"""
        me = bpy.data.meshes.new(name)
        me.from_pydata(gb.verts, [], gb.faces)
        me.validate(verbose=False)
        for mn in gb.materials:
            m = bpy.data.materials.get(mn)
            if m is None:
                m = make_material(mn, base=(0.62, 0.60, 0.58, 1.0), rough=0.7)
                print("[kit] WARN missing material auto-created:", mn)
            me.materials.append(m)
        # 面材质
        for i, poly in enumerate(me.polygons):
            if i < len(gb.face_mats):
                poly.material_index = gb.materials.index(gb.face_mats[i])
                poly.use_smooth = gb.face_smooth[i]
        me.update()
        # 外法线
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()
        if uv_scale:
            box_uv(me, uv_scale)
        ob = bpy.data.objects.new(name, me)
        self.coll(self.layer).objects.link(ob)
        # 父级
        pname = parent or self.layer
        ob.parent = self.empties.get(pname) or self.empties.get(self.layer)
        self.objects.append(ob)
        self.layer_of[ob.name] = self.layer
        return ob

    def empty(self, name, layer=None):
        layer = layer or self.layer
        c = self.coll(layer)
        e = bpy.data.objects.new(name, None)
        c.objects.link(e)
        e.parent = self.empties[layer]
        e.empty_display_size = 0.3
        return e

    def room(self, rid, zh, en, floor, pos, area, desc=""):
        """pos 传入 (x, z, y) 的 Blender 习惯写法；落盘转成 glTF 的 Y-up：(x, z, -y)。"""
        gx, gz, gy = pos[0], pos[1], pos[2]
        self.rooms.append(dict(id=rid, zh=zh, en=en, floor=floor,
                               pos=[round(gx, 2), round(gz, 2), round(-gy, 2)],
                               area=round(area, 1), desc=desc))
