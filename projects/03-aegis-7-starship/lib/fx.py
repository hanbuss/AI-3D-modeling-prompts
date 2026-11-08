"""starship/lib/fx.py — 特效件：三台引擎尾焰（3 层同心锥）+ 炮塔激光束

这些网格是「看得见的特效」而不是结构件，但它们在 Three.js 里同样要能点选/拆解，
所以一律 kit.part 打标签（group='detail'，part_id 前缀 "fx_"）。

参数全部来自 spec：
  尾焰长度  = ENGINES[eid].flame_len
  尾焰根部  = ENGINES[eid].exit_x / (y, z)，半径 = bell_r_in（喷口内半径）
  激光起点  = TURRET_DORSAL (x, y, z+0.55)，方向 +X，长 LASER_LEN
"""
import math

import bpy, bmesh

import kit
import mats
import spec as S

TAU = math.tau

# 光束长度（m）：build.py 的 ship_meta 只用位置/方向，长度只影响渲染构图。
# Lead 约束：fx_ 特效件单件长度 ≤ 20 m（GLB 里会被剔除，只在渲染时保留）。
LASER_LEN = 18.0

# (t, r/r0)：加力燃烧的焰形 —— 前段几乎不收，65% 处仍保持半宽，尾段才收到尖
PLUME_SECTIONS = ((0.00, 1.00), (0.16, 0.96), (0.34, 0.86), (0.52, 0.71),
                  (0.68, 0.50), (0.82, 0.30), (0.92, 0.135), (1.00, 0.0))


# ---------------------------------------------------------------- 回转体
def _cone(name, cy, cz, prof, seg=40, mat=None, col=None):
    """绕 X 轴旋转一条 (x, r) 剖面并封两端（尾焰锥体）"""
    bm = bmesh.new()
    cs = [(math.cos(TAU * i / seg), math.sin(TAU * i / seg)) for i in range(seg)]
    rings = []
    for (x, r) in prof:
        if r <= 1e-7:
            rings.append([bm.verts.new((x, cy, cz))])
        else:
            rings.append([bm.verts.new((x, cy + r * c, cz + r * s)) for (c, s) in cs])
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(seg):
                bm.faces.new((a[0], b[i], b[(i + 1) % seg]))
        elif len(b) == 1:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[0]))
        else:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit.obj_from_bm(name, bm, mat, col, smooth=True)


def _plume_prof(x_root, length, r0):
    """尾焰剖面：从喷口内侧 x_root 沿 -X 拉出 length，按 PLUME_SECTIONS 收束"""
    return [(x_root - length * t, r0 * f) for (t, f) in PLUME_SECTIONS]


def _flame_attr(ob, x_root, length):
    """写入自定义属性 flame_t（0=尖端, 1=喷口）—— 材质用它把亮度/透明度沿长度衰减"""
    me = ob.data
    ca = me.color_attributes.new(name="flame_t", type='FLOAT_COLOR', domain='POINT')
    for i, v in enumerate(me.vertices):
        t = (v.co.x - x_root) / (-length)
        t = min(1.0, max(0.0, t))
        # 根部略压，中段最亮，尖端收到 0：读起来像被气流扯开的火焰
        k = (0.55 + 0.75 * t) * (t ** 0.55)
        k = min(1.0, max(0.0, k))
        ca.data[i].color = (k, k, k, 1.0)
    me.update()


# ---------------------------------------------------------------- 材质
def _length_fade(mat, strength=None, alpha=None):
    """给火焰材质接上 flame_t：沿长度衰减自发光强度与不透明度（一次性，幂等）"""
    nt = mat.node_tree
    if nt.nodes.get("flameAttr") is not None:
        return mat
    mix = next((n for n in nt.nodes if n.type == 'MIX_SHADER'), None)
    emit = next((n for n in nt.nodes if n.type == 'EMISSION'), None)
    if mix is None or emit is None:
        return mat
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.name = "flameAttr"
    attr.attribute_name = "flame_t"
    attr.location = (-240, -420)

    if alpha is not None:
        a0 = nt.nodes.new('ShaderNodeMath'); a0.operation = 'MULTIPLY'
        a0.location = (-40, -300); a0.inputs[1].default_value = 0.18
        a1 = nt.nodes.new('ShaderNodeMath'); a1.operation = 'ADD'
        a1.location = (120, -300); a1.inputs[1].default_value = 0.82
        a2 = nt.nodes.new('ShaderNodeMath'); a2.operation = 'MULTIPLY'
        a2.location = (300, -300); a2.inputs[1].default_value = alpha
        nt.links.new(attr.outputs['Fac'], a0.inputs[0])
        nt.links.new(a0.outputs['Value'], a1.inputs[0])
        nt.links.new(a1.outputs['Value'], a2.inputs[0])
        nt.links.new(a2.outputs['Value'], mix.inputs['Fac'])

    if strength is not None:
        s0 = nt.nodes.new('ShaderNodeMath'); s0.operation = 'MULTIPLY'
        s0.location = (300, -520); s0.inputs[1].default_value = strength
        nt.links.new(attr.outputs['Fac'], s0.inputs[0])
        nt.links.new(s0.outputs['Value'], emit.inputs['Strength'])
    return mat


def _extra_mats(M):
    """外焰/中层用 mats._plume_material（噪声驱动的白热→橙红渐变，不是平涂发光）"""
    if 'fx_plume_outer' not in M:
        m = mats._plume_material("fx_plume_outer", (0.95, 0.42, 0.10), (0.42, 0.05, 0.02),
                                 strength=7.0, alpha=0.40, noise_scale=2.0, seed=7)
        M['fx_plume_outer'] = _length_fade(m, strength=7.0, alpha=0.40)
    if 'fx_plume_mid' not in M:
        m = mats._plume_material("fx_plume_mid", (1.00, 0.72, 0.32), (0.90, 0.22, 0.04),
                                 strength=11.0, alpha=0.62, noise_scale=2.8, seed=11)
        M['fx_plume_mid'] = _length_fade(m, strength=11.0, alpha=0.62)
    return M


# ---------------------------------------------------------------- 尾焰
def plume_geo(M, col):
    obs = []
    sfx = {"engine_port": "p", "engine_stbd": "s", "engine_ctr": "c"}
    for eid in S.ENGINE_IDS:
        y, z, r_body, xs, xe, ro, ri, exit_x, flen = S.ENGINES[eid]
        s = sfx[eid]
        layers = (
            ("outer", 0.96, 1.00, M['fx_plume_outer'], 40,
             "外焰（半透明）", "Outer Plume (translucent)"),
            ("mid", 0.66, 0.94, M['fx_plume_mid'], 34, "中层焰", "Mid Plume"),
            ("core", 0.32, 0.78, M['engine_core'], 28, "尾焰内芯", "Plume Core"),
        )
        for (tag, rf, lf, mat, seg, zh, en) in layers:
            r0 = ri * rf
            x_root = exit_x + 0.05
            length = flen * lf
            ob = _cone("fx_plume_%s_%s" % (s, tag), y, z,
                       _plume_prof(x_root, length, r0), seg=seg, mat=mat, col=col)
            if tag != "core":
                _flame_attr(ob, x_root, length)
            obs.append(kit.part(
                ob, "fx_plume_%s_%s" % (s, tag), "%s·%s" % (zh, eid), en, "detail",
                (-1, 0, 0), order=None,
                note="特效件（非结构）：根部中心 (%.2f, %.2f, %.2f) 半径 %.3f（%.2f×bell_r_in），"
                     "长 %.2f m，沿 -X 收束" % (exit_x, y, z, r0, rf, length)))
    return obs


# ---------------------------------------------------------------- 激光束
def laser_geo(M, col):
    t = S.TURRET_DORSAL
    ox, oy, oz = t['x'], t['y'], t['z'] + 0.55     # 与 build.ship_meta() 的炮口位置一致
    L = LASER_LEN
    obs = []
    for (tag, r, mat, zh, en) in (
            ("core", 0.028, M['laser'], "激光内芯", "Laser Beam Core"),
            ("glow", 0.100, M['laser_glow'], "激光外晕", "Laser Beam Glow")):
        ob = kit.cyl("fx_laser_%s" % tag, r, L, axis='X',
                     loc=(ox + L / 2.0, oy, oz), mat=mat, col=col, seg=24, bw=0.0, segs=1)
        obs.append(kit.part(
            ob, "fx_laser_%s" % tag, zh, en, "detail", (1, 0, 0),
            order=None,
            note="特效件（非结构）：从炮塔 (%.2f, %.2f, %.2f) 沿 +X 的 %.0f m 光束，半径 %.3f m"
                 % (ox, oy, oz, L, r)))
    return obs


def build(M, col):
    M = _extra_mats(M)
    obs = []
    obs += plume_geo(M, col)
    obs += laser_geo(M, col)
    obs = [o for o in obs if o is not None]
    print("FX parts=%d  (plume layers=%d, laser=%d)"
          % (len(obs), len(obs) - 2, 2))
    return obs
