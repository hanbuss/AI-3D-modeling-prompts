# -*- coding: utf-8 -*-
"""一次性预处理：把 PolyHaven 的 CC0 模型导入、合并、减面、贴图压到 1k，
存成 assets/<name>.blend，之后 build 时用 append 直接取（快且小）。

用法：blender -b --python prep_assets.py -- [name ...]
"""
import bpy
import bmesh
import os
import sys
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# name: (gltf 相对路径, 减面比例, 目标贴图边长)
JOBS = {
    "pine":     ("pine_sapling_small/pine_sapling_small_1k.gltf", 0.12, 512),
    "jacaranda": ("jacaranda_tree/jacaranda_tree_1k.gltf", 0.05, 512),
    "flower":   ("flower_gazania/flower_gazania_1k.gltf", 0.55, 512),
    "cover":    ("periwinkle_plant/periwinkle_plant_1k.gltf", 0.35, 512),
    "shrub":    ("shrub_03/shrub_03_1k.gltf", 0.6, 512),
    "calathea": ("calathea_orbifolia_01/calathea_orbifolia_01_1k.gltf", 0.5, 512),
    "anthurium": ("anthurium_botany_01/anthurium_botany_01_1k.gltf", 0.5, 512),
}


def log(*a):
    print("[prep]", *a, flush=True)


def prep(name, rel, ratio, tex):
    gp = os.path.join(ASSETS, rel)
    if not os.path.exists(gp):
        log(f"SKIP {name}: {gp} 不存在")
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    bpy.ops.import_scene.gltf(filepath=gp)
    log(f"{name}: imported in {time.time()-t0:.1f}s, objects={len(bpy.context.scene.objects)}")

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        log(f"FAIL {name}: 没有 mesh")
        return
    # 合并成一个对象
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    tri0 = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    log(f"{name}: faces~{tri0} verts={len(ob.data.vertices)}")

    # 减面
    if ratio < 1.0:
        md = ob.modifiers.new("dec", "DECIMATE")
        md.ratio = ratio
        md.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=md.name)
        tri1 = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        log(f"{name}: decimate {ratio} -> faces~{tri1}")

    # 贴图压到 tex²
    for im in list(bpy.data.images):
        if im.size[0] > tex or im.size[1] > tex:
            try:
                im.scale(tex, tex)
                log(f"  texture {im.name} -> {tex}")
            except Exception as e:
                log("  tex scale fail", im.name, e)

    # 居中到原点、落地 z=0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    dx, dy, dz = -(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)
    for v in bm.verts:
        v.co.x += dx
        v.co.y += dy
        v.co.z += dz
    bm.to_mesh(ob.data)
    bm.free()
    h = max(zs) - min(zs)
    r = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    ob["src_height"] = h
    ob["src_radius"] = r
    log(f"{name}: 归一化 height={h:.2f} radius={r:.2f}")

    out = os.path.join(ASSETS, f"{name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    log(f"{name}: saved {out} ({os.path.getsize(out)/1048576:.2f} MB)")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for name, (rel, ratio, tex) in JOBS.items():
        if args and name not in args:
            continue
        try:
            prep(name, rel, ratio, tex)
        except Exception as e:
            log(f"ERROR {name}: {e}")


main()
