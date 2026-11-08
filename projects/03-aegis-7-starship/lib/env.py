"""mk18/lib/env.py — 程序化影棚环境图（equirect），同时供 Blender 世界与 Three.js 使用

一张图定义所有高光形状：金属反射读的是它，而不是一堆直射灯。

"""

import bpy, numpy as np, os, math



HERE = os.path.dirname(os.path.abspath(__file__))

TEX = os.path.join(os.path.dirname(HERE), "tex")





def _softbox(u, v, cu, cv, su, sv, power=1.0, edge=0.35):

    """u,v,cu,cv 都是 0..1；返回高斯软边矩形强度"""

    du = np.abs(((u - cu + 0.5) % 1.0) - 0.5)

    dv = np.abs(v - cv)

    # 软边：smoothstep

    ku = np.clip((su - du) / (su * edge + 1e-6), 0, 1)

    kv = np.clip((sv - dv) / (sv * edge + 1e-6), 0, 1)

    w = (ku * ku * (3 - 2 * ku)) * (kv * kv * (3 - 2 * kv))

    return w * power





def build_env(w=2048, h=1024, path=None, seed=3):

    u = (np.arange(w) + 0.5) / w

    v = (np.arange(h) + 0.5) / h

    U, V = np.meshgrid(u, v)          # V: 0=顶, 1=底

    # 基础：天顶略亮、地面很暗

    base = 0.030 + 0.090 * np.clip(1.0 - V * 1.15, 0, 1) ** 1.5

    # 冷调

    img = np.stack([base * 0.95, base * 0.98, base * 1.05], -1)

    # 主柔光箱（左前上方，大面积）

    key = _softbox(U, V, 0.34, 0.34, 0.070, 0.070, power=16.0)

    # 冷侧光（右后）

    fill = _softbox(U, V, 0.78, 0.42, 0.090, 0.090, power=4.0)

    # 顶部条灯

    top = _softbox(U, V, 0.55, 0.10, 0.26, 0.022, power=9.0)

    # 轮廓条灯（正后方窄条，给金属边缘高光）

    rim = _softbox(U, V, 0.5, 0.38, 0.005, 0.32, power=12.0)

    # 地面反光板

    bounce = _softbox(U, V, 0.30, 0.86, 0.35, 0.10, power=0.55)

    # 暖色小补光

    warm = _softbox(U, V, 0.12, 0.55, 0.035, 0.06, power=2.0)
    # 环绕柔光带（模拟影棚四周白墙的一次反射）
    band = _softbox(U, V, 0.5, 0.62, 0.62, 0.075, power=0.55) + _softbox(U, V, 0.0, 0.30, 0.62, 0.06, power=0.35)



    img[:, :, 0] += key * 1.00 + fill * 0.86 + top * 1.00 + rim * 0.92 + bounce * 1.02 + warm * 1.15 + band * 1.0

    img[:, :, 1] += key * 0.97 + fill * 0.92 + top * 0.99 + rim * 0.96 + bounce * 0.98 + warm * 0.86 + band * 0.98

    img[:, :, 2] += key * 0.93 + fill * 1.00 + top * 0.96 + rim * 1.00 + bounce * 0.90 + warm * 0.62 + band * 0.96

    os.makedirs(TEX, exist_ok=True)

    hdr = np.maximum(img, 0).astype(np.float32)

    # LDR 编码：reinhard 压缩后转 sRGB，再手工写 PNG（不依赖 bpy 图像缓冲，绕开 foreach_set 丢数据）

    ldr = hdr / (1.0 + hdr * 0.42)

    ldr = np.clip(ldr, 0, 1) ** (1 / 2.2)

    # 上下翻转：equirect V=0 在顶部，PNG 第一行就是顶部 -> 不翻转

    rgb8 = (ldr * 255.0 + 0.5).astype(np.uint8)

    png = path or os.path.join(TEX, "studio_env.png")

    write_png(png, rgb8)

    # 给 bpy 一个可用的图像：从磁盘加载

    old = bpy.data.images.get("studio_env.png")

    if old:

        bpy.data.images.remove(old)

    im = bpy.data.images.load(png, check_existing=False)

    im.name = "studio_env.png"

    im.colorspace_settings.name = 'sRGB'

    print("ENV", png, "hdr_max %.2f" % float(hdr.max()), "mean %.3f" % float(hdr.mean()))

    return im, png





def write_png(path, rgb8):
    """最小 PNG 写入器（8bit RGB，无依赖）"""
    import zlib, struct
    h, w, _ = rgb8.shape
    zero = bytes(1)            # filter byte 0x00
    buf = bytearray()
    for y in range(h):
        buf += zero
        buf += rgb8[y].tobytes()

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(buf), 9)))
        f.write(chunk(b"IEND", b""))


def world_env(strength=1.15, bg_color=(0.012, 0.014, 0.017)):
    """世界：环境图负责照明与反射；相机直接看到的背景换成深色（Light Path → Is Camera Ray）"""
    sc = bpy.context.scene
    w = bpy.data.worlds.get("ENV") or bpy.data.worlds.new("ENV")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg_env = nt.nodes.new('ShaderNodeBackground')
    bg_env.inputs['Strength'].default_value = strength
    bg_dark = nt.nodes.new('ShaderNodeBackground')
    bg_dark.inputs['Color'].default_value = (*bg_color, 1.0)
    bg_dark.inputs['Strength'].default_value = 1.0
    tex = nt.nodes.new('ShaderNodeTexEnvironment')
    img = bpy.data.images.get("studio_env.png")
    if img is None:
        img = build_env()[0]
    tex.image = img
    nt.links.new(tex.outputs['Color'], bg_env.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    lp = nt.nodes.new('ShaderNodeLightPath')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg_env.outputs['Background'], mix.inputs[1])
    nt.links.new(bg_dark.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w
