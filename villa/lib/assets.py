# -*- coding: utf-8 -*-
"""成品植被（PolyHaven CC0 模型）加载与实例化。

prep_assets.py 已经把模型减面、贴图压到 1k、归一化（落地居中），存成 assets/*.blend。
这里用 append 取一次，其余副本共享同一份 mesh —— glTF 导出时只写一份，实例只多节点。
"""
import os
import bpy
import math
from mathutils import Vector

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")

_cache = {}      # name -> (object, src_height, src_radius)


def load(name):
    if name in _cache:
        return _cache[name]
    path = os.path.join(ASSETS, f"{name}.blend")
    if not os.path.exists(path):
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = [n for n in src.objects]
        dst.objects = names
    objs = [o for o in dst.objects if o is not None]
    if not objs:
        return None
    ob = objs[0]
    h = float(ob.get("src_height", 1.0)) or 1.0
    r = float(ob.get("src_radius", 1.0)) or 1.0
    _cache[name] = (ob, h, r)
    return _cache[name]


def instance(ctx, layer, name, tag, x, y, z=0.0, height=6.0, rot=None, sink=0.05,
             max_w=None):
    """把 assets/<name>.blend 里的树放一份到 (x,y,z)，按目标高度缩放。"""
    got = load(name)
    if not got:
        print(f"[assets] MISSING {name}.blend —— 跳过 {tag}")
        return None
    src, sh, sr = got
    k = height / max(sh, 1e-6)
    if max_w and sr * 2.0 * k > max_w:
        k = max_w / max(sr * 2.0, 1e-6)   # 太宽的成品植物按宽度收     # 太宽的成品植物按宽度收
    ob = src.copy()                     # 共享 mesh 数据
    ob.data = src.data
    ob.name = f"ASSET_{name}_{tag}"
    ob.animation_data_clear() if ob.animation_data else None
    ctx.coll(layer).objects.link(ob)
    ob.parent = ctx.empties[layer]
    ob.scale = (k, k, k)
    # 按缩放后的真实包围盒落地，避免不同模型原点不同导致陷进地里
    bpy.context.view_layer.update()
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    dz = min(v.z for v in bb)
    ob.location = (x, y, z - dz - sink)
    ob.rotation_euler = (0, 0, rot if rot is not None else (hash(tag) % 360) * math.pi / 180)
    return ob


def available():
    if not os.path.isdir(ASSETS):
        return []
    return sorted(n[:-6] for n in os.listdir(ASSETS) if n.endswith(".blend"))
