# -*- coding: utf-8 -*-
"""渲染预览：python script via blender -b villa.blend --python render_shots.py -- [args]"""
import bpy
import sys
import os
import math
import json

HERE = os.path.dirname(os.path.abspath(__file__))


def argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def parse(args):
    o = dict(cams="CAM_Hero", res="1280x720", samples="64", mode="day",
             engine="eevee", tag="")
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            o[k] = v
    return o


def set_world(mode, hour):
    """垂直渐变天光：方向向量的 Z 分量做 ramp，稳定不挑引擎。"""
    w = bpy.context.scene.world
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
        stops = [(0.44, (0.62, 0.58, 0.50, 1)), (0.50, (0.90, 0.90, 0.86, 1)),
                 (0.62, (0.62, 0.76, 0.94, 1)), (1.0, (0.26, 0.46, 0.86, 1))]
        bg.inputs["Strength"].default_value = 1.15
    else:
        stops = [(0.44, (0.03, 0.035, 0.05, 1)), (0.50, (0.09, 0.11, 0.18, 1)),
                 (0.64, (0.04, 0.06, 0.13, 1)), (1.0, (0.012, 0.016, 0.04, 1))]
        bg.inputs["Strength"].default_value = 1.0
    r.elements[0].position = stops[0][0]
    r.elements[0].color = stops[0][1]
    r.elements[1].position = stops[-1][0]
    r.elements[1].color = stops[-1][1]
    for pos, col in stops[1:-1]:
        e = r.elements.new(pos)
        e.color = col


def apply_mode(mode):
    sc = bpy.context.scene
    sun = bpy.data.objects.get("Sun")
    fill = bpy.data.objects.get("SkyFill")
    if mode == "day":
        set_world("day", 14)
        if sun:
            sun.data.energy = 4.6
            sun.data.color = (1.0, 0.95, 0.86)
            sun.rotation_euler = (math.radians(54), 0, math.radians(-34))
            sun.location = (14, -18, 22)
        if fill:
            fill.data.energy = 900
            fill.data.size = 30
            fill.data.color = (0.78, 0.87, 1.0)
        for ob in bpy.data.lights:
            if ob.name.startswith("Lamp"):
                ob.energy = 22
        emis = {"M_WinGlow": 0.25, "M_LampShade": 0.55, "M_Screen": 0.15}
    else:
        set_world("night", 22)
        if sun:
            sun.data.energy = 0.22
            sun.data.color = (0.62, 0.74, 1.0)
            sun.rotation_euler = (math.radians(64), 0, math.radians(150))
            sun.location = (-16, 16, 20)
        if fill:
            fill.data.energy = 60
            fill.data.color = (0.40, 0.52, 1.0)
        for ob in bpy.data.lights:
            if ob.name.startswith("Lamp"):
                ob.energy = 130
        emis = {"M_WinGlow": 1.5, "M_LampShade": 2.6, "M_Screen": 0.8}
    for name, v in emis.items():
        m = bpy.data.materials.get(name)
        if not m or not m.use_nodes:
            continue
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = v
    # 夜景提高曝光
    sc.view_settings.exposure = 0.45 if mode == "day" else 1.0


def setup_render(engine, res, samples):
    sc = bpy.context.scene
    if engine == "eevee":
        try:
            sc.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            sc.render.engine = "BLENDER_EEVEE"
        ee = sc.eevee
        for attr, val in (("taa_render_samples", samples), ("use_raytracing", True),
                          ("use_shadows", True), ("shadow_ray_count", 2),
                          ("use_gtao", True), ("use_bloom", True)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass
    else:
        sc.render.engine = "CYCLES"
        prefs = bpy.context.preferences.addons.get("cycles")
        if prefs:
            try:
                prefs.preferences.compute_device_type = "HIP"
                prefs.preferences.get_devices()
                for d in prefs.preferences.devices:
                    d.use = True
                sc.cycles.device = "GPU"
            except Exception:
                sc.cycles.device = "CPU"
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
    w, h = [int(v) for v in res.lower().split("x")]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast" if False else "None"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass


def render_one(cam, path):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[cam]
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[render] wrote", path)


def main():
    o = parse(argv())
    os.makedirs(os.path.join(HERE, "previews"), exist_ok=True)
    setup_render(o["engine"], o["res"], int(o["samples"]))
    apply_mode(o["mode"])
    for cam in o["cams"].split(","):
        cam = cam.strip()
        if not cam:
            continue
        tag = o["tag"] or o["mode"]
        path = os.path.join(HERE, "previews", f"{cam}_{tag}.png")
        render_one(cam, path)
    print("[render] DONE")


main()
