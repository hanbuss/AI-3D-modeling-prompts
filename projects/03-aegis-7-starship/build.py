"""starship/build.py — 总装：船体基线 + 各分系统模块 → 材质/UV → 元数据 → GLB/manifest

用法（无头，必须）：
    blender -b -P build.py
    blender -b -P build.py -- --no-glb        # 只建场景
    blender -b -P build.py -- --only fore     # 只装某一个模块（调试）

模块契约（每个 lib/<mod>.py 必须提供）：
    build(M, col) -> list[Object]     # M = mats.M() 字典, col = 该组的 collection
零件必须用 kit.part(...) 打标签，group 必须取自 spec.GROUP_BASE。
"""
import bpy, sys, os, time, math, json, traceback

P = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(P, "lib"))

import kit
import mats
import hull
import spec as S
import export as EX

MODULES = [
    ("fore",    "fore.py",    "COL_FORE"),
    ("mid",     "mid.py",     "COL_MID"),
    ("aft",     "aft.py",     "COL_AFT"),
    ("fx",      "fx.py",      "COL_FX"),
    ("wings",   "wings.py",   "COL_WINGS"),
    ("weapons", "weapons.py", "COL_WEAPONS"),
    ("gear",    "gear.py",    "COL_GEAR"),
]

# 兜底：aft.py / fx.py 没到位时，用 lib/aft_lead.py（Lead 保底实现）顶上，尾焰和喷口永远不缺
FALLBACK = {"aft": ("aft_lead", "build"), "fx": ("aft_lead", "build_fx")}


def build_hull_base(M, cols):
    """三段船体：接缝环点一致，拆开时严丝合缝"""
    out = []
    specs = [
        ("hull_fore", S.HULL_SEG["hull_fore"], M['hull'], (1, 0, 0), "前段船体", "Forward Hull",
         "舰首至座舱后隔框：外形段 + 装甲板基底"),
        ("hull_mid",  S.HULL_SEG["hull_mid"],  M['hull'], (0.55, 0, 0.15), "中段船体", "Center Hull",
         "主承力段：油箱/弹舱/机翼根部接头所在"),
        ("hull_aft",  S.HULL_SEG["hull_aft"],  M['hull'], (-1, 0, 0), "尾段船体", "Aft Hull",
         "动力段：三台主引擎安装座与尾框"),
    ]
    for pid, (x0, x1), mat, d, zh, en, note in specs:
        nx = max(12, int(abs(x0 - x1) * 2.4))
        ob = hull.segment(pid, x0, x1, nx=nx, n=40, mat=mat, col=cols['hull'])
        grp = pid            # hull_fore / hull_mid / hull_aft
        kit.part(ob, pid, zh, en, grp, d, order=S.GROUP_BASE[grp], note=note)
        out.append(ob)
    return out


def build(all_modules=True, only=None, save=True, glb=True, verbose=True, keep_fx=False):
    t0 = time.time()
    kit.clean_scene()
    M = mats.M()
    cols = {}
    for key, _, cname in MODULES:
        cols[key] = kit.new_col(cname)
    cols['hull'] = kit.new_col("COL_HULL")

    parts = build_hull_base(M, cols)

    for key, modname, _cname in MODULES:
        if only and key != only:
            continue
        if not os.path.exists(os.path.join(P, "lib", modname)):
            fb = FALLBACK.get(key)
            if not fb or not os.path.exists(os.path.join(P, "lib", fb[0] + ".py")):
                if verbose:
                    print("SKIP module %s (no lib/%s yet)" % (key, modname))
                continue
            try:
                mod = __import__(fb[0])
                res = getattr(mod, fb[1])(M, cols[key])
                got = [o for o in (res or []) if o is not None]
                parts += got
                if verbose:
                    print("FALLBACK %-8s -> %3d objects (via lib/%s.py)" % (key, len(got), fb[0]))
            except Exception:
                print("!! FALLBACK %s FAILED" % key)
                traceback.print_exc()
            continue
        try:
            mod = __import__(modname[:-3])
            res = mod.build(M, cols[key])
            got = [o for o in (res or []) if o is not None]
            parts += got
            if verbose:
                print("MODULE %-8s -> %3d objects" % (key, len(got)))
        except Exception:
            print("!! MODULE %s FAILED" % key)
            traceback.print_exc()

    # 尾焰/激光是"渲染件"：默认不进 GLB（Three.js 那边会用 shader 自己生成，双份会打架，
    # 而且 60 m 的激光束会把包围盒撑到 88 m，取景和爆炸中心全毁）
    if not keep_fx:
        # 先把名字抄下来再做删除：bpy 里对象一旦 remove，句柄就失效，之后碰 .name 会抛 ReferenceError
        named = [(p.name, p) for p in parts if p is not None]
        dead_names = {o.name for o in bpy.context.scene.objects if o.name.startswith("fx_")}
        parts = [p for (nm, p) in named if nm not in dead_names]
        for o in [x for x in bpy.context.scene.objects if x.name in dead_names]:
            bpy.data.objects.remove(o, do_unlink=True)
        if verbose and dead_names:
            print("DROP fx objects %d (render-only)" % len(dead_names))

    refine_explode([o for o in parts if o is not None and 'part_id' in o])

    # 网格合法性兜底：把退化面/重复点清掉，glTF 导出才不会再报 "mesh is not valid"
    for o in [x for x in bpy.context.scene.objects if x.type == 'MESH']:
        try:
            o.data.validate(verbose=False, clean_customdata=False)
        except Exception as e:
            print("  ! validate failed", o.name, e)

    # UV + 平滑
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    mats.assign_all_uv(meshes)

    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in meshes)
    bb = [1e9] * 3 + [-1e9] * 3
    for o in meshes:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                bb[i] = min(bb[i], w[i])
                bb[i + 3] = max(bb[i + 3], w[i])
    size = [round(bb[i + 3] - bb[i], 3) for i in range(3)]
    tagged = [o for o in meshes if 'part_id' in o]
    if verbose:
        print("BUILD  objects=%d  tagged_parts=%d  tris=%d  size(m)=%s  %.1fs"
              % (len(meshes), len(tagged), tris, size, time.time() - t0))

    os.makedirs(os.path.join(P, "out"), exist_ok=True)
    man = EX.objects_manifest()
    EX.write_manifest(os.path.join(P, "out", "manifest.json"), man)

    # 引擎/武器元数据（Three.js 侧要用它生成尾焰与激光）
    meta = ship_meta()
    json.dump(meta, open(os.path.join(P, "out", "ship_meta.json"), "w"), indent=1)

    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P, "out", "starship.blend"))
    if glb:
        g = os.path.join(P, "out", "starship.glb")
        EX.export_glb(g)
        st = EX.glb_stats(g)
        st.update(dict(size_m=size, parts=len(tagged), tris=tris))
        json.dump(st, open(os.path.join(P, "out", "glb_stats.json"), "w"), indent=1)
        if verbose:
            print("GLB", st)
    return parts


# ------------------------------------------------------------------ 爆炸向量统一化
# 爆炸幅度（米）：整舰 32 m 长，收在"结构清晰但不散架"的范围内 —— 太大就变成一堆远处的碎点
GROUP_MAG = {
    "weapons": 5.0, "gear": 4.0, "canopy": 3.4, "engines": 5.0,
    "wings": 4.6, "hull_fore": 7.0, "hull_mid": 5.0, "hull_aft": 6.5,
    "detail": 2.3,
}


def refine_explode(parts):
    """统一算爆炸向量与拆解顺序（覆盖各模块自己填的值）。

    规则：从全舰包围盒中心出发，按零件世界包围盒中心的方向径向炸开；
    再按"沿舰轴向外 + 高度"加权，保证前段向前、尾段向后、机翼向两侧、细节件向外，
    既不会互相穿插，也不会因为模块各自填的数不一样而显得乱七八糟。
    序号：组基线（spec.GROUP_BASE）+ 组内按 |x| 从舰中向外排。
    """
    from mathutils import Vector
    bb = [1e9] * 3 + [-1e9] * 3
    for o in parts:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                bb[i] = min(bb[i], w[i])
                bb[i + 3] = max(bb[i + 3], w[i])
    ctr = Vector(((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2))

    by_group = {}
    for o in parts:
        g = o.get("group", "detail")
        by_group.setdefault(g, []).append(o)

    for g, objs in by_group.items():
        base = S.GROUP_BASE.get(g, 90)
        mag = GROUP_MAG.get(g, 8.0)
        # 组内排序：离舰体中心越远越先拆
        def cx(o):
            mn = [1e9] * 3; mx = [-1e9] * 3
            verts = list(o.data.vertices)
            for v in verts[::max(1, len(verts) // 64)]:
                w = o.matrix_world @ v.co
                for i in range(3):
                    mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
            c2 = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2))
            return -abs(c2.x - ctr.x)
        objs.sort(key=cx)
        n = len(objs)
        for i, o in enumerate(objs):
            mn = [1e9] * 3; mx = [-1e9] * 3
            step = max(1, len(o.data.vertices) // 96)
            verts2 = list(o.data.vertices)
            for v in verts2[::step]:
                w = o.matrix_world @ v.co
                for k in range(3):
                    mn[k] = min(mn[k], w[k]); mx[k] = max(mx[k], w[k])
            c = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2))
            d = c - ctr
            # 轴向加权：前后段往两端飞，机翼/武器往侧上下飞
            d.x *= 1.15
            d.y *= 1.25 if g in ("wings", "weapons", "gear") else 1.0
            d.z *= 0.9
            if d.length < 1e-4:
                d = Vector((0.0, 0.0, 1.0))
            d.normalize()
            spread = mag * (0.86 + 0.28 * (i / max(1, n - 1)))
            o["explode"] = [round(d.x * spread, 3), round(d.y * spread, 3), round(d.z * spread, 3)]
            o["order"] = int(base + i)
    return parts


def _to_gltf(p):
    """Blender(X,Y,Z) -> glTF/Three.js (X, Z, -Y)（export_yup=True 的映射）"""
    return [round(float(p[0]), 4), round(float(p[2]), 4), round(float(-p[1]), 4)]


def ship_meta():
    eng = []
    for eid in S.ENGINE_IDS:
        y, z, r_body, xs, xe, br_out, br_in, exit_x, flen = S.ENGINES[eid]
        eng.append(dict(id=eid, pos=_to_gltf((exit_x, y, z)), dir=_to_gltf((-1, 0, 0)),
                        r_out=round(br_out, 3), r_in=round(br_in, 3),
                        flame_len=round(flen, 2),
                        color=[1.0, 0.55, 0.18]))
    t = S.TURRET_DORSAL
    return {
        "ship": S.SHIP_NAME, "class": S.SHIP_CLASS,
        "length_m": S.LENGTH_M, "span_m": S.SPAN_M,
        "engines": eng,
        "turret": dict(pos=_to_gltf((t['x'], t['y'], t['z'] + 0.55)),
                       dir=_to_gltf((1, 0, 0.02)), color=[0.15, 0.72, 1.0]),
        "groups": S.GROUP_ZH,
    }


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    build(all_modules=True, only=only,
          save=("--no-save" not in argv),
          glb=("--no-glb" not in argv),
          keep_fx=("--keep-fx" in argv))
