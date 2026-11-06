# -*- coding: utf-8 -*-
"""布局审查：跑在 mvilla.blend 上，检查越界、穿墙、悬空、丢材质、退化面。

    blender -b mvilla.blend --python audit.py

退出码 0 = 全过；1 = 有 ERROR。
"""
import bpy
import sys
import os
import math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))

# 允许范围（米），来自 LAYOUT.md
BOUNDS = {
    "SITE":     (-80, 80, -80, 80, -1.0, 13.0),
    "ARCH_1F":  (-7.8, 7.8, -2.6, 9.4, -0.12, 4.70),
    "ARCH_2F":  (-7.8, 7.8, -2.6, 9.4, 3.30, 8.00),
    "ARCH_3F":  (-7.8, 7.8, -2.6, 9.4, 6.60, 10.05),
    "ROOF":     (-7.9, 7.9, -2.7, 9.7, -0.10, 10.90),
    "COURT":    (-11.6, 11.6, -19.8, -1.35, -0.15, 6.60),
    "INT_1F":   (-7.35, 7.35, -1.65, 9.15, 0.10, 3.35),
    "INT_2F":   (-7.35, 7.35, -1.65, 9.15, 3.55, 6.65),
    "INT_3F":   (-7.35, 7.35, -1.65, 9.15, 6.85, 9.95),
}
# 室内不能出现在房子以外的范围（穿墙会立刻违反）
HOUSE_XY = (-7.35, 7.35, -1.65, 9.15)
TOL = 0.02

errors = []
warns = []
stats = {}


def bbox(ob):
    xs, ys, zs = [], [], []
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        xs.append(w.x); ys.append(w.y); zs.append(w.z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def layer_of(ob):
    for c in ob.users_collection:
        return c.name
    return "?"


def main():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    print(f"[audit] meshes={len(meshes)}")

    for ob in meshes:
        layer = layer_of(ob)
        b = BOUNDS.get(layer)
        x0, x1, y0, y1, z0, z1 = bbox(ob)

        if b:
            gx0, gx1, gy0, gy1, gz0, gz1 = b
            if x0 < gx0 - TOL or x1 > gx1 + TOL:
                errors.append(f"{layer}/{ob.name}: X [{x0:.2f},{x1:.2f}] 超出 [{gx0},{gx1}]")
            if y0 < gy0 - TOL or y1 > gy1 + TOL:
                errors.append(f"{layer}/{ob.name}: Y [{y0:.2f},{y1:.2f}] 超出 [{gy0},{gy1}]")
            if z0 < gz0 - TOL or z1 > gz1 + TOL:
                errors.append(f"{layer}/{ob.name}: Z [{z0:.2f},{z1:.2f}] 超出 [{gz0},{gz1}]")
        else:
            warns.append(f"{ob.name}: 未知层 {layer}")

        # 室内不能超出房子
        if layer.startswith("INT_"):
            if x0 < HOUSE_XY[0] - TOL or x1 > HOUSE_XY[1] + TOL or \
               y0 < HOUSE_XY[2] - TOL or y1 > HOUSE_XY[3] + TOL:
                errors.append(f"{layer}/{ob.name}: 室内对象穿出房子 "
                              f"X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}]")

        # 材质
        if len(ob.data.materials) == 0:
            errors.append(f"{layer}/{ob.name}: 没有材质槽")
        elif any(m is None for m in ob.data.materials):
            errors.append(f"{layer}/{ob.name}: 空材质槽")
        else:
            used = {p.material_index for p in ob.data.polygons}
            assigned = {i for i in used if i < len(ob.data.materials)}
            if not used:
                warns.append(f"{layer}/{ob.name}: 没有面")
            # 面数统计
        stats[layer] = stats.get(layer, 0) + len(ob.data.polygons)

        # 退化面
        deg = 0
        for p in ob.data.polygons:
            if p.area < 1e-9:
                deg += 1
        if deg > max(3, len(ob.data.polygons) * 0.02):
            warns.append(f"{layer}/{ob.name}: {deg} 个退化面 (共{len(ob.data.polygons)})")

        # 悬空：COURT 里 z0 明显高于地面的独立对象（除非是灯/水幕/亭顶）
        if layer == "COURT":
            nm = ob.name.lower()
            floating_ok = any(k in nm for k in ("light", "lamp", "water", "pergola",
                                                "gate", "wall", "tree", "pine",
                                                "maple", "car", "street", "shrub",
                                                "bench", "sofa", "table"))
            if z0 > 0.35 and not floating_ok:
                warns.append(f"{layer}/{ob.name}: 底边 z={z0:.2f} 疑似悬空")

    # ---- 汇总
    print("\n[audit] 各层面数：")
    for k in sorted(stats):
        print(f"   {k:10s} {stats[k]:>8d}")

    if warns:
        print(f"\n[audit] WARN {len(warns)}")
        for w in warns[:40]:
            print("   -", w)
    if errors:
        print(f"\n[audit] ERROR {len(errors)}")
        for e in errors[:60]:
            print("   !", e)
    else:
        print("\n[audit] 无 ERROR")
    print(f"\n[audit] {'FAIL' if errors else 'PASS'}")
    sys.exit(1 if errors else 0)


main()
