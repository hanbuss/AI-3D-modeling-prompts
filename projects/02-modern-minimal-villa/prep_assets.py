# -*- coding: utf-8 -*-
"""素材预处理：PolyHaven CC0 .blend → 项目素材库 assets/<name>.blend。

上一版栽在哪：源对象带对象缩放（花丛 0.148），却按**局部**坐标量尺寸，于是
"要 0.30 m 的植物"出来 4 cm。这一版每个资产都先 apply 全部变换再量，对象缩放
已经烘进顶点，之后任何读数都是世界米制。

每个资产的流程
  1. 从 assets/_raw/<name>.blend append 指定对象（PolyHaven 一个 blend 里塞了
     4~11 个变体 × LOD0..LODn，全部摊在 +X 轴上；这里只取一个变体的一套）
  2. transform_apply(location/rotation/scale=True) —— 对象缩放烘进顶点
  3. 多部件 join 成一个 mesh
  4. 归一化：X/Y 居中、最低点 z=0（base 在原点），保留变换后的真实米制高度
  5. 减面到预算（树 8k–25k / 灌木 2k–8k / 草花 1k–5k / 户外家具 2k–12k），保 UV、保材质
  6. 贴图 ≤1024、按用途重编码（带 alpha 的留 PNG，其余 JPEG）并 pack 进 blend
  7. 对象写自定义属性 src_height / src_radius（归一化后的真实米数）
  8. 存 assets/<name>.blend（compress=True），顺手清掉旧的一批坏资产
  9. 汇总表 + assets/catalog.json（lib/assets2.catalog() 读它，省得每次 append 一堆 blend）

源件放 assets/_raw/（源 .blend + PolyHaven 的 textures/），默认**保留**；要清加 --prune。

用法
    blender -b --factory-startup --python prep_assets.py
    blender -b --factory-startup --python prep_assets.py -- fir_tree_01 shrub_02
    blender -b --factory-startup --python prep_assets.py -- --fetch    # 只下源件（blend + 贴图）
    blender -b --factory-startup --python prep_assets.py -- --prune    # 跑完清 _raw（默认保留）
"""
import bpy
import bmesh
import os
import re
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
RAW = os.path.join(ASSETS, "_raw")            # 源 .blend（不进最终库）
TEXSRC = os.path.join(RAW, "textures")        # 源贴图（PolyHaven blend 用相对路径 //textures）
ENCDIR = os.path.join(RAW, "_enc")            # 重编码后的贴图（pack 完即删）

MAX_TEX = 1024
# 重编码质量：法线最高，albedo 次之，粗糙/金属等灰度图最低（肉眼看不出）
Q_NOR, Q_DIFF, Q_MISC = 92, 88, 82

# ---------------------------------------------------------------- 资产清单
# name, kind, 选取正则（按对象名匹配，只取一个变体的一套）, 可选覆盖
JOBS = [
    # ---- 树（PolyHaven 树的 LOD0 是百万面级，直接取最粗的现成 LOD 再减）
    ("fir_tree_01",     "tree",  r"^fir_tree_01_a_LOD2$", None),
    # 已弃用：jacaranda_tree。实测它就 1.85M 面 / 1.81M 顶点的卡片汤（27k 个互不相连的岛、
    # 边界边占 44.6%），collapse 到 87k 就塌不动；再硬压只能整岛删除，而它的枝干岛自己
    # 就有 52.8k 面 —— 结果是一棵没有叶子的光杆树。PolyHaven 没给这个资产出低模 LOD，
    # 庭园的树换 pine_tree_01 / tree_small_02 顶上。
    ("island_tree_01",  "tree",  r"^island_tree_01_LOD1$", None),
    ("island_tree_02",  "tree",  r"^island_tree_02_LOD1$", None),
    # 追加：fir / island_01 / island_02 是野生疏叶树，庭园要密叶品种
    ("pine_tree_01",    "tree",  r"^pine_tree_01_a_LOD1$", None),
    ("tree_small_02",   "tree",  r"^tree_small_02_LOD1$", None),
    # ---- 灌木（同一 blend 里 4~11 个变体，取 x≈0 的那个，结果可复现）
    ("shrub_01",        "shrub", r"^shrub_01_c_LOD0$", None),
    ("shrub_02",        "shrub", r"^shrub_02_b_LOD0$", None),
    ("shrub_03",        "shrub", r"^shrub_03_a_LOD0$", None),
    ("shrub_04",        "shrub", r"^shrub_04_a_LOD0$", None),
    # ---- 草 / 花 / 蕨（_geo / _geometry_nodes / _geonodes_ 是预览用的副本，排除）
    ("grass_medium_02", "grass", r"^grass_medium_02_d$", None),
    ("periwinkle_plant", "grass", r"^periwinkle_plant_03_LOD0$", None),
    ("celandine_01",    "grass", r"^celandine_01_c_LOD0$", None),
    ("fern_02",         "grass", r"^fern_02_b$", None),
    # ---- 户外家具（屋面露台）
    ("ArmChair_01",     "prop",  r"^ArmChair_01$", None),
    ("sofa_02",         "prop",  r"^sofa_02_(Seat|Base)$", None),
    ("Ottoman_01",      "prop",  r"^Ottoman_01$", None),
]
BUDGET = {"tree": (8000, 25000), "shrub": (2000, 8000),
          "grass": (1000, 5000), "prop": (2000, 12000)}

# 旧的一批坏资产：PolyHaven 平摊标本扫描（花丛 9×9×2.5 且自带 0.148 对象缩放），
# 立栽会塌成薄片 / 只有 4 cm 高，整套替换掉。
OLD_BROKEN = ["anthurium", "calathea", "flower", "shrub", "pine", "cover", "jacaranda"]
OLD_SRC_DIRS = ["anthurium_botany_01", "calathea_orbifolia_01", "flower_gazania",
                "jacaranda_tree", "periwinkle_plant", "pine_sapling_small", "shrub_03"]


def log(*a):
    print("[prep]", *a, flush=True)


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


# ---------------------------------------------------------------- 0. 下载源件
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
API = "https://api.polyhaven.com/files/%s"


def _curl(url, dst):
    """curl 比 urllib 稳（有些环境会注入无效的代理变量，urllib 会踩）。"""
    import subprocess
    r = subprocess.run(["curl", "-sL", "--retry", "2", "--retry-delay", "2", "-C", "-",
                        "-m", "1800", "-H", "User-Agent: " + UA, url, "-o", dst],
                       capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dst)


def _md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(names):
    """从 PolyHaven 拉源件：<name>.blend（1k 版）+ 它 include 里的全部贴图。

    PolyHaven 的 .blend **不含贴图**：图是相对路径 //textures/xxx_1k.*，必须单独下，
    否则 pack_all 失败、资产渲染是品红/黑色。API 没有浏览器 UA 会 403。
    """
    os.makedirs(TEXSRC, exist_ok=True)
    for name in names:
        jp = os.path.join(RAW, "_files_%s.json" % name)
        ok = _curl(API % name, jp)
        if not ok:
            log("FETCH %-17s API 取不到文件清单（id 不存在？）" % name)
            continue
        try:
            d = json.load(open(jp, encoding="utf-8"))
            b = d["blend"]["1k"]["blend"]
        except Exception as e:
            log("FETCH %-17s 清单解析失败: %s" % (name, e))
            continue
        dst = os.path.join(RAW, "%s.blend" % name)
        if os.path.exists(dst) and _md5(dst) == b.get("md5"):
            log("FETCH %-17s blend 已在（md5 ok）" % name)
        else:
            _curl(b["url"], dst)
            log("FETCH %-17s blend %s" % (name, "ok" if _md5(dst) == b.get("md5") else "MD5 不符！"))
        n = 0
        for rel, meta in b.get("include", {}).items():
            tp = os.path.join(TEXSRC, os.path.basename(rel))
            if os.path.exists(tp) and _md5(tp) == meta.get("md5"):
                n += 1
                continue
            if _curl(meta["url"], tp) and _md5(tp) == meta.get("md5"):
                n += 1
            else:
                log("FETCH %-17s 贴图失败 %s" % (name, os.path.basename(rel)))
        log("FETCH %-17s 贴图 %d/%d" % (name, n, len(b.get("include", {}))))
        os.remove(jp)


# ---------------------------------------------------------------- 1. append
def append_objects(path, pattern):
    rx = re.compile(pattern)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if rx.match(n)]
    objs = [o for o in dst.objects if o is not None and o.type == "MESH"]
    sc = bpy.context.scene.collection
    for o in objs:
        if o.name not in sc.objects:
            sc.objects.link(o)
        o.hide_set(False)
        o.hide_viewport = False
        o.hide_render = False
        if o.data.users > 1:            # transform_apply 不接受多用户 mesh
            o.data = o.data.copy()
    return objs


# ---------------------------------------------------------------- 2. apply
def apply_transforms(objs):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


# ---------------------------------------------------------------- 3. join
def join_all(objs, name):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = vl.objects.active
    ob.name = name
    ob.data.name = name
    return ob


# ---------------------------------------------------------------- 4. 归一化
def normalise(ob):
    """X/Y 包围盒居中到原点，最低顶点 z=0；返回（高度, 半径）真实米制。"""
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    dx = -(min(xs) + max(xs)) * 0.5
    dy = -(min(ys) + max(ys)) * 0.5
    dz = -min(zs)
    if abs(dx) > 1e-9 or abs(dy) > 1e-9 or abs(dz) > 1e-9:
        for v in me.vertices:
            v.co.x += dx
            v.co.y += dy
            v.co.z += dz
        me.update()
    height = max(zs) - min(zs)
    radius = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.5
    ob.location = (0.0, 0.0, 0.0)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)
    return height, radius


# ---------------------------------------------------------------- 5. 减面
FOLIAGE_HINT = ("leaf", "leaves", "twig", "needle", "frond", "fern", "grass",
                "flower", "bloom", "petal", "foliage", "spruce", "frond")


def _is_foliage(matname):
    n = (matname or "").lower()
    return any(k in n for k in FOLIAGE_HINT)


def _decimate_pass(ob, target):
    cur = tri_count(ob.data)
    if cur <= target:
        return cur
    md = ob.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = max(0.004, target / float(cur))
    md.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=md.name)
    return tri_count(ob.data)


def _clean_loose(ob):
    """减面会留下成千上万的孤立顶点（jacaranda 87k 面配 392k 顶点），清掉省体积。"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.to_mesh(ob.data)
        ob.data.update()
    bm.free()
    return len(loose)


def _split_by_face_pred(ob, name, keep):
    """按面谓词切出一份只保留 keep(faces) 的对象（材质由 join 自动重映射）。"""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if not keep(f)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    left = [v for v in bm.verts if not v.link_faces]
    if left:
        bmesh.ops.delete(bm, geom=left, context="VERTS")
    nm = bpy.data.meshes.new(name)
    bm.to_mesh(nm)
    bm.free()
    for m in me.materials:
        nm.materials.append(m)
    new = bpy.data.objects.new(name, nm)
    bpy.context.scene.collection.objects.link(new)
    new.matrix_world = ob.matrix_world
    return new


def _split_decimate(ob, budget_hi):
    """整体 collapse 冲不到预算时：把「枝干/树皮」和「叶片」拆开各自减。
    树叶是成千上万张独立卡片，整体 ratio 一刀切时 Blender 会为了保住枝干把叶片全留着，
    结果树冠没减、枝干过量——分开减才控制得住。"""
    me = ob.data
    mats = [m.name if m else "" for m in me.materials]
    leaves = [i for i, n in enumerate(mats) if _is_foliage(n)]
    if not leaves or len(leaves) == len(mats):
        return ob
    keep_leaf = set(leaves)
    lo = ob.name
    a = _split_by_face_pred(ob, lo + "_foliage", lambda f: f.material_index in keep_leaf)
    b = _split_by_face_pred(ob, lo + "_struct", lambda f: f.material_index not in keep_leaf)
    if not a.data.polygons or not b.data.polygons:
        for x in (a, b):
            if x.data.polygons:
                continue
            bpy.data.objects.remove(x, do_unlink=True)
        return ob
    f_share = 0.74
    _decimate_pass(a, int(budget_hi * f_share))
    _decimate_pass(b, int(budget_hi * (1.0 - f_share)))
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    a.select_set(True)
    b.select_set(True)
    vl.objects.active = a
    bpy.ops.object.join()
    new = vl.objects.active
    old = ob
    old.name = lo + "_old"                 # 先让出名字，否则新对象会拿到 .001
    new.name = lo
    new.data.name = lo
    bpy.data.objects.remove(old, do_unlink=True)
    return new


def _islands(me):
    """连通分量（union-find）。PolyHaven 的树是卡片汤：一棵 jacaranda 有 27k 个互不相连的岛，
    边界边占 44%，collapse 减到某个底数就再也塌不动（不删岛就没法再少）。"""
    n = len(me.vertices)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    isl = {}
    for p in me.polygons:
        r = find(p.vertices[0])
        rec = isl.get(r)
        if rec is None:
            isl[r] = [[p.index], len(p.vertices) - 2]
        else:
            rec[0].append(p.index)
            rec[1] += len(p.vertices) - 2
    return isl


def _thin_islands(ob, target, big_tris=120):
    """整岛抽稀：大岛（枝干筒体）全留，小岛按质心排序后等距抽掉一部分。
    等距抽而不是随机抽——抽得空间均匀，树冠不会缺一大块。"""
    me = ob.data
    isl = _islands(me)
    if not isl:
        return 0
    co = [v.co for v in me.vertices]
    big, small = [], []
    for faces, t in isl.values():
        if t >= big_tris:
            big.append((faces, t))
        else:
            p = me.polygons[faces[0]]
            c = co[p.vertices[0]]
            small.append((faces, t, round(c.z, 2), round(c.x, 2), round(c.y, 2)))
    small.sort(key=lambda r: (r[2], r[3], r[4]))
    used = sum(t for _, t in big)
    if used >= target:
        # 光枝干就超预算了：这时候把小岛全删只会得到一棵没叶子的树（实测 jacaranda 就是这样
        # 变成光杆的）。宁可超预算也要保住叶子，由调用方决定要不要真的硬压。
        return 0
    room = target - used
    small_tris = max(1, sum(t for _, t, *_ in small))
    want = max(0, min(len(small), int(len(small) * room / small_tris)))
    keep = set()
    for faces, _ in big:
        keep.update(faces)
    if small and want:                       # 等距抽：保留 i = j*len/want
        stride = len(small) / float(want)
        for j in range(want):
            keep.update(small[int(j * stride)][0])
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if f.index not in keep]
    if not kill:
        bm.free()
        return 0
    nk = len(kill)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    left = [v for v in bm.verts if not v.link_faces]
    if left:
        bmesh.ops.delete(bm, geom=left, context="VERTS")
    bm.to_mesh(me)
    me.update()
    bm.free()
    return nk


def decimate_to(ob, target_hi):
    """冲到 target_hi 以内。

    三步交替（缺一步都到不了预算）：
      ① collapse 整体塌 —— 平时一步到位；
      ② 塌不动了（卡片汤：jacaranda 27k 个互不相连的小岛，边界边占 44%，ratio 给到 0.002
         面数也不再变）就把小岛整片抽稀；
      ③ 抽稀之后剩下的大岛（枝干筒体）是流形，再对它们 collapse 一次 —— 这一步才真能把
         53k 压到 25k。顺序反了就一直卡在"卡片减不掉、枝干减不动"。
    """
    t0 = tri_count(ob.data)
    for _ in range(8):
        if tri_count(ob.data) <= target_hi * 1.03:
            break
        before = tri_count(ob.data)
        _decimate_pass(ob, target_hi)
        if tri_count(ob.data) <= target_hi * 1.03:
            break
        if tri_count(ob.data) >= before * 0.999:        # collapse 塌不动 → 抽稀卡片
            _thin_islands(ob, int(target_hi * 0.92))
        if tri_count(ob.data) >= before * 0.999:        # 两种都无效，收工
            break
    if tri_count(ob.data) > target_hi * 1.15:
        ob = _split_decimate(ob, target_hi)
    _clean_loose(ob)
    return t0, tri_count(ob.data), ob


# ---------------------------------------------------------------- 6. 贴图
def used_images(ob):
    out = []
    for m in ob.data.materials:
        if not m or m.node_tree is None:
            continue
        for nd in m.node_tree.nodes:
            if nd.type == "TEX_IMAGE" and nd.image and nd.image not in out:
                out.append(nd.image)
    return out


def _basename(im):
    return os.path.basename(im.filepath.replace("\\", "/")) or (im.name + ".png")


def fix_source_paths():
    """append 之后 //textures/xxx.png 相对路径找不到文件，改指到 _raw/textures/。"""
    for im in bpy.data.images:
        if im.source != "FILE":
            continue
        p = os.path.join(TEXSRC, _basename(im))
        if os.path.exists(p) and im.filepath != p:
            im.filepath = p
            im.reload()


def needs_alpha(im, mats):
    tag = (im.name + " " + _basename(im)).lower()
    if any(k in tag for k in ("alpha", "opacity", "mask")):
        return True
    for m in mats:                                   # material 里 Alpha 口接了这张图
        if not m or m.node_tree is None:
            continue
        for nd in m.node_tree.nodes:
            if nd.type == "TEX_IMAGE" and nd.image is im:
                for o in nd.outputs:
                    if o.name == "Alpha" and o.is_linked:
                        return True
    return False


def encode_image(im, alpha):
    """缩到 ≤1024、重编码成 web 友好格式，返回新路径（失败返回 None）。"""
    if im.size[0] == 0:
        im.reload()
        if im.size[0] == 0:
            return None
    w, h = im.size
    if max(w, h) > MAX_TEX:
        s = MAX_TEX / float(max(w, h))
        im.scale(max(1, int(round(w * s))), max(1, int(round(h * s))))
    stem = os.path.splitext(_basename(im))[0]
    tag = (im.name + stem).lower()
    if alpha:
        fmt, ext, q = "PNG", ".png", 100
    else:
        fmt, ext = "JPEG", ".jpg"
        q = Q_NOR if "nor" in tag else (Q_DIFF if ("diff" in tag or "col" in tag) else Q_MISC)
    path = os.path.join(ENCDIR, stem + ext)
    im.file_format = fmt
    im.filepath_raw = path
    try:
        im.save(quality=q)
    except Exception as e:                            # 极少数图（如 32bit disp）转 JPEG 失败
        log("   ! save %s -> %s failed: %s" % (im.name, fmt, e))
        return None
    im.filepath = path                                # pack_all 从这里取
    return path


def process_textures(ob):
    mats = [m for m in ob.data.materials if m]
    keep = used_images(ob)
    for im in keep:
        alpha = needs_alpha(im, mats)
        encode_image(im, alpha)
    # 清掉本资产用不到的图 / 材质（变体自带的另外几套贴图，白占体积）
    for m in list(bpy.data.materials):
        if m is None:
            continue
        if m.users == 0:
            bpy.data.materials.remove(m)
    for im in list(bpy.data.images):
        if im.users == 0 or (im.source == "FILE" and im not in keep):
            try:
                bpy.data.images.remove(im)
            except Exception:
                pass
    # pack 进 blend —— 之后 .blend 自包含，append 出来不再依赖外部贴图
    try:
        bpy.ops.file.pack_all()
    except RuntimeError as e:
        log("   ! pack_all: %s" % e)
    for im in bpy.data.images:                        # 逐张兜底，缺一张不至于整资产失败
        if im.source == "FILE" and not im.packed_file:
            try:
                im.pack()
            except RuntimeError as e:
                log("   ! unpacked image %s: %s" % (im.name, e))
    unpacked = [im.name for im in bpy.data.images
                if im.source == "FILE" and not im.packed_file]
    if unpacked:
        log("   ! 仍有 %d 张未打包: %s" % (len(unpacked), ", ".join(unpacked)))
    return len(keep)


# ---------------------------------------------------------------- 7. 汇总
def scene_tris():
    return sum(tri_count(o.data) for o in bpy.data.objects if o.type == "MESH")


def prep(name, kind, pattern, opt=None):
    src = os.path.join(RAW, "%s.blend" % name)
    if not os.path.exists(src):
        log("SKIP %-17s 源文件不存在: %s" % (name, src))
        return None
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(ENCDIR, exist_ok=True)

    objs = append_objects(src, pattern)
    if not objs:
        log("FAIL %-17s 没匹配到对象（pattern=%s）" % (name, pattern))
        return None
    log("%-17s append %d obj: %s" % (name, len(objs), ", ".join(o.name for o in objs[:4])
                                     + (" ..." if len(objs) > 4 else "")))

    apply_transforms(objs)          # ← 上一版的 bug 就死在这步缺失
    ob = join_all(objs, name)

    lo, hi = BUDGET[kind]
    if opt and opt.get("max"):
        hi = int(opt["max"])                     # 单资产预算覆盖（见 JOBS 里的注释）
    t_before, t_after, ob = decimate_to(ob, hi)
    height, radius = normalise(ob)
    ntex = process_textures(ob)

    ob["src_height"] = round(height, 4)
    ob["src_radius"] = round(radius, 4)
    ob["src_tris"] = t_after
    ob["src_kind"] = kind

    out = os.path.join(ASSETS, "%s.blend" % name)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    mb = os.path.getsize(out) / 1048576.0
    over = "  ← 超预算" if t_after > hi * 1.05 else ""
    log("%-17s tris %7d→%6d (预算 %d–%d%s)  h=%.2f r=%.2f  tex=%d  %.2f MB  %.1fs"
        % (name, t_before, t_after, lo, hi,
           (", " + opt["note"]) if opt and opt.get("note") else "", height, radius,
           ntex, mb, time.time() - t0) + over)
    return dict(name=name, kind=kind, tris=t_after, height=round(height, 4),
                radius=round(radius, 4), tex=ntex, mb=round(mb, 2))


# ---------------------------------------------------------------- 8. 清理
def drop_old_assets():
    gone = []
    for stem in OLD_BROKEN:
        for ext in (".blend", ".blend1"):
            p = os.path.join(ASSETS, stem + ext)
            if os.path.exists(p):
                os.remove(p)
                gone.append(os.path.basename(p))
    for d in OLD_SRC_DIRS:                      # 旧的 glTF 源（已换成 _raw 里的 .blend）
        p = os.path.join(ASSETS, d)
        if os.path.isdir(p):
            n = len(os.listdir(p))
            for f in os.listdir(p):
                os.remove(os.path.join(p, f))
            os.rmdir(p)
            gone.append("%s/ (%d files)" % (d, n))
    return gone


def prune_raw():
    import shutil
    freed = 0.0
    for d in (ENCDIR, RAW):
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    freed += os.path.getsize(os.path.join(root, f)) / 1048576.0
            shutil.rmtree(d, ignore_errors=True)
    return freed


def du(path, skip=()):
    n = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in skip]
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n / 1048576.0


def du_no_raw(assets_dir):
    """成品库大小：不算 _raw / _enc（那是源件和中间产物，不随库交付）。"""
    return du(assets_dir, skip={RAW, ENCDIR})


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

    # 子进程模式：只处理一个资产，结果写成 json 交给父进程汇总。
    # 每个资产独占一个 Blender 进程 —— 大网格（jacaranda 1.8M 面）在同一进程里连着做
    # 几次 append/apply/decimate 会吃到 access violation，隔离进程后一个崩了也不带走整批。
    if "--one" in argv:
        name = argv[argv.index("--one") + 1]
        job = next((j for j in JOBS if j[0] == name), None)
        if job is None:
            log("未知资产 %s" % name)
            return
        r = prep(job[0], job[1], job[2], job[3] if len(job) > 3 else None)
        if r:
            with open(os.path.join(RAW, "_result_%s.json" % name), "w", encoding="utf-8") as f:
                json.dump(r, f)
        return

    want = [a for a in argv if not a.startswith("--")]
    if "--fetch" in argv:
        fetch(want or [j[0] for j in JOBS])
        return
    # 默认**保留** _raw：一次误跑就把 525 MB 源 .blend + 155 MB 源贴图删掉，重下要好几分钟
    # （已经栽过一次）。要清就显式 --prune。--keep-raw 仍接受，等义于默认。
    prune = "--prune" in argv

    gone = drop_old_assets()
    if gone:
        log("删除旧坏资产 %d 项: %s" % (len(gone), ", ".join(gone)))

    import subprocess
    rows, failed = [], []
    for name, kind, pattern, opt in JOBS:
        if want and name not in want:
            continue
        cmd = [bpy.app.binary_path, "-b", "--factory-startup",
               "--python", os.path.abspath(__file__), "--", "--one", name]
        t = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
            txt = (p.stdout or "") + (p.stderr or "")
            code = p.returncode
        except subprocess.TimeoutExpired:
            txt, code = "", -9
        for line in txt.splitlines():
            if line.startswith("[prep]") or "EXCEPTION" in line or line.startswith("Error "):
                print(line, flush=True)
        rp = os.path.join(RAW, "_result_%s.json" % name)
        if code == 0 and os.path.exists(rp):
            rows.append(json.load(open(rp, encoding="utf-8")))
            os.remove(rp)
        else:
            failed.append(name)
            log("FAIL %-17s 子进程 exit=%s（%.0fs）" % (name, code, time.time() - t))

    # 汇总表 + catalog.json（lib/assets2.catalog() 读它，省得每次 append 15 个 blend）
    print("")
    print("%-18s %7s %8s %8s %5s %8s" % ("asset", "tris", "height m", "radius m", "tex", "MB"))
    print("-" * 60)
    for r in sorted(rows, key=lambda x: (x["kind"], x["name"])):
        print("%-18s %7d %8.2f %8.2f %5d %8.2f"
              % (r["name"], r["tris"], r["height"], r["radius"], r["tex"], r["mb"]))
    print("-" * 60)
    print("%-18s %7d %8s %8s %5d %8.2f" % ("TOTAL", sum(r["tris"] for r in rows), "", "",
                                           sum(r["tex"] for r in rows), sum(r["mb"] for r in rows)))
    if failed:
        print("失败: %s" % ", ".join(failed))
    if rows:
        cat = {r["name"]: dict(kind=r["kind"], height=r["height"], radius=r["radius"],
                               tris=r["tris"], tex=r["tex"])
               for r in rows}
        cp = os.path.join(ASSETS, "catalog.json")
        old = {}
        if os.path.exists(cp):
            try:
                old = json.load(open(cp, encoding="utf-8"))
            except Exception:
                old = {}
        old.update(cat)
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(old, f, indent=1, ensure_ascii=False, sort_keys=True)
        log("catalog.json 更新（%d 条）" % len(old))

    log("assets/ 总大小 %.1f MB（不含 _raw）" % du_no_raw(ASSETS))
    if prune and not want:
        freed = prune_raw()
        log("--prune：清掉 _raw/_enc，释放 %.1f MB；assets/ 现在 %.1f MB"
            % (freed, du_no_raw(ASSETS)))
    else:
        log("保留 _raw/_enc（要清加 --prune）")


main()
