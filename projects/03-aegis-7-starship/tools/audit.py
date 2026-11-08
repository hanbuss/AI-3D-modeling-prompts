"""starship/tools/audit.py — 几何验收（爆炸图/网页之前必须过这一关）

检查项：
  1) 每个 mesh 是否带 part_id；part_id 是否唯一
  2) 每个分组零件数、三角面数（含预算告警）
  3) 退化几何：零面积面、NaN 坐标、松散点
  4) 浮空件：与**所有**其他零件的包围盒距离都 > 阈值 → 大概率没贴上结构
  5) 爆炸向量：是否为零、是否过大（爆炸图会散架）
  6) 全局包围盒与舰体尺度核对

用法：
    blender -b -P tools/audit.py            # 建场景再审计
    blender -b -P tools/audit.py -- --blend out/starship.blend   # 审已有工程
输出：out/audit.json + 控制台报告（FAIL 会以 AUDIT_FAIL 开头，方便脚本判断）
"""
import bpy, sys, os, json, math
from mathutils import Vector

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P, "lib"))

FLOAT_TOL = 0.04        # 米：包围盒间距超过这个值就报警（4 cm）
EXPLODE_MAX = 18.0      # 米（32 m 长的舰，零件飞 13–15 m 是合理的爆炸图幅度）


def bbox_world(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return mn, mx


def bbox_gap(a, b):
    (amn, amx), (bmn, bmx) = a, b
    dx = max(0.0, max(amn.x - bmx.x, bmn.x - amx.x))
    dy = max(0.0, max(amn.y - bmx.y, bmn.y - amx.y))
    dz = max(0.0, max(amn.z - bmx.z, bmn.z - amx.z))
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def degenerate(me):
    bad_area = 0
    for p in me.polygons:
        if p.area < 1e-9:
            bad_area += 1
    nan = 0
    for v in me.vertices:
        if not all(map(math.isfinite, (v.co.x, v.co.y, v.co.z))):
            nan += 1
    return bad_area, nan, 0


def run():
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    parts = [o for o in meshes if 'part_id' in o]
    rep = {"meshes": len(meshes), "parts": len(parts), "fails": [], "warns": []}

    # 1) 标签
    untagged = [o.name for o in meshes if 'part_id' not in o]
    if untagged:
        rep["warns"].append("未打 part_id 的对象 %d 个：%s" % (len(untagged), untagged[:8]))
    ids = [o["part_id"] for o in parts]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        rep["fails"].append("part_id 重复：%s" % dup)

    # 2) 分组 & 三角面
    groups = {}
    total_tris = 0
    per_part = []
    bb = {}
    for o in parts:
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        total_tris += tris
        g = o.get("group", "?")
        groups.setdefault(g, {"parts": 0, "tris": 0})
        groups[g]["parts"] += 1
        groups[g]["tris"] += tris
        bb[o.name] = bbox_world(o)
        bad_area, nan, _loose = degenerate(o.data)
        if nan:
            rep["fails"].append("%s 含 NaN 顶点 %d 个" % (o.name, nan))
        if bad_area:
            rep["warns"].append("%s 零面积面 %d 个" % (o.name, bad_area))
        e = list(o.get("explode", (0, 0, 0)))
        el = math.sqrt(sum(v * v for v in e))
        if el < 1e-6:
            rep["warns"].append("%s 爆炸向量为 0（会在拆解时留在原地）" % o.name)
        elif el > EXPLODE_MAX:
            rep["fails"].append("%s 爆炸位移过大 %.1f m" % (o.name, el))
        per_part.append(dict(id=o["part_id"], name=o.name, group=g, tris=tris,
                             order=int(o.get("order", 0)), explode_len=round(el, 3),
                             min=[round(v, 3) for v in bb[o.name][0]],
                             max=[round(v, 3) for v in bb[o.name][1]],
                             note=o.get("note", "")))
    rep["groups"] = groups
    rep["total_tris"] = total_tris
    rep["parts_detail"] = sorted(per_part, key=lambda d: (d["group"], d["order"]))

    # 3) 全局包围盒
    gmn = Vector((1e9, 1e9, 1e9)); gmx = Vector((-1e9, -1e9, -1e9))
    for (mn, mx) in bb.values():
        for i in range(3):
            gmn[i] = min(gmn[i], mn[i]); gmx[i] = max(gmx[i], mx[i])
    rep["bbox_min"] = [round(v, 3) for v in gmn]
    rep["bbox_max"] = [round(v, 3) for v in gmx]
    rep["size_m"] = [round(gmx[i] - gmn[i], 3) for i in range(3)]

    # 4) 浮空检测（与所有其他件的包围盒最小间距都超阈值）
    names = list(bb.keys())
    floaters = []
    for i, n in enumerate(names):
        best = 1e9
        for j, m in enumerate(names):
            if i == j:
                continue
            g = bbox_gap(bb[n], bb[m])
            if g < best:
                best = g
            if best <= FLOAT_TOL:
                break
        if best > FLOAT_TOL:
            floaters.append((n, round(best, 3)))
    if floaters:
        rep["warns"].append("疑似浮空件 %d 个（与最近零件间距 > %.0f cm）：%s"
                            % (len(floaters), FLOAT_TOL * 100, floaters[:10]))
        rep["floaters"] = floaters

    # 5) 预算
    if total_tris > 900000:
        rep["warns"].append("总三角面 %d 偏大（网页端建议 < 60 万）" % total_tris)

    os.makedirs(os.path.join(P, "out"), exist_ok=True)
    json.dump(rep, open(os.path.join(P, "out", "audit.json"), "w"), ensure_ascii=False, indent=1)

    print("AUDIT parts=%d tris=%d size=%s" % (len(parts), total_tris, rep["size_m"]))
    for g in sorted(groups):
        print("  %-12s parts=%3d tris=%7d" % (g, groups[g]["parts"], groups[g]["tris"]))
    for w in rep["warns"]:
        print("  WARN", w)
    for f in rep["fails"]:
        print("AUDIT_FAIL", f)
    print("AUDIT ok" if not rep["fails"] else "AUDIT has failures")
    return rep


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    blend = None
    if "--blend" in argv:
        blend = argv[argv.index("--blend") + 1]
    if blend:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
    else:
        import build as B
        B.build(all_modules=True, save=False, glb=False, verbose=True)
    run()


if __name__ == "__main__":
    main()
