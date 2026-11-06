# -*- coding: utf-8 -*-
"""分层平面图（俯视正交）+ 剖切透视图。

    blender -b mvilla.blend --python plan_shots.py -- [res=1200x900] [tag=plan]

为每层生成一张：只显该层（保留该层以下的建筑外壳做底），俯视正交。
"""
import bpy
import sys
import os
import math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "previews")

# 层 -> (要显的几何层集合, 相机高度, 正交尺度)
# (可见层, 相机高度, 正交尺度, 中心 x, 中心 y)
# 房子 Y 中心 = (-1.5 + 9.0)/2 = 3.75；院子中心 y ≈ -7.5
PLANS = {
    "1F": ({"SITE", "COURT", "ARCH_1F", "INT_1F"}, 26.0, 26.0, 0.0, -3.4),
    "2F": ({"ARCH_1F", "ARCH_2F", "INT_2F"}, 26.0, 19.0, 0.0, 3.75),
    "3F": ({"ARCH_2F", "ARCH_3F", "INT_3F"}, 26.0, 17.0, -1.5, 3.75),
    "SITE_PLAN": ({"SITE", "COURT"}, 30.0, 30.0, 0.0, -6.0),
}


def argv():
    a = sys.argv
    o = dict(res="1200x900", samples="32", tag="plan")
    for x in (a[a.index("--") + 1:] if "--" in a else []):
        if "=" in x:
            k, v = x.split("=", 1)
            o[k] = v
    return o


def top_layers():
    """收集每个空物体（层节点）下挂的 mesh。"""
    out = {}
    for o in bpy.data.objects:
        p = o
        root = None
        while p:
            if p.type == "EMPTY" and p.name in LAYER_NAMES:
                root = p.name
            p = p.parent
        if root:
            out.setdefault(root, []).append(o)
    return out


LAYER_NAMES = {"SITE", "ARCH_1F", "ARCH_2F", "ARCH_3F", "ROOF", "COURT",
               "INT_1F", "INT_2F", "INT_3F", "GARDEN"}


def setup(o):
    sc = bpy.context.scene
    avail = [e.identifier for e in
             bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in avail else "BLENDER_EEVEE"
    try:
        sc.eevee.taa_render_samples = int(o["samples"])
    except Exception:
        pass
    w, h = [int(v) for v in o["res"].lower().split("x")]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.view_settings.exposure = 0.45
    # 平光：改用顶光，弱对比便于看平面
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.rotation_euler = (math.radians(8), 0, math.radians(-20))
        sun.data.energy = 3.0
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.6


def make_ortho_cam(name, z, scale, cx=0.0, cy=-3.0):
    cd = bpy.data.cameras.new(name)
    cd.type = "ORTHO"
    cd.ortho_scale = scale
    cd.clip_start = 0.1
    cd.clip_end = 200.0
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (cx, cy, z)
    ob.rotation_euler = (0, 0, 0)
    return ob


def main():
    o = argv()
    os.makedirs(OUT, exist_ok=True)
    setup(o)
    groups = top_layers()

    for plan_name, (keep, camz, scale, ccx, ccy) in PLANS.items():
        # 显隐
        for lay, objs in groups.items():
            vis = lay in keep
            for ob in objs:
                if ob.type == "MESH":
                    ob.hide_render = not vis
                    ob.hide_viewport = not vis
        cam = make_ortho_cam("CAM_PLAN_" + plan_name, camz, scale, ccx, ccy)
        bpy.context.scene.camera = cam
        path = os.path.join(OUT, f"PLAN_{plan_name}_{o['tag']}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("[plan] wrote", path, flush=True)

    print("[plan] DONE")


main()
