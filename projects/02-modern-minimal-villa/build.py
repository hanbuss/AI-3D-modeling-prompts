# -*- coding: utf-8 -*-
"""现代简约别墅 · 总装。

用法（无头）：
    blender -b --factory-startup \
        --python build.py -- [--only=arch,court,rooms] [--no-export] [--save]

产物：mvilla/mvilla.blend / mvilla.glb / rooms.json
"""
import os
import sys
import math
import json
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
from mathutils import Vector, Matrix

from lib import kit, mats, mats2
from lib.kit import GB, Ctx

# ------------------------------------------------------------------ 参数
def _argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


ARGS = {}
for _a in _argv():
    if "=" in _a and _a.startswith("--"):
        k, v = _a[2:].split("=", 1)
        ARGS[k] = v
    elif _a.startswith("--"):
        ARGS[_a[2:]] = "1"

ONLY = set(ARGS.get("only", "site,arch,court,rooms").split(","))
NO_EXPORT = "no-export" in ARGS
DO_SAVE = "save" in ARGS


# ------------------------------------------------------------------ 清场
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    # 引擎名各版本不同：5.x 回到 BLENDER_EEVEE，4.2~4.5 叫 BLENDER_EEVEE_NEXT
    available = [e.identifier for e in
                 bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if eng in available:
            try:
                sc.render.engine = eng
                break
            except Exception:
                continue
    print("[build] engine =", sc.render.engine)
    return sc


# ------------------------------------------------------------------ 世界 / 太阳
def setup_world(sc, mode="day"):
    w = bpy.data.worlds.new("W_Modern")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    r = ramp.color_ramp
    r.interpolation = "EASE"
    if mode == "day":
        stops = [(0.42, (0.60, 0.57, 0.52, 1)), (0.50, (0.88, 0.90, 0.90, 1)),
                 (0.58, (0.66, 0.78, 0.96, 1)), (1.00, (0.22, 0.44, 0.88, 1))]
        bg.inputs["Strength"].default_value = 1.25
    else:
        stops = [(0.42, (0.020, 0.024, 0.036, 1)), (0.50, (0.075, 0.095, 0.150, 1)),
                 (0.62, (0.030, 0.048, 0.105, 1)), (1.00, (0.010, 0.014, 0.034, 1))]
        bg.inputs["Strength"].default_value = 1.0
    r.elements[0].position = stops[0][0]
    r.elements[0].color = stops[0][1]
    r.elements[1].position = stops[-1][0]
    r.elements[1].color = stops[-1][1]
    for pos, col in stops[1:-1]:
        e = r.elements.new(pos)
        e.color = col
    return w


def add_sun(sc, mode="day"):
    """太阳光：参考图是阴天/柔和晴天，长阴影，偏暖。"""
    sd = bpy.data.lights.new("Sun", type="SUN")
    sd.angle = math.radians(1.4)
    if mode == "day":
        sd.energy = 4.2
        sd.color = (1.0, 0.965, 0.912)
        rot = (math.radians(48), 0.0, math.radians(-52))
    else:
        sd.energy = 0.35
        sd.color = (0.72, 0.80, 1.0)
        rot = (math.radians(58), 0.0, math.radians(-40))
    ob = bpy.data.objects.new("Sun", sd)
    sc.collection.objects.link(ob)
    ob.rotation_euler = rot
    ob.location = (10, -10, 20)
    return ob


def add_fill_area(sc):
    """补光：模拟天空漫射打在立面，避免背光面死黑。"""
    ld = bpy.data.lights.new("FillSky", type="AREA")
    ld.shape = "RECTANGLE"
    ld.size = 24.0
    ld.size_y = 18.0
    ld.energy = 260.0
    ld.color = (0.86, 0.90, 1.0)
    ob = bpy.data.objects.new("FillSky", ld)
    sc.collection.objects.link(ob)
    ob.location = (0.0, -18.0, 16.0)
    ob.rotation_euler = (math.radians(58), 0.0, 0.0)
    return ob


# ------------------------------------------------------------------ 场地
def build_site(ctx):
    """场地：基底土、院墙外街道、远景地面、周边林带与邻栋。"""
    import random as _rnd
    from lib import nature

    ctx.use("SITE")
    g = GB("site_ground")
    # 院内基础地坪（石材铺装由 court 负责盖面，这里只做兜底底板）
    g.plane(((-9.6, 9.6), (-14.6, 10.6)), z=-0.06, mat="M_Concrete")
    # 院外一圈地坪（薄板）。顶面必须低于院内底板 z=-0.06，否则会把整个场地盖成绿色
    g.box((66.0, 66.0, 0.30), (0, 0, -0.42), mat="M_Lawn")
    # 街道（南侧）
    g.plane(((-33.0, 33.0), (-19.0, -14.60)), z=-0.02, mat="M_Asphalt")
    g.plane(((-33.0, 33.0), (-19.4, -19.0)), z=-0.01, mat="M_PaveGrey")
    for i in range(-8, 9):
        g.plane(((i * 4.0 - 0.08, i * 4.0 + 0.08), (-19.42, -19.0)), z=0.0, mat="M_RoadLine")
    ctx.mesh(g, "SITE_Ground", uv_scale=4.0)

    # ---- 周边林带：PolyHaven 真三维模型（fir / 阔叶），实例共享 mesh，GLB 只写一份几何
    from lib import assets2
    rng = _rnd.Random(20261106)
    # 5 个真树品种，全部按「自然高度 ±30%」用：
    #   fir / pine 是针叶，island_tree_01（5.0m）/ tree_small_02（4.55m）是密叶阔叶。
    #   千万别把 5 m 的树拉到 8.5 m —— 会变细长扫帚。
    KINDS = [("fir_tree_01", 7.0, 10.0, 4.4), ("pine_tree_01", 8.0, 12.0, 5.0),
             ("island_tree_01", 4.6, 6.2, 6.0), ("tree_small_02", 3.4, 4.6, 5.2),
             ("island_tree_02", 3.0, 4.2, 5.2), ("island_tree_01", 5.0, 6.4, 6.2),
             ("pine_tree_01", 7.0, 10.5, 4.4), ("tree_small_02", 3.6, 4.8, 5.4)]
    placed = []

    def ring(n, rmax, ymin, ymax, hmin, hmax):
        for i in range(n):
            for _try in range(28):
                x = rng.uniform(-rmax, rmax)
                y = rng.uniform(ymin, ymax)
                if -12.0 < x < 12.0 and -22.0 < y < 14.0:
                    continue
                if abs(x) < 13.0 and -21.0 < y < -14.0:
                    continue
                if -16.0 < x < 32.0 and -34.0 < y < -15.0:
                    continue
                if any((x - c[0][0]) ** 2 + (y - c[0][1]) ** 2 < 100.0
                       for c in CAMS.values()):
                    continue
                if all((x - px) ** 2 + (y - py) ** 2 > 30.0 for px, py in placed):
                    placed.append((x, y))
                    kind, kmin, kmax, wmax = KINDS[i % len(KINDS)]
                    hh = rng.uniform(max(hmin, kmin), min(hmax, kmax))
                    assets2.instance(ctx, "SITE", kind, "t%02d_%02d" % (i, _try),
                                     x, y, z=0.0, height=hh,
                                     max_w=wmax + rng.uniform(-0.6, 0.9),
                                     rot=rng.uniform(0, 6.283))
                    break

    ring(22, 30.0, -6.0, 32.0, 5.0, 11.0)      # 北侧背景林
    ring(9, 24.0, -24.0, -6.0, 4.0, 8.0)       # 西
    ring(9, 24.0, -24.0, -6.0, 4.0, 8.0)       # 东
    ring(5, 31.0, -40.0, -22.0, 5.0, 9.0)      # 街对面

    # ---- 邻栋：三级真房子（lib/houses.py）
    from lib import houses
    gn = GB("site_neighbors")
    NB = [(-27.0, -33.0, 9.0, 8.0, 7.4, 0, 0.05),
          (27.0, -34.0, 10.0, 8.5, 6.8, 1, -0.04),
          (-25.0, 30.0, 11.0, 9.0, 9.2, 2, 0.0),
          (25.5, 32.0, 10.5, 9.0, 8.6, 0, 3.10),
          (-38.0, -40.0, 12.0, 9.0, 6.4, 1, 0.02),
          (38.0, -39.0, 11.0, 9.0, 7.2, 2, -0.03)]
    for k, (nx, ny, w, d, h, var, rt) in enumerate(NB):
        houses.neighbour(gn, nx, ny, w, d, h, var, rot=rt)
    ctx.mesh(gn, "SITE_Neighbors", uv_scale=4.0)


# ------------------------------------------------------------------ 相机
CAMS = {
    "CAM_Aerial":  ((21.0, -30.0, 23.0), (0.0, -3.0, 2.6), 36.0),
    "CAM_Hero":    ((12.6, -19.0, 6.4), (-0.8, -3.0, 3.0), 32.0),
    "CAM_Front":   ((0.0, -26.0, 4.0), (0.0, -1.0, 4.6), 34.0),
    "CAM_Entry":   ((0.0, -17.5, 1.85), (0.0, -3.0, 2.6), 28.0),
    "CAM_Court":   ((-8.0, -12.6, 5.6), (2.2, -5.2, 1.4), 30.0),
    "CAM_Pergola": ((1.2, -12.2, 2.4), (6.4, -5.6, 1.9), 30.0),
    "CAM_Deck":    ((4.6, -12.0, 3.2), (-6.4, -5.4, 0.9), 32.0),
    "CAM_Water":   ((-1.0, -8.0, 2.2), (8.2, -3.4, 1.6), 30.0),
    "CAM_Interior": ((-4.4, -1.2, 1.75), (-6.2, 6.0, 1.6), 22.0),
    "CAM_Roof":    ((-14.0, -6.0, 17.0), (0.0, 2.0, 6.0), 40.0),
}


def aim(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def build_cams(sc):
    ctx_cams = {}
    for name, (loc, tgt, lens) in CAMS.items():
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start = 0.05
        cd.clip_end = 400.0
        ob = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(ob)
        ob.location = loc
        aim(ob, tgt)
        ctx_cams[name] = ob
    sc.camera = ctx_cams["CAM_Hero"]
    return ctx_cams


# ------------------------------------------------------------------ 主流程
def main():
    sc = reset_scene()
    setup_world(sc, ARGS.get("mode", "day"))
    add_sun(sc, ARGS.get("mode", "day"))
    add_fill_area(sc)

    mats.build_all()
    mats2.build_all()

    ctx = Ctx()
    ctx.use("SITE")
    if "site" in ONLY:
        build_site(ctx)

    loaded = []
    for mod_name, key in (("arch2", "arch"), ("court", "court"), ("rooms", "rooms")):
        if key not in ONLY:
            continue
        try:
            mod = importlib.import_module("lib." + mod_name)
            importlib.reload(mod)
            fn = getattr(mod, "build", None)
            if fn is None:
                print(f"[build] SKIP {mod_name}: no build()")
                continue
            ctx.use(key.upper())
            fn(ctx)
            loaded.append(mod_name)
            print(f"[build] OK {mod_name}")
        except ModuleNotFoundError:
            print(f"[build] MISS {mod_name}.py (not written yet)")
        except Exception as e:
            import traceback
            print(f"[build] FAIL {mod_name}: {type(e).__name__}: {e}")
            traceback.print_exc()

    cams = build_cams(sc)

    # 灯光（室内 + 园林 + 水景 + 树下射灯）
    try:
        from lib import lights
        lights.build(sc, ctx)
    except Exception as e:
        print("[build] lights FAIL:", type(e).__name__, e)

    # 统计
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    n_obj = len(meshes)
    tris = sum(len(o.data.polygons) for o in meshes)
    print(f"[build] modules={loaded} meshes={n_obj} faces={tris} rooms={len(ctx.rooms)}")

    # 每层包围盒（越界/悬空一眼可见）
    for layer in sorted(ctx.colls.keys()):
        cols = ctx.colls[layer]
        xs, ys, zs = [], [], []
        for ob in cols.objects:
            if ob.type != "MESH":
                continue
            for c in ob.bound_box:
                w = ob.matrix_world @ Vector(c)
                xs.append(w.x); ys.append(w.y); zs.append(w.z)
        if not xs:
            continue
        print(f"[bbox] {layer:10s} X[{min(xs):7.2f},{max(xs):7.2f}] "
              f"Y[{min(ys):7.2f},{max(ys):7.2f}] Z[{min(zs):6.2f},{max(zs):6.2f}]")

    # 房间元数据
    with open(os.path.join(HERE, "rooms.json"), "w", encoding="utf-8") as f:
        json.dump(dict(cameras=list(CAMS.keys()), rooms=ctx.rooms), f,
                  ensure_ascii=False, indent=1)

    if DO_SAVE:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "mvilla.blend"))
        print("[build] saved mvilla.blend")

    if not NO_EXPORT:
        export_all()

    print("[build] DONE")


def export_all():
    path = os.path.join(HERE, "mvilla.glb")
    props = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    kw = dict(filepath=path, export_format="GLB",
              export_apply=True, export_yup=True, use_selection=False,
              export_cameras=False, export_lights=False, export_extras=True,
              export_materials="EXPORT", export_image_format="AUTO")
    for k, v in (("export_texcoords", True), ("export_normals", True),
                 ("export_extras", True)):
        if k in props:
            kw[k] = v
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError as e:
        print("[build] gltf kw rejected, retry minimal:", e)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                                  export_apply=True)
    sz = os.path.getsize(path) / 1e6 if os.path.exists(path) else 0
    print(f"[build] exported {path} {sz:.1f} MB")


if __name__ == "__main__":
    main()
