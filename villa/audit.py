# -*- coding: utf-8 -*-
"""布局审查：穿墙 / 浮空 / 沉地 / 越界 / 互相穿插。

用法： blender -b villa.blend --python audit.py
"""
import bpy
import os
import sys
import json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))

STRUCT_KW = ("Walls", "Slab", "Ceiling", "Belts", "Skirt", "Stair", "Balcony",
             "Terrace", "Deck", "Pond", "Bridge", "Pavilion", "Path", "PondEdge",
             "Bamboo", "Pine", "Trees", "Shrubs", "Reeds", "Lotus", "Roof", "EAVE",
             "Eave", "Canopy", "Main", "FloorFinish", "Ground", "Plinth",
             "PerimeterWall", "Paving", "Lantern", "Windows", "Plumbing")
# 吸顶 / 挂墙 / 摆在家具上的，不参与"浮空"判定
CEIL_MOUNT = ("Pendant", "_L_", "Lamp", "Ceiling", "Reeds")
ON_SURFACE = ("Bowl", "Vase", "Tray", "Books", "Ware", "Dish", "Towel", "Clock",
              "Hook", "Slippers", "Mat", "Platform", "Cushion", "Incense", "Cup", "Parasol", "ASSET_", "ASSET_",
              "_Tile", "Med_Table", "Med_Screen", "Tea", "D_", "ROOF_Corner",
              "Pergola", "Sideboard")
WALL_MOUNT = ("Art", "Curtain", "Upper", "Mirror", "Sconce", "TV")
ON_TOP = ("Entry_Vase", "GARDEN_Tea", "Med_Incense", "Med_Cushion", "Med_Table",
          "Med_Screen", "Med_Vase")
# 允许贴墙的（柜类），穿墙阈值放宽
FLUSH_KW = ("Wardrobe", "Shelf", "TV", "Cabinet", "Console", "Basin", "Sink",
            "Counter", "Run", "Sideboard", "Desk", "Toilet", "Tub", "Shower",
            "Washer", "Art", "Curtain", "Skirt", "Sconce", "Island")

# 各层楼面标高
FLOORS = [0.02, 0.14, 0.17, 0.20, 3.43, 3.46, 6.63, 6.70]


def layer_of(ob):
    p = ob
    while p:
        if p.name in ("SITE", "GARDEN", "F1", "F2", "F3", "ROOF"):
            return p.name
        p = p.parent
    return "?"


def wbbox(ob):
    mw = ob.matrix_world
    pts = [mw @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def overlap(a, b):
    """返回 (x 重叠, y 重叠, z 重叠)，负值表示不相交"""
    return (min(a[1], b[1]) - max(a[0], b[0]),
            min(a[3], b[3]) - max(a[2], b[2]),
            min(a[5], b[5]) - max(a[4], b[4]))


def is_struct(n):
    return any(k in n for k in STRUCT_KW)


def main():
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    data = {}
    for o in objs:
        try:
            data[o.name] = (layer_of(o), wbbox(o), is_struct(o.name))
        except Exception:
            pass

    walls = []
    wj = os.path.join(HERE, "walls.json")
    if os.path.exists(wj):
        for (ax, a0, a1, b0, b1, c0, c1) in json.load(open(wj)):
            if ax == "X":
                walls.append((a0, a1, b0, b1, c0, c1))
            else:
                walls.append((b0, b1, a0, a1, c0, c1))

    props = {n: d for n, d in data.items() if not d[2]}
    structs = {n: d for n, d in data.items() if d[2]}

    problems = {"float": [], "sink": [], "wall": [], "out": [], "clash": []}

    # ---- 浮空 / 沉地 ----
    for n, (lay, bb, _) in props.items():
        if any(k in n for k in CEIL_MOUNT + WALL_MOUNT + ON_SURFACE):
            continue
        zmin = bb[4]
        near = min(FLOORS, key=lambda f: abs(f - zmin))
        d = zmin - near
        if d > 0.06:
            problems["float"].append((n, lay, round(zmin, 3), round(near, 2)))
        elif d < -0.06:
            problems["sink"].append((n, lay, round(zmin, 3), round(near, 2)))

    # ---- 穿墙（逐墙段）----
    for n, (lay, bb, _) in props.items():
        if any(k in n for k in WALL_MOUNT + ON_SURFACE):
            continue
        thr = 0.30 if any(k in n for k in FLUSH_KW) else 0.05
        worst = 0.0
        for wb in walls:
            ox, oy, oz = overlap(bb, wb)
            if ox <= 0 or oy <= 0 or oz <= 0:
                continue
            depth = min(ox, oy)
            if depth > worst:
                worst = depth
        if worst > thr:
            problems["wall"].append((n, lay, round(worst, 3)))

    # ---- 越界（楼内家具跑到建筑外） ----
    for n, (lay, bb, _) in props.items():
        if lay not in ("F1", "F2", "F3"):
            continue
        if any(k in n for k in ("Bal", "Ter", "Planter", "Pot")):
            continue
        out = 0.0
        out = max(out, -8.02 - bb[0], bb[1] - 8.02, -6.02 - bb[2], bb[3] - 6.02)
        if out > 0.05:
            problems["out"].append((n, lay, round(out, 3)))

    # ---- 互相穿插 ----
    names = list(props.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if data[a][0] != data[b][0]:
                continue
            if any(k in (a + b) for k in ON_SURFACE + WALL_MOUNT):
                continue
            ox, oy, oz = overlap(data[a][1], data[b][1])
            if ox > 0.03 and oy > 0.03 and oz > 0.03:
                vol = ox * oy * oz
                if vol > 0.03:
                    problems["clash"].append((a, b, round(vol, 3)))

    # ---- 输出 ----
    tot = 0
    for k, label in (("float", "浮空（离地 >6cm）"), ("sink", "沉入地面 >6cm"),
                     ("wall", "穿墙 >5cm"), ("out", "越出建筑外轮廓"),
                     ("clash", "家具互相穿插")):
        rows = problems[k]
        tot += len(rows)
        print(f"\n=== {label} · {len(rows)} 处 ===")
        for r in rows[:80]:
            print("   ", r)
        if len(rows) > 80:
            print(f"    ... 还有 {len(rows) - 80} 条")
    print(f"\n[TOTAL] {tot} 处问题，对象总数 {len(props)} 家具 / {len(structs)} 构件")
    with open(os.path.join(HERE, "audit_report.json"), "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=1)


main()
