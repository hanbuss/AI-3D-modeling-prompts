"""材质库。所有名字以 M_ 开头；M_WinGlow / M_LampShade 在查看器里夜间发光。"""
import os
import json
import bpy
from .kit import make_material, principled

HERE = os.path.dirname(os.path.abspath(__file__))
TEXDIR = os.path.join(os.path.dirname(HERE), "textures")
_MANIFEST = None

# name: (base color, roughness, metallic, alpha, emit, emit_strength, noise)
SPEC = {
    # ---- 建筑主体 ----
    "M_WallWhite":   ((0.830, 0.812, 0.770, 1), 0.86, 0.0, 1.0, None, 0, (48, 2.0, 0.06)),
    "M_WallWarm":    ((0.800, 0.760, 0.690, 1), 0.86, 0.0, 1.0, None, 0, (40, 2.0, 0.05)),
    "M_WallInner":   ((0.760, 0.735, 0.690, 1), 0.90, 0.0, 1.0, None, 0, (36, 1.5, 0.03)),
    "M_Ceiling":     ((0.820, 0.800, 0.760, 1), 0.92, 0.0, 1.0, None, 0, None),
    "M_Stone":       ((0.520, 0.505, 0.480, 1), 0.78, 0.0, 1.0, None, 0, (60, 3.0, 0.10)),
    "M_StoneDark":   ((0.240, 0.238, 0.232, 1), 0.62, 0.0, 1.0, None, 0, (70, 2.0, 0.08)),
    "M_StoneLight":  ((0.700, 0.685, 0.650, 1), 0.72, 0.0, 1.0, None, 0, (55, 2.5, 0.09)),
    "M_Concrete":    ((0.470, 0.462, 0.450, 1), 0.85, 0.0, 1.0, None, 0, (30, 2.0, 0.07)),
    "M_Marble":      ((0.880, 0.870, 0.850, 1), 0.16, 0.0, 1.0, None, 0, (18, 3.0, 0.03)),
    "M_MarbleDark":  ((0.220, 0.215, 0.210, 1), 0.20, 0.0, 1.0, None, 0, (22, 3.0, 0.03)),
    # ---- 瓦 / 檐 ----
    "M_Tile":        ((0.093, 0.100, 0.108, 1), 0.58, 0.05, 1.0, None, 0, (90, 3.0, 0.16)),
    "M_TileEdge":    ((0.055, 0.058, 0.062, 1), 0.45, 0.10, 1.0, None, 0, (70, 2.0, 0.08)),
    # ---- 木作 ----
    "M_Wood":        ((0.300, 0.176, 0.098, 1), 0.52, 0.0, 1.0, None, 0, (26, 4.0, 0.10)),
    "M_WoodDark":    ((0.105, 0.072, 0.050, 1), 0.48, 0.0, 1.0, None, 0, (30, 3.0, 0.09)),
    "M_WoodLight":   ((0.560, 0.420, 0.270, 1), 0.55, 0.0, 1.0, None, 0, (24, 4.0, 0.10)),
    "M_WoodPale":    ((0.680, 0.575, 0.430, 1), 0.60, 0.0, 1.0, None, 0, (24, 3.0, 0.08)),
    "M_Bamboo":      ((0.330, 0.315, 0.170, 1), 0.58, 0.0, 1.0, None, 0, (20, 3.0, 0.08)),
    "M_Lacquer":     ((0.180, 0.052, 0.042, 1), 0.22, 0.0, 1.0, None, 0, (14, 2.0, 0.03)),
    # ---- 金属 / 玻璃 ----
    "M_MetalBlack":  ((0.055, 0.058, 0.062, 1), 0.34, 0.90, 1.0, None, 0, None),
    "M_MetalGrey":   ((0.400, 0.405, 0.415, 1), 0.30, 0.85, 1.0, None, 0, None),
    "M_Brass":       ((0.780, 0.610, 0.320, 1), 0.24, 1.00, 1.0, None, 0, None),
    "M_Chrome":      ((0.860, 0.870, 0.880, 1), 0.10, 1.00, 1.0, None, 0, None),
    "M_Glass":       ((0.520, 0.610, 0.640, 0.16), 0.04, 0.0, 0.16, None, 0, None),
    "M_GlassTint":   ((0.220, 0.290, 0.310, 0.24), 0.05, 0.0, 0.24, None, 0, None),
    "M_WinGlow":     ((0.430, 0.510, 0.530, 0.30), 0.05, 0.0, 0.30,
                      (1.0, 0.82, 0.55, 1), 0.22, None),
    "M_Mirror":      ((0.900, 0.910, 0.920, 1), 0.03, 1.0, 1.0, None, 0, None),
    # ---- 灯光 ----
    "M_LampShade":   ((0.960, 0.900, 0.780, 1), 0.55, 0.0, 1.0,
                      (1.0, 0.78, 0.48, 1), 0.9, None),
    "M_LampDark":    ((0.090, 0.085, 0.080, 1), 0.42, 0.35, 1.0, None, 0, None),
    # ---- 软装 ----
    "M_FabricCream": ((0.780, 0.740, 0.680, 1), 0.95, 0.0, 1.0, None, 0, (120, 2.0, 0.10)),
    "M_FabricGrey":  ((0.330, 0.335, 0.340, 1), 0.96, 0.0, 1.0, None, 0, (120, 2.0, 0.10)),
    "M_FabricRust":  ((0.400, 0.150, 0.095, 1), 0.94, 0.0, 1.0, None, 0, (110, 2.0, 0.10)),
    "M_FabricInk":   ((0.115, 0.130, 0.150, 1), 0.93, 0.0, 1.0, None, 0, (110, 2.0, 0.10)),
    "M_FabricOat":   ((0.680, 0.620, 0.530, 1), 0.95, 0.0, 1.0, None, 0, (110, 2.0, 0.10)),
    "M_Linen":       ((0.880, 0.860, 0.820, 1), 0.94, 0.0, 1.0, None, 0, (150, 2.0, 0.08)),
    "M_Leather":     ((0.235, 0.140, 0.090, 1), 0.42, 0.0, 1.0, None, 0, (60, 3.0, 0.06)),
    "M_Rug":         ((0.520, 0.470, 0.410, 1), 0.99, 0.0, 1.0, None, 0, (200, 2.0, 0.12)),
    "M_RugRed":      ((0.330, 0.115, 0.100, 1), 0.98, 0.0, 1.0, None, 0, (200, 2.0, 0.12)),
    "M_Silk":        ((0.870, 0.820, 0.740, 0.75), 0.35, 0.0, 0.75, None, 0, None),
    # ---- 器物 ----
    "M_Porcelain":   ((0.930, 0.925, 0.905, 1), 0.14, 0.0, 1.0, None, 0, None),
    "M_Celadon":     ((0.560, 0.700, 0.640, 1), 0.12, 0.0, 1.0, None, 0, None),
    "M_Ceramic":     ((0.300, 0.265, 0.245, 1), 0.55, 0.0, 1.0, None, 0, (40, 2.0, 0.05)),
    "M_BookPage":    ((0.880, 0.850, 0.790, 1), 0.88, 0.0, 1.0, None, 0, None),
    "M_BookSpine":   ((0.290, 0.230, 0.200, 1), 0.80, 0.0, 1.0, None, 0, None),
    "M_BookSpineB":  ((0.200, 0.290, 0.260, 1), 0.80, 0.0, 1.0, None, 0, None),
    "M_Canvas":      ((0.860, 0.850, 0.820, 1), 0.92, 0.0, 1.0, None, 0, None),
    "M_Screen":      ((0.030, 0.035, 0.040, 1), 0.12, 0.0, 1.0, (0.55, 0.72, 0.85, 1), 0.10, None),
    # ---- 水 / 植物 / 地景 ----
    "M_Water":       ((0.014, 0.040, 0.048, 0.90), 0.12, 0.0, 0.90, None, 0, None),
    "M_WaterDark":   ((0.012, 0.028, 0.034, 0.92), 0.05, 0.0, 0.92, None, 0, None),
    "M_Grass":       ((0.215, 0.275, 0.155, 1), 0.95, 0.0, 1.0, None, 0, (240, 3.0, 0.28)),
    "M_Moss":        ((0.180, 0.240, 0.130, 1), 0.97, 0.0, 1.0, None, 0, (300, 3.0, 0.3)),
    "M_Gravel":      ((0.560, 0.540, 0.500, 1), 0.92, 0.0, 1.0, None, 0, (260, 4.0, 0.35)),
    "M_Bark":        ((0.180, 0.150, 0.120, 1), 0.90, 0.0, 1.0, None, 0, (60, 4.0, 0.22)),
    "M_LeafGreen":   ((0.150, 0.235, 0.105, 1), 0.72, 0.0, 1.0, None, 0, (90, 3.0, 0.2)),
    "M_LeafDeep":    ((0.085, 0.150, 0.075, 1), 0.70, 0.0, 1.0, None, 0, (90, 3.0, 0.2)),
    "M_LeafPine":    ((0.100, 0.165, 0.095, 1), 0.75, 0.0, 1.0, None, 0, (110, 3.0, 0.22)),
    "M_LeafMaple":   ((0.420, 0.130, 0.075, 1), 0.70, 0.0, 1.0, None, 0, (110, 3.0, 0.2)),
    "M_LeafOlive":   ((0.290, 0.330, 0.180, 1), 0.75, 0.0, 1.0, None, 0, (110, 3.0, 0.2)),
    "M_LeafPale":    ((0.400, 0.470, 0.250, 1), 0.75, 0.0, 1.0, None, 0, (110, 3.0, 0.2)),
    "M_Lotus":       ((0.300, 0.420, 0.240, 1), 0.65, 0.0, 1.0, None, 0, (140, 2.0, 0.2)),
    "M_Soil":        ((0.135, 0.110, 0.090, 1), 0.98, 0.0, 1.0, None, 0, (200, 3.0, 0.25)),
    "M_GroundSoil":  ((0.190, 0.165, 0.135, 1), 0.97, 0.0, 1.0, None, 0, (180, 2.0, 0.18)),
}


# 材质 -> 贴图套（None 表示保持纯色）
TEXMAP = {
    "M_WallWhite": "plaster", "M_WallWarm": "plaster", "M_WallInner": "plaster",
    "M_Ceiling": "plaster",
    "M_Stone": "stone", "M_StoneDark": "stone", "M_StoneLight": "stone_light",
    "M_Marble": "marble", "M_MarbleDark": "marble",
    "M_WoodPale": "wood_oak", "M_WoodLight": "wood_oak",
    "M_Wood": "wood_walnut", "M_WoodDark": "wood_charred",
    "M_Bamboo": "wood_oak",
    "M_Tile": "tile", "M_TileEdge": "tile",
    "M_FabricCream": "fabric", "M_FabricOat": "fabric", "M_FabricGrey": "fabric",
    "M_FabricInk": "fabric", "M_Linen": "fabric", "M_FabricRust": "fabric",
    "M_Rug": "rug", "M_RugRed": "rug",
    "M_Grass": "grass", "M_Gravel": "gravel",
}


def manifest():
    global _MANIFEST
    if _MANIFEST is None:
        mp = os.path.join(TEXDIR, "manifest.json")
        try:
            _MANIFEST = json.load(open(mp, encoding="utf-8")).get("tiles", {})
        except Exception:
            _MANIFEST = {}
    return _MANIFEST


def wire_texture(mat, tile, uv_scale=2.0):
    """把 albedo + normal 接到材质上；UV 已按 uv_scale 米归一，Mapping 再乘比例。"""
    info = manifest().get(tile)
    if not info:
        return False
    apath = os.path.join(TEXDIR, os.path.basename(info["albedo"]))
    npath = os.path.join(TEXDIR, os.path.basename(info["normal"]))
    if not (os.path.exists(apath) and os.path.exists(npath)):
        return False
    nt = mat.node_tree
    bsdf = principled(mat)
    if bsdf is None:
        return False
    img_a = bpy.data.images.load(apath, check_existing=True)
    img_n = bpy.data.images.load(npath, check_existing=True)
    for im in (img_a, img_n):
        try:
            im.colorspace_settings.name = "sRGB" if im is img_a else "Non-Color"
        except Exception:
            pass
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale / info.get("tile_m", 2.0),) * 3
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = img_a
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img_n
    nt.links.new(mp.outputs["Vector"], ta.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tn.inputs["Vector"])
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.26
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return True


def build_all():
    out = {}
    for name, spec in SPEC.items():
        base, rough, metal, alpha, emit, es, noise = spec
        out[name] = make_material(name, base=base, rough=rough, metal=metal,
                                  alpha=alpha, emit=emit, emit_strength=es,
                                  noise=noise)
    # 若有贴图就接上（无贴图时保持纯色 + 程序化 bump）
    wired = 0
    for mname, tile in TEXMAP.items():
        m = bpy.data.materials.get(mname)
        if m and wire_texture(m, tile):
            wired += 1
    print(f"[mats] textured materials: {wired}/{len(TEXMAP)}")
    return out
