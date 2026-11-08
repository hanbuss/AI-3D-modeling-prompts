"""starship/tools/smoke.py — 单模块冒烟：船体基线 + 指定模块 + 出图（给分件负责人自检用）

用法：
    blender -b -P tools/smoke.py -- --module fore
    blender -b -P tools/smoke.py -- --module aft --cam rear --res 960x540
    blender -b -P tools/smoke.py -- --module all --cam hero --res 1280x720 --samples 32

cam 可选：hero / side / top / rear / explode
输出：previews/smoke_<module>_<cam>.png
"""
import bpy, sys, os, time, traceback

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P, "lib"))

import kit, mats, hull, shots
import spec as S

CAMS = {"hero": "cam_hero", "side": "cam_side", "top": "cam_top",
        "rear": "cam_rear", "explode": "cam_explode"}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

    def arg(name, default=None):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    module = arg("--module", "all")
    cam = arg("--cam", "hero")
    res_s = arg("--res", "960x540")
    res = tuple(int(v) for v in res_s.lower().split("x")) if "x" in res_s else (960, 540)
    samples = int(arg("--samples", "24"))

    kit.clean_scene()
    M = mats.M()
    col_hull = kit.new_col("COL_HULL")
    col_mod = kit.new_col("COL_" + module.upper())

    # 船体基线（三段都给，方便看接缝对位）
    for pid, (x0, x1) in S.HULL_SEG.items():
        hull.segment(pid, x0, x1, nx=max(12, int(abs(x0 - x1) * 2.4)), n=36,
                     mat=(M['hull'] if pid != "hull_mid" else M['hull_dark']), col=col_hull)

    import build as B
    names = [module] if module != "all" else [k for k, _f, _c in B.MODULES]
    for name in names:
        f = os.path.join(P, "lib", name + ".py")
        if not os.path.exists(f):
            print("SKIP", name)
            continue
        try:
            mod = __import__(name)
            got = mod.build(M, col_mod)
            print("MODULE %-8s -> %s objects" % (name, len(got or [])))
        except Exception:
            print("!! MODULE %s FAILED" % name)
            traceback.print_exc()

    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    mats.assign_all_uv(meshes)
    tris = sum(sum(len(fc.vertices) - 2 for fc in o.data.polygons) for o in meshes)
    print("SMOKE objects=%d tris=%d" % (len(meshes), tris))

    shots.env_studio(1.05)
    shots.studio_lights((0.0, 0.0, 0.2), S=1.0)
    getattr(shots, CAMS.get(cam, "cam_hero"))()
    shots.setup_render(res=res, samples=samples, engine='EEVEE')
    out = os.path.join(P, "previews", "smoke_%s_%s.png" % (module, cam))
    shots.shot(out)


if __name__ == "__main__":
    main()
