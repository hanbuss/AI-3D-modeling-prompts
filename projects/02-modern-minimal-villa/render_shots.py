# -*- coding: utf-8 -*-
"""渲染预览（无头）。

    blender -b mvilla.blend --python render_shots.py -- cams=CAM_Hero res=1600x900 \
        samples=48 mode=day tag=day

mode=day / night / dusk
"""
import bpy
import sys
import os
import math

HERE = os.path.dirname(os.path.abspath(__file__))


def argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def parse(args):
    o = dict(cams="CAM_Hero", res="1600x900", samples="48", mode="day",
             engine="eevee", tag="")
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            o[k] = v
    return o


def engine_enum():
    props = bpy.types.RenderSettings.bl_rna.properties["engine"]
    return [e.identifier for e in props.enum_items]


# ------------------------------------------------------------------ 天光
def set_world(mode):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("W")
    sc.world = w
    if not w.use_nodes:
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
        stops = [(0.40, (0.58, 0.56, 0.52, 1)), (0.50, (0.90, 0.92, 0.92, 1)),
                 (0.57, (0.68, 0.80, 0.96, 1)), (1.00, (0.24, 0.46, 0.88, 1))]
        strength = 1.30
    elif mode == "dusk":
        stops = [(0.40, (0.24, 0.16, 0.13, 1)), (0.50, (0.72, 0.42, 0.26, 1)),
                 (0.56, (0.42, 0.40, 0.52, 1)), (1.00, (0.09, 0.13, 0.30, 1))]
        strength = 1.00
    else:
        stops = [(0.40, (0.016, 0.020, 0.030, 1)), (0.50, (0.062, 0.082, 0.135, 1)),
                 (0.60, (0.026, 0.042, 0.092, 1)), (1.00, (0.008, 0.011, 0.030, 1))]
        strength = 1.00
    bg.inputs["Strength"].default_value = strength
    r.elements[0].position = stops[0][0]
    r.elements[0].color = stops[0][1]
    r.elements[1].position = stops[-1][0]
    r.elements[1].color = stops[-1][1]
    for pos, col in stops[1:-1]:
        e = r.elements.new(pos)
        e.color = col


# ------------------------------------------------------------------ 太阳 / 补光
def apply_mode(mode):
    sc = bpy.context.scene
    set_world(mode)
    sun = bpy.data.objects.get("Sun")
    fill = bpy.data.objects.get("FillSky")

    if mode == "day":
        if sun:
            sun.data.energy = 4.4
            sun.data.color = (1.0, 0.962, 0.906)
            sun.data.angle = math.radians(1.6)
            sun.rotation_euler = (math.radians(44), 0, math.radians(-54))
            sun.location = (16, -18, 24)
        if fill:
            fill.data.energy = 300
            fill.data.color = (0.82, 0.89, 1.0)
        sc.view_settings.exposure = 0.30
    elif mode == "dusk":
        if sun:
            sun.data.energy = 1.5
            sun.data.color = (1.0, 0.72, 0.46)
            sun.data.angle = math.radians(3.0)
            sun.rotation_euler = (math.radians(83), 0, math.radians(-104))
            sun.location = (20, -30, 4)
        if fill:
            fill.data.energy = 60
            fill.data.color = (0.50, 0.58, 0.90)
        sc.view_settings.exposure = 0.75
    else:
        if sun:
            sun.data.energy = 0.30
            sun.data.color = (0.66, 0.76, 1.0)
            sun.data.angle = math.radians(2.0)
            sun.rotation_euler = (math.radians(62), 0, math.radians(146))
            sun.location = (-18, 18, 22)
        if fill:
            fill.data.energy = 40
            fill.data.color = (0.36, 0.48, 1.0)
        sc.view_settings.exposure = 1.05

    # 室内灯 / 户外灯的实际光源（bpy.data.lights 是 Light datablock，不是 object，
    # 所以直接改 la.energy，没有 .data 这一层）
    for la in bpy.data.lights:
        n = la.name
        if n.startswith("Lamp"):
            la.energy = 45 if mode == "day" else (95 if mode == "dusk" else 165)
        elif n.startswith("Garden"):
            la.energy = 0 if mode == "day" else (60 if mode == "dusk" else 110)
        elif n.startswith("Water"):
            la.energy = 0 if mode == "day" else (35 if mode == "dusk" else 60)

    # 自发光强度
    if mode == "day":
        emis = {"M_WinGlow": 0.10, "M_LampShade": 0.35, "M_StepLight": 0.10,
                "M_Uplight": 0.10, "M_WaterfallLED": 0.10, "M_Flame": 0.30,
                "M_EmberGlow": 0.30}
    elif mode == "dusk":
        emis = {"M_WinGlow": 1.10, "M_LampShade": 2.20, "M_StepLight": 1.60,
                "M_Uplight": 2.40, "M_WaterfallLED": 1.40, "M_Flame": 3.00,
                "M_EmberGlow": 2.00}
    else:
        emis = {"M_WinGlow": 1.90, "M_LampShade": 3.40, "M_StepLight": 2.60,
                "M_Uplight": 3.60, "M_WaterfallLED": 2.20, "M_Flame": 4.20,
                "M_EmberGlow": 2.60}
    for name, v in emis.items():
        m = bpy.data.materials.get(name)
        if not m or not m.use_nodes:
            continue
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = v


# ------------------------------------------------------------------ 渲染设置
def setup_render(engine, res, samples):
    sc = bpy.context.scene
    avail = engine_enum()
    if engine == "cycles":
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
    else:
        eng = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in avail else "BLENDER_EEVEE"
        sc.render.engine = eng
        ee = sc.eevee
        for attr, val in (("taa_render_samples", samples), ("use_raytracing", True),
                          ("use_shadows", True), ("use_gtao", True),
                          ("use_bloom", True), ("shadow_ray_count", 2),
                          ("use_volumetric_shadows", True)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass

    w, h = [int(v) for v in res.lower().split("x")]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 20
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        try:
            sc.view_settings.view_transform = "Filmic"
        except Exception:
            pass


def render_one(cam, path):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[cam]
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[render] wrote", path, flush=True)


def main():
    o = parse(argv())
    out = os.path.join(HERE, "previews")
    os.makedirs(out, exist_ok=True)
    setup_render(o["engine"], o["res"], int(o["samples"]))
    apply_mode(o["mode"])
    for cam in o["cams"].split(","):
        cam = cam.strip()
        if not cam:
            continue
        tag = o["tag"] or o["mode"]
        render_one(cam, os.path.join(out, f"{cam}_{tag}.png"))
    print("[render] DONE")


if __name__ == "__main__":
    main()
