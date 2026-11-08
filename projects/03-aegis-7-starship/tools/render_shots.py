"""starship/tools/render_shots.py — 成品机位渲染（EEVEE + 合成器辉光）

用法：
    blender -b -P tools/render_shots.py
    blender -b -P tools/render_shots.py -- --res 1600x900 --samples 64
    blender -b -P tools/render_shots.py -- --only hero,rear,explode

输出：previews/<shot>.png
"""
import bpy, sys, os, math, time, json
from mathutils import Vector

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P, "lib"))

import kit, mats, hull, shots
import spec as S
import build as B


# ------------------------------------------------------------------ 合成器
def add_glare(threshold=0.85, size=7, strength=0.42):
    """合成器辉光（Blender 5.x：Glare 节点改成"接口/socket"参数，不再是节点属性）。
    Type=FOG_GLOW，质量 HIGH；失败就跳过，不影响出图。"""
    sc = bpy.context.scene
    try:
        ng = getattr(sc, "compositing_node_group", None)
        if ng is None:
            ng = bpy.data.node_groups.new("Comp", 'CompositorNodeTree')
            sc.compositing_node_group = ng
        nt = ng
        had_iface = len(nt.interface.items_tree) > 0 if hasattr(nt, "interface") else False
        nt.nodes.clear()
        rl = nt.nodes.new('CompositorNodeRLayers')
        gl = nt.nodes.new('CompositorNodeGlare')

        def setin(name, val):
            if name not in gl.inputs:
                return False
            try:
                gl.inputs[name].default_value = val
                return True
            except Exception:
                return False

        picked = None
        for cand in ('Bloom', 'BLOOM', 'Fog Glow', 'FOG_GLOW'):
            try:
                gl.inputs['Type'].default_value = cand
                picked = cand
                break
            except Exception:
                continue
        if picked is None:
            print("GLARE skip: 找不到 Bloom 类型（5.x 枚举动态，未能赋值）")
            return None
        setin('Quality', 'HIGH')
        setin('Threshold', threshold)
        setin('Strength', strength)
        setin('Size', size)
        setin('Saturation', 1.0)

        try:
            out = nt.nodes.new('NodeGroupOutput')
            if not had_iface:
                nt.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            nt.links.new(gl.outputs['Image'], out.inputs[0])
        except Exception:
            comp = nt.nodes.new('CompositorNodeComposite')
            nt.links.new(gl.outputs['Image'], comp.inputs['Image'])
        nt.links.new(rl.outputs['Image'], gl.inputs['Image'])
        print("GLARE on  type=%s strength=%.2f" % (gl.inputs['Type'].default_value, strength))
        return gl
    except Exception as e:
        print("GLARE skip:", e)
        return None


def engine_lights():
    """喷口处的橙色点光：让尾焰真的照亮尾部结构（这一盏决定"点火感"）"""
    out = []
    for eid in S.ENGINE_IDS:
        y, z, r_body, xs, xe, br_out, br_in, exit_x, flen = S.ENGINES[eid]
        l = bpy.data.lights.new("eng_%s" % eid, 'POINT')
        l.energy = 26000.0
        l.color = (1.0, 0.52, 0.16)
        l.shadow_soft_size = 0.55
        ob = bpy.data.objects.new("eng_%s" % eid, l)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = (exit_x - 1.2, y, z)
        out.append(ob)
    # 激光冷光（仅 laser 机位用得上，先建好隐藏）
    l = bpy.data.lights.new("laser_light", 'POINT')
    l.energy = 0.0
    l.color = (0.25, 0.8, 1.0)
    ob = bpy.data.objects.new("laser_light", l)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (S.TURRET_DORSAL['x'] + 6.0, 0, S.TURRET_DORSAL['z'] + 0.6)
    return out


def explode_scene(parts, amp=1.0):
    """按 part 元数据把零件沿 explode 向量推开（爆炸图用）"""
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or 'part_id' not in o:
            continue
        e = o.get("explode", (0, 0, 0))
        o.location = o.location + Vector((e[0] * amp, e[1] * amp, e[2] * amp))


def build_scene(verbose=False):
    B.build(all_modules=True, save=False, glb=False, verbose=verbose, keep_fx=True)
    # 飞船不落地：深空背景 + 影棚反射，比"模型摆在灰地上"高级得多
    shots.env_studio(0.34)
    shots.studio_lights((0.0, 0.0, 0.2), S=1.0)
    engine_lights()
    shots.setup_render(res=(1600, 900), samples=48, engine='EEVEE')
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']


# ------------------------------------------------------------------ 机位定义
def shot_defs():
    """(名字, 相机建立函数, 说明)"""
    return [
        ("hero", lambda: shots.camera("c", (36.0, -30.0, 14.0), (0.5, 0.0, 0.1), lens=60),
         "三分之四主视角"),
        ("side_right", lambda: shots.camera("c", (0.4, 46.0, 1.0), (0.2, 0, 0.2), lens=100),
         "右舷侧视"),
        ("top", lambda: shots.camera("c", (0.4, 0.0, 56.0), (0.4, 0.0, 0.0), lens=85),
         "俯视（看翼展与背脊）"),
        ("front", lambda: shots.camera("c", (30.0, -8.0, 3.2), (2.0, 0.0, 0.2), lens=55),
         "舰首（看座舱与鼻锥）"),
        ("rear", lambda: shots.camera("c", (-31.0, -12.0, 6.5), (-15.0, 0.0, -0.1), lens=68),
         "尾部（三台引擎 + 尾焰）"),
        ("detail_cockpit", lambda: shots.camera("c", (17.5, -6.4, 3.6), (9.4, 0.0, 0.9), lens=85),
         "座舱特写"),
        ("detail_engine", lambda: shots.camera("c", (-21.0, -4.2, 1.4), (-16.2, -2.55, -0.15), lens=90),
         "主引擎喷口特写"),
        ("explode", None, "爆炸图（全部零件按 order 展开）"),
        ("laser", lambda: shots.camera("c", (24.0, -20.0, 9.0), (6.0, 0.0, 1.6), lens=62),
         "激光发射"),
    ]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

    def arg(n, d=None):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else d

    res = arg("--res", "1600x900")
    res = tuple(int(v) for v in res.lower().split("x"))
    samples = int(arg("--samples", "48"))
    only = arg("--only", "")
    only = [s.strip() for s in only.split(",") if s.strip()]

    t0 = time.time()
    parts = build_scene()
    print("SCENE meshes=%d  %.1fs" % (len(parts), time.time() - t0))

    sc = shots.setup_render(res=res, samples=samples, engine='EEVEE')
    add_glare(threshold=1.15, size=7)

    outdir = os.path.join(P, "previews")
    os.makedirs(outdir, exist_ok=True)
    done = []
    # 激光束只在 laser 机位可见（otherwise 它会横穿主视角，看着像模型坏了）
    laser_objs = [o for o in bpy.context.scene.objects if o.name.startswith("fx_laser")]

    def laser_visible(on):
        for o in laser_objs:
            o.hide_render = not on

    for name, mk, note in shot_defs():
        if only and name not in only:
            continue
        laser_visible(name == "laser")
        if name == "explode":
            explode_scene(parts, amp=1.0)
            shots.camera("c", (58.0, -52.0, 34.0), (0.0, 0.0, 0.0), lens=58)
        else:
            mk()
        path = os.path.join(outdir, "%s.png" % name)
        t1 = time.time()
        shots.shot(path, report=True)
        done.append(dict(shot=name, note=note, path=path, sec=round(time.time() - t1, 1)))
    json.dump(done, open(os.path.join(outdir, "shots.json"), "w"), ensure_ascii=False, indent=1)
    print("SHOTS done %d  total %.1fs" % (len(done), time.time() - t0))


if __name__ == "__main__":
    main()
