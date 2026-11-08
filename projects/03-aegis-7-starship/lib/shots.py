"""starship/lib/shots.py — 影棚灯光 / 相机 / 渲染（EEVEE Next 光追，30 m 尺度标定）

灯能量按距离² 标定：mk18 是 0.8 m 的枪（柔光箱 110 W @1.2 m），
这里舰长 32 m，灯摆在 20–40 m 外，能量按 (d/1.2)² 放大。
"""
import bpy, math, os
from mathutils import Vector
import env as ENV


def env_studio(strength=0.34):
    """程序化影棚 equirect 环境图（金属反射的形状全靠它），加两盏极柔面光做方向感"""
    ENV.build_env()
    ENV.world_env(strength, bg_color=(0.008, 0.009, 0.012))
    sc = bpy.context.scene
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    return sc.world


def light_box(name, loc, target, size, energy, color=(1, 1, 1), shape='RECTANGLE', size_y=None):
    l = bpy.data.lights.new(name, 'AREA')
    l.shape = shape
    l.size = size
    if size_y:
        l.size_y = size_y
    l.energy = energy
    l.color = color
    ob = bpy.data.objects.new(name, l)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def studio_lights(target=(0.0, 0.0, 0.0), S=1.0):
    """舰体尺度三点光：主光 40 m 外大柔光箱 + 冷补光 + 两道轮廓条灯"""
    out = []
    out.append(light_box("key", (18 * S, -34 * S, 26 * S), target, 22 * S, 90000 * S * S,
                         (1.0, 0.975, 0.945)))
    out.append(light_box("fill", (-30 * S, -26 * S, 8 * S), target, 26 * S, 6500 * S * S,
                         (0.82, 0.90, 1.0)))
    out.append(light_box("rim", (-14 * S, 34 * S, 20 * S), target, 16 * S, 42000 * S * S,
                         (0.90, 0.95, 1.0)))
    # 顶部天光条（长条，给背脊一条连续高光）
    out.append(light_box("topbar", (2 * S, 6 * S, 40 * S), target, 34 * S, 16000 * S * S,
                         (1.0, 1.0, 1.0), size_y=6 * S))
    # 两侧窄条灯：舷侧金属的反光条
    for sgn in (-1, 1):
        out.append(light_box("strip%d" % sgn, (4 * S, sgn * 26 * S, 2 * S), (0, 0, 0),
                             26 * S, 9000 * S * S, (1.0, 1.0, 1.0), size_y=3 * S))
    return out


def setup_render(res=(1600, 900), samples=64, engine='EEVEE', transparent=False, exposure=-0.85):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE' if engine == 'EEVEE' else 'CYCLES'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = exposure
    if engine == 'EEVEE':
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_raytracing = True
        try:
            sc.eevee.ray_tracing_options.use_denoise = True
        except Exception:
            pass
        try:
            sc.eevee.use_shadows = True
        except Exception:
            pass
    else:
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        try:
            sc.cycles.device = 'GPU'
        except Exception:
            pass
    return sc


def camera(name, loc, look_at=(0, 0, 0), lens=85, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = ob
    return ob


def mean_lum(path):
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
    lum = float((0.2126 * px[:, :, 0] + 0.7152 * px[:, :, 1] + 0.0722 * px[:, :, 2]).mean())
    bpy.data.images.remove(img)
    return lum


def shot(path, report=True):
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    msg = "SHOT %s" % path
    if report:
        try:
            msg += "  mean_lum=%.3f" % mean_lum(path)
        except Exception as e:
            msg += "  (lum fail %s)" % e
    print(msg)
    return path


def auto_exposure(path, target=0.26, lo=0.10, hi=0.62, tries=3, res=(800, 450), samples=16):
    sc = bpy.context.scene
    ox, oy = sc.render.resolution_x, sc.render.resolution_y
    os_ = sc.eevee.taa_render_samples
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.eevee.taa_render_samples = samples
    for i in range(tries):
        shot(path, report=False)
        m = mean_lum(path)
        print("  exp=%.2f mean=%.3f" % (sc.view_settings.exposure, m))
        if lo <= m <= hi:
            break
        sc.view_settings.exposure += math.log2(target / max(m, 1e-4)) * 0.7
    sc.render.resolution_x, sc.render.resolution_y = ox, oy
    sc.eevee.taa_render_samples = os_
    return sc.view_settings.exposure


def ground(size=140.0, mat=None, z=-6.5):
    """深色地面（接影用）：飞船"停"在空中，地面只做反光与阴影承接"""
    import bmesh
    me = bpy.data.meshes.new("ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("ground", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 0, z)
    m = mat or bpy.data.materials.get("S_Ground")
    if not m:
        m = bpy.data.materials.new("S_Ground")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs['Base Color'].default_value = (0.004, 0.0045, 0.0055, 1)
        b.inputs['Roughness'].default_value = 0.62
        b.inputs['Metallic'].default_value = 0.10
    me.materials.append(m)
    return ob


# ------------------------------------------------------------------ 机位预置
def cam_hero():
    return camera("cam_hero", (38.0, -34.0, 17.0), (0.5, 0.0, 0.2), lens=46)


def cam_side(y=52.0, sign=1):
    return camera("cam_side", (0.4, sign * y, 1.6), (0.2, 0, 0.2), lens=52)


def cam_top(z=58.0):
    return camera("cam_top", (0.4, 0.0, z), (0.4, 0.0, 0.0), lens=52)


def cam_rear(power=True):
    """尾部机位：专门看三台引擎喷口与尾焰"""
    return camera("cam_rear", (-34.0, -15.0, 8.0), (-15.5, 0.0, -0.1), lens=62)


def cam_explode(dist=76.0):
    return camera("cam_explode", (dist * 0.62, -dist * 0.78, dist * 0.42), (0.0, 0.0, 0.0), lens=52)
