# -*- coding: utf-8 -*-
"""分层平面图渲染：每层单独出一张俯视正交图（配合"分层查看"）。
用法：blender -b villa.blend --python plan_shots.py -- [res=1100x850]
"""
import bpy
import sys
import os
import json
import math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
LAYERS = ["SITE", "GARDEN", "F1", "F2", "F3", "ROOF"]


def argv():
    a = sys.argv
    o = dict(res="1100x850", samples="32")
    for x in (a[a.index("--") + 1:] if "--" in a else []):
        if "=" in x:
            k, v = x.split("=", 1)
            o[k] = v
    return o


def layer_objects():
    out = {}
    for lay in LAYERS:
        emp = bpy.data.objects.get(lay)
        objs = []
        if emp:
            for o in bpy.data.objects:
                p = o
                while p:
                    if p.name == lay:
                        objs.append(o)
                        break
                    p = p.parent
        out[lay] = objs
    return out


def setup(o):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    try:
        sc.eevee.taa_render_samples = int(o["samples"])
        sc.eevee.use_raytracing = True
        if hasattr(sc.eevee, "use_gtao"):
            sc.eevee.use_gtao = True
    except Exception:
        pass
    w, h = [int(v) for v in o["res"].lower().split("x")]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = 0.35
    # 顶光：平一点，便于看平面
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.data.energy = 3.2
        sun.data.angle = math.radians(6)
        sun.rotation_euler = (math.radians(12), 0, math.radians(-25))
    fill = bpy.data.objects.get("SkyFill")
    if fill:
        fill.data.energy = 1600
        fill.data.size = 40
    w_node = sc.world.node_tree if sc.world else None
    if w_node:
        for n in w_node.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value = 1.6
                n.inputs["Color"].default_value = (0.90, 0.91, 0.93, 1)
    # 相机
    cd = bpy.data.cameras.new("CAM_PLAN")
    cd.type = "ORTHO"
    cam = bpy.data.objects.new("CAM_PLAN", cd)
    sc.collection.objects.link(cam)
    cam.location = (0, 0, 40)
    cam.rotation_euler = (0, 0, 0)
    sc.camera = cam
    return cam


FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
         "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyhbd.ttc"]


def load_font():
    for f in FONTS:
        if os.path.exists(f):
            try:
                return bpy.data.fonts.load(f)
            except Exception:
                continue
    return None


def make_labels(rooms, floors, font):
    """为可见楼层生成房间名文字（俯视可读）。"""
    for r in rooms:
        if r["floor"] not in floors:
            continue
        x, y = r["pos"][0], -r["pos"][2]      # glTF(x,z,-y) -> blender(x,y)
        z = r["pos"][1]
        cu = bpy.data.curves.new(f"LBL_{r['id']}", "FONT")
        cu.body = r["zh"]
        if font:
            cu.font = font
        cu.size = 0.60
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.extrude = 0.004
        ob = bpy.data.objects.new(f"LBL_{r['id']}", cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = (x, y, z + 2.0)
        ob.rotation_euler = (0, 0, 0)
        m = bpy.data.materials.get("M_LabelInk")
        if not m:
            m = bpy.data.materials.new("M_LabelInk")
            m.use_nodes = True
            b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if b:
                b.inputs["Base Color"].default_value = (0.025, 0.022, 0.020, 1)
                b.inputs["Roughness"].default_value = 0.9
            m.diffuse_color = (0.025, 0.022, 0.020, 1)
        cu.materials.append(m)


def clear_labels():
    for ob in list(bpy.data.objects):
        if ob.name.startswith("LBL_"):
            bpy.data.objects.remove(ob, do_unlink=True)


def render_plan(cam, objs, show, path, scale, cx, cy):
    for lay in LAYERS:
        for ob in objs[lay]:
            try:
                hide = lay not in show
                # 平面图不要楼板/吊顶（它们会挡住俯视视线）
                if any(k in ob.name for k in ("_Slab", "_Ceiling")):
                    hide = True
                ob.hide_render = hide
            except Exception:
                pass
    cam.data.ortho_scale = scale
    cam.location = (cx, cy, 40)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[plan] wrote", path)


def main():
    o = argv()
    os.makedirs(os.path.join(HERE, "previews"), exist_ok=True)
    objs = layer_objects()
    cam = setup(o)
    pv = os.path.join(HERE, "previews")
    font = load_font()
    rooms = []
    rp = os.path.join(HERE, "rooms.json")
    if os.path.exists(rp):
        rooms = json.load(open(rp, encoding="utf-8"))["rooms"]
    print("[plan] font:", font.name if font else "DEFAULT(无中文)")
    make_labels(rooms, {"F1"}, font)
    render_plan(cam, objs, {"SITE", "GARDEN", "F1"}, os.path.join(pv, "PLAN_F1.png"),
                21.0, 0.0, -0.5)
    clear_labels()
    make_labels(rooms, {"F2"}, font)
    render_plan(cam, objs, {"SITE", "F2"}, os.path.join(pv, "PLAN_F2.png"),
                21.0, 0.0, -0.5)
    clear_labels()
    make_labels(rooms, {"F3"}, font)
    render_plan(cam, objs, {"SITE", "F3"}, os.path.join(pv, "PLAN_F3.png"),
                21.0, 0.0, 1.0)
    clear_labels()
    make_labels(rooms, {"GARDEN"}, font)
    render_plan(cam, objs, {"SITE", "GARDEN", "F1", "F2", "F3", "ROOF"},
                os.path.join(pv, "PLAN_SITE.png"), 46.0, 0.0, -1.0)
    clear_labels()
    print("[plan] DONE")


main()
