# -*- coding: utf-8 -*-
"""成品资产（PolyHaven CC0 模型）加载与实例化 —— assets2。

和旧 lib/assets.py 的差别（都是踩过的坑）
  * 尺寸：prep_assets.py 现在先把对象变换 apply 掉再归一化，src_height / src_radius 是
    变换后的**真实米制**。旧链路按局部坐标量、不管对象缩放，0.30 m 的花丛出来 4 cm。
  * 落地：用 matrix_world @ bound_box **现算**（scene 更新之后再读），不信任未 apply 的
    对象包围盒，底面精确贴 z，sink 只往下埋 sink 那么多。
  * 朝向：默认旋转走 crc32(tag)，跨进程稳定。旧版用 hash(tag)，Python 的 str hash 每进程
    随机加盐，同一棵树每次 build 朝向都不同。

约定：assets/<name>.blend 里只有一个 mesh，原点在 base 中心（X/Y 居中、最低点 z=0）。
"""
import os
import math
import json
import zlib

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")
CATALOG = os.path.join(ASSETS, "catalog.json")

_cache = {}          # name -> (object, src_height, src_radius)


# ---------------------------------------------------------------- 查询
def available():
    if not os.path.isdir(ASSETS):
        return []
    return sorted(n[:-6] for n in os.listdir(ASSETS)
                  if n.endswith(".blend") and not n.startswith("_"))


def _measure(ob):
    """兜底：资产没写自定义属性时，直接从几何量（此时对象变换已 apply，读数即米制）。"""
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    h = (max(zs) - min(zs)) if zs else 1.0
    r = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.5 if xs else 1.0
    return h or 1.0, r or 1.0


def load(name):
    """缓存加载 (object, src_height, src_radius)。同一个名字只 append 一次。"""
    if name in _cache:
        return _cache[name]
    path = os.path.join(ASSETS, "%s.blend" % name)
    if not os.path.exists(path):
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None and o.type == "MESH"]
    if not objs:
        return None
    ob = max(objs, key=lambda o: len(o.data.vertices))
    for extra in objs:                          # 兜底：真有多个就并成一个
        if extra is not ob:
            bpy.data.objects.remove(extra, do_unlink=True)
    sh = float(ob.get("src_height") or 0.0)
    sr = float(ob.get("src_radius") or 0.0)
    if sh <= 0.0 or sr <= 0.0:
        h2, r2 = _measure(ob)
        sh = sh or h2
        sr = sr or r2
    _cache[name] = (ob, sh, sr)
    return _cache[name]


def catalog():
    """{name: (height, radius, tris)}。优先读 prep 写的 catalog.json（不用 append 15 个 blend）。"""
    out = {}
    if os.path.exists(CATALOG):
        try:
            raw = json.load(open(CATALOG, encoding="utf-8"))
            for k, v in raw.items():
                if os.path.exists(os.path.join(ASSETS, "%s.blend" % k)):
                    out[k] = (float(v["height"]), float(v["radius"]), int(v["tris"]))
            return out
        except Exception:
            out = {}
    for name in available():                    # 没有 catalog.json 就现量
        got = load(name)
        if got:
            ob, h, r = got
            tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
            out[name] = (h, r, tris)
    return out


# ---------------------------------------------------------------- 实例化
def _default_rot(tag):
    """tag → 0..2π，跨进程稳定（不用 hash()，那个每进程不同）。"""
    return (zlib.crc32(tag.encode("utf-8")) % 360) * math.pi / 180.0


def instance(ctx, layer, name, tag, x, y, z=0.0, height=None, rot=None,
             max_w=None, sink=0.0):
    """把 assets/<name>.blend 放一份到 (x, y, z)，底面贴 z（再按 sink 往下埋）。

    height : 目标高度（米）。None = 用资产自然高度。
    max_w  : 目标最大宽度（米）。超过就再缩，防止宽冠树压到邻居。
    rot    : 绕 Z 弧度。None = 由 tag 定（确定、可复现）。
    """
    got = load(name)
    if not got:
        print("[assets2] MISSING %s.blend —— 跳过 %s" % (name, tag))
        return None
    src, sh, sr = got
    k = (height / sh) if height else 1.0
    if max_w and (2.0 * sr) * k > max_w:
        k = max_w / max(2.0 * sr, 1e-6)         # 太宽的按宽度收
    ob = src.copy()                             # 共享 mesh data：glTF 只写一份几何
    ob.data = src.data
    ob.name = "ASSET_%s_%s" % (name, tag)
    coll = ctx.coll(layer)
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    parent = getattr(ctx, "empties", {}).get(layer)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    ob.location = (x, y, z)
    ob.rotation_euler = (0.0, 0.0, _default_rot(tag) if rot is None else rot)
    ob.scale = (k, k, k)
    # 缩放/摆位之后重新算世界包围盒，把底面顶到 z（不信任 src 的包围盒）
    bpy.context.view_layer.update()
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    dz = (z - sink) - min(v.z for v in bb)
    ob.location = (ob.location.x, ob.location.y, ob.location.z + dz)
    return ob


def footprint(ob):
    """实例在世界上真正占的 (宽, 深, 高)，用于摆放校验。"""
    bpy.context.view_layer.update()
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
