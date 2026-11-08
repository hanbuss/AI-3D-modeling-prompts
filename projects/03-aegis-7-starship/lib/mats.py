"""starship/lib/mats.py — 全舰材质库（PBR，程序化贴图，glTF 口径 ORM）

要点（踩过的坑，别改回去）：
1. glTF 的 metallicRoughness 贴图 = R:AO / G:roughness / B:metalness。
   灰度图同时喂 G/B 会让金属度掉到 ~0.3，网页里马上变塑料灰 → 必须走 ORM + SeparateColor。
2. bpy 的 image.pixels.foreach_set 在 5.x 某些场景会把数据写成 0，所以贴图一律用自写 PNG 落盘再 load。
3. 飞船是 30 m 尺度的物件：UV 用世界盒式展开（1 单位 = 1 m），uv_scale 表示"每米几次平铺"。
"""
import bpy, numpy as np, os, math

TEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tex")
_cache = {}


# ---------------------------------------------------------------- noise
def _fbm(h, w, octaves=4, seed=0, base=4):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh = max(2, base * 2 ** o)
        g = rng.random((gh, gh)).astype(np.float32)
        yi = np.linspace(0, gh - 1, h, dtype=np.float32)
        xi = np.linspace(0, gh - 1, w, dtype=np.float32)
        y0 = np.floor(yi).astype(int); x0 = np.floor(xi).astype(int)
        y1 = np.minimum(y0 + 1, gh - 1); x1 = np.minimum(x0 + 1, gh - 1)
        fy = (yi - y0)[:, None]; fx = (xi - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
        a = g[np.ix_(y0, x0)]; b = g[np.ix_(y0, x1)]
        c = g[np.ix_(y1, x0)]; d = g[np.ix_(y1, x1)]
        acc += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= 0.5
    return acc / tot


def _normal_from_height(hmap, strength=1.0):
    dx = np.roll(hmap, -1, axis=1) - np.roll(hmap, 1, axis=1)
    dy = np.roll(hmap, -1, axis=0) - np.roll(hmap, 1, axis=0)
    nx, ny = -dx * strength, -dy * strength
    nz = np.ones_like(hmap)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / ln, ny / ln, nz / ln], -1)


def _save_image(name, arr, noncolor=True):
    import png as PNG
    rgb8 = (np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype("uint8")
    os.makedirs(TEX_DIR, exist_ok=True)
    path = os.path.join(TEX_DIR, name + ".png")
    PNG.write_png(path, rgb8)
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    img.pack()
    return img


def _norm_img(name, hm, strength):
    hm = (hm - hm.min()) / max(1e-6, hm.max() - hm.min())
    nrm = _normal_from_height(hm, strength)
    return _save_image(name, nrm * 0.5 + 0.5, noncolor=True)


# ---------------------------------------------------------------- textures
def tex_paint_normal(size=1024, seed=5):
    """涂装船壳微法线：细喷砂颗粒 + 少量刮痕（长条形划伤）"""
    if 'paint_normal' in _cache:
        return _cache['paint_normal']
    rng = np.random.default_rng(seed)
    f = _fbm(size, size, 5, seed, base=8)
    # 刮痕：随机长条
    h = np.zeros((size, size), np.float32)
    for _ in range(70):
        x = rng.integers(0, size); y = rng.integers(0, size)
        L = rng.integers(20, 160); ang = rng.uniform(0, math.pi)
        for t in range(L):
            px = int(x + math.cos(ang) * t) % size
            py = int(y + math.sin(ang) * t) % size
            h[py, px] -= 0.35
    h = h * 0.5 + f * 0.5 + _fbm(size, size, 3, seed + 7, base=48) * 0.28
    img = _norm_img("paint_normal", h, size * 0.0035)
    _cache['paint_normal'] = img
    return img


def tex_paint_albedo(size=1024, seed=31, lo=0.84, hi=1.04, name="paint_albedo"):
    """涂装底色斑驳（大块补漆/积灰/流痕）：与 baseColor 相乘，sRGB。
    没有这张图，漆面在 evny 下就是一坨纯色 —— 显脏才是真实感。"""
    if name in _cache:
        return _cache[name]
    f = _fbm(size, size, 6, seed, base=22)
    g = _fbm(size, size, 5, seed + 5, base=64)
    # 竖向流痕：把噪声沿 V 拉长
    streak = _fbm(size // 8, size, 3, seed + 9, base=8)
    yi = np.linspace(0, streak.shape[0] - 1, size)
    y0 = np.floor(yi).astype(int); y1 = np.minimum(y0 + 1, streak.shape[0] - 1)
    fy = (yi - y0)[:, None]; fy = fy * fy * (3 - 2 * fy)
    streak = streak[y0] * (1 - fy) + streak[y1] * fy
    v = 0.55 * f + 0.25 * g + 0.20 * streak
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    v = lo + v * (hi - lo)
    arr = np.stack([v, v * 0.995, v * 0.985], -1)
    img = _save_image(name, arr, noncolor=False)
    _cache[name] = img
    return img


def tex_paint_orm(size=1024, seed=9, rough_lo=0.30, rough_hi=0.66, metal=0.10, name="orm_paint"):
    """涂装板的 ORM：粗糙度有斑驳（油渍/补漆），金属度低（漆面绝缘）"""
    if name in _cache:
        return _cache[name]
    f = _fbm(size, size, 5, seed, base=6)
    g = _fbm(size, size, 4, seed + 3, base=20)
    v = 0.65 * f + 0.35 * g
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    rough = rough_lo + v ** 1.6 * (rough_hi - rough_lo)
    # 少量磨损处露出金属（B 通道局部抬高）
    m = np.full((size, size), metal, np.float32)
    wear = np.clip((v - 0.78) * 4.0, 0, 1) * 0.55
    m = np.clip(m + wear, 0, 1)
    arr = np.stack([np.ones((size, size), np.float32), rough, m], -1)
    img = _save_image(name, arr, noncolor=True)
    _cache[name] = img
    return img


def tex_metal_normal(size=1024, seed=13):
    if 'metal_normal' in _cache:
        return _cache['metal_normal']
    f = _fbm(size, size, 5, seed, base=10)
    st = _fbm(size, size, 3, seed + 1, base=120)
    img = _norm_img("metal_normal", f * 0.7 + st * 0.3, size * 0.0028)
    _cache['metal_normal'] = img
    return img


def tex_orm_metal(size=1024, rough_lo=0.18, rough_hi=0.38, metal=1.0, seed=17, name="orm_metal_ship"):
    if name in _cache:
        return _cache[name]
    f = _fbm(size, size, 5, seed, base=12)
    v = (f - f.min()) / max(1e-6, f.max() - f.min())
    rough = rough_lo + v * (rough_hi - rough_lo)
    arr = np.stack([np.ones((size, size), np.float32), rough,
                    np.full((size, size), metal, np.float32)], -1)
    img = _save_image(name, arr, noncolor=True)
    _cache[name] = img
    return img


def tex_heat_normal(size=512, seed=23):
    """喷口/热区：高温氧化造成的鳞片状纹理"""
    if 'heat_normal' in _cache:
        return _cache['heat_normal']
    rng = np.random.default_rng(seed)
    h = _fbm(size, size, 5, seed, base=9)
    for _ in range(260):
        cx, cy = rng.integers(0, size, 2)
        r = int(rng.integers(4, 16))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d2 = dx * dx + dy * dy
                if d2 <= r * r:
                    h[(cy + dy) % size, (cx + dx) % size] += (1 - d2 / (r * r)) * 0.5
    img = _norm_img("heat_normal", h, size * 0.004)
    _cache['heat_normal'] = img
    return img


def tex_hull_ao(size=1024, seed=29):
    """假 AO / 接缝积灰：用于 R 通道与基础色混合（不做真烘焙，靠 UV 尺度控制观感）"""
    if 'hull_ao' in _cache:
        return _cache['hull_ao']
    f = _fbm(size, size, 6, seed, base=5)
    v = (f - f.min()) / max(1e-6, f.max() - f.min())
    v = np.clip(0.55 + (v - 0.5) * 0.9, 0, 1)
    arr = np.stack([v, v, v], -1)
    img = _save_image("hull_ao", arr, noncolor=True)
    _cache['hull_ao'] = img
    return img


# ---------------------------------------------------------------- 船壳专用：带板缝/铆钉的成套贴图
def _seam_mask(size=1024, cells=2, w_frac=0.006, seed=3, rivets=True):
    """板缝遮罩：1=板面，0=缝。cells×cells 网格 + 轻微抖动，外加铆钉点。"""
    rng = np.random.default_rng(seed)
    m = np.ones((size, size), np.float32)
    # 每条缝的位置抖动（板不是完美一样大）
    xs = [0.0] + [i / cells + rng.uniform(-0.02, 0.02) / cells for i in range(1, cells)] + [1.0]
    ys = [0.0] + [i / cells + rng.uniform(-0.02, 0.02) / cells for i in range(1, cells)] + [1.0]
    lw = max(1, int(size * w_frac / cells))

    def draw_line(pos, vertical):
        jitter = rng.uniform(-0.0015, 0.0015) * size
        p = int(pos * size + jitter)
        for k in range(-lw, lw + 1):
            q = (p + k) % size
            fade = 1.0 - abs(k) / (lw + 1.0)
            if vertical:
                sl = m[:, q]
                m[:, q] = np.minimum(sl, 1.0 - fade * 0.95)
            else:
                sl = m[q, :]
                m[q, :] = np.minimum(sl, 1.0 - fade * 0.95)

    for x in xs:
        draw_line(x % 1.0, True)
    for y in ys:
        draw_line(y % 1.0, False)
    if rivets:
        # 沿缝两侧的铆钉点
        r = max(1, int(size * 0.0016))
        for x in xs:
            p = int(x * size)
            for ry in range(0, size, max(8, size // 60)):
                for k in range(-r, r + 1):
                    cy = (p + 5 + k) % size
                    cx = (ry + int(abs(k) * 0.0)) % size
                    m[cy, cx] = min(m[cy, cx], 0.55)
    return m


def tex_hull_set(size=512, cells=2, seed=7):
    """船壳一整套：albedo（斑驳 + 板缝 + 铆钉）/ normal（缝边倒角）/ orm（缝里更粗糙更脏）"""
    """兼容旧调用：返回 (albedo, normal, orm)"""
    if 'hull_set' in _cache:
        return _cache['hull_set']
    seam = _seam_mask(size, cells, seed=seed)
    # --- albedo
    f = _fbm(size, size, 6, seed + 11, base=22)
    g = _fbm(size, size, 5, seed + 17, base=70)
    v = 0.6 * f + 0.4 * g
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    alb = 0.86 + v * 0.16
    alb = alb * (0.55 + 0.45 * seam)          # 缝里压暗
    alb = np.clip(alb, 0, 1.2)
    arr = np.stack([alb, alb * 0.995, alb * 0.985], -1)
    alb_img = _save_image("hull_albedo", np.clip(arr, 0, 1), noncolor=False)
    # --- normal：缝两侧各一道缓坡
    hm = (1.0 - seam) * 0.55 + _fbm(size, size, 5, seed + 23, base=40) * 0.32
    hm = (hm - hm.min()) / max(1e-6, hm.max() - hm.min())
    nrm = _normal_from_height(hm, size * 0.0042)
    nrm_img = _save_image("hull_normal", nrm * 0.5 + 0.5, noncolor=True)
    # --- orm：缝里粗糙度低一点（积灰）+ 局部露出金属
    rough = 0.34 + (1.0 - seam) * 0.20 + v * 0.14
    metal = 0.10 + (1.0 - seam) * 0.16
    ao = 0.72 + 0.28 * seam
    arr = np.stack([np.clip(ao, 0, 1), np.clip(rough, 0, 1), np.clip(metal, 0, 1)], -1)
    orm_img = _save_image("hull_orm", arr, noncolor=True)
    out = (alb_img, nrm_img, orm_img)
    _cache['hull_set'] = out
    return out


def _enc_srgb(lin):
    return np.clip(lin, 0, 1) ** (1.0 / 2.2)


def tex_hull_albedo(name, tint, size=512, cells=2, seed=7, mottle=0.14, seam_dark=0.55):
    """船壳底色：tint（线性色）× 斑驳 × 板缝压暗，最后 sRGB 编码存图。
    每个涂装色一张（glTF 里 baseColorFactor 只能是白色，靠贴图带颜色）。"""
    if name in _cache:
        return _cache[name]
    seam = _seam_mask(size, cells, seed=seed)
    f = _fbm(size, size, 6, seed + 11, base=14)
    g = _fbm(size, size, 5, seed + 17, base=40)
    v = 0.6 * f + 0.4 * g
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    m = (1.0 - mottle / 2) + v * mottle
    m = m * (seam_dark + (1.0 - seam_dark) * seam)
    lin = np.stack([m * tint[0], m * tint[1], m * tint[2]], -1)
    arr = _enc_srgb(lin)
    img = _save_image(name, arr, noncolor=False)
    _cache[name] = img
    return img


# ---------------------------------------------------------------- material factory
def _principled(name, base, metallic, rough, normal=None, orm=None, spec=0.5, nrm_str=0.35,
                alpha=1.0, transmission=0.0, emission=None, coat=0.0, ior=1.45,
                uv_scale=0.5, clearcoat_rough=0.1, base_map=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'DITHERED'
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (260, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*base, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['IOR'].default_value = ior
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = spec
    if alpha < 1.0:
        bsdf.inputs['Alpha'].default_value = alpha
    if transmission > 0:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    if coat > 0:
        bsdf.inputs['Coat Weight'].default_value = coat
        if 'Coat Roughness' in bsdf.inputs:
            bsdf.inputs['Coat Roughness'].default_value = clearcoat_rough
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission[:3], 1.0)
        bsdf.inputs['Emission Strength'].default_value = emission[3]

    def texnode(img, y):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = img
        t.location = (-360, y)
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.location = (-560, y)
        mp.inputs['Scale'].default_value = (uv_scale, uv_scale, uv_scale)
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.location = (-740, y)
        uvn.uv_map = "UVMap"
        nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector'])
        return t

    if base_map:
        # 直接把贴图接到 Base Color：glTF 导出器只认这种"直连"，Mix/Multiply 会被丢掉，
        # 结果就是网页里所有涂装变成一坨纯色（踩过一次，别再改回去）
        t = texnode(base_map, 240)
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    if normal:
        t = texnode(normal, -260)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.location = (40, -260)
        nm.inputs['Strength'].default_value = nrm_str
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    if orm:
        t = texnode(orm, -560)
        sepc = nt.nodes.new('ShaderNodeSeparateColor')
        sepc.location = (-140, -560)
        nt.links.new(t.outputs['Color'], sepc.inputs['Color'])
        nt.links.new(sepc.outputs['Green'], bsdf.inputs['Roughness'])
        nt.links.new(sepc.outputs['Blue'], bsdf.inputs['Metallic'])
    return m


def _plume_material(name, c_hot, c_cool, strength=18.0, alpha=0.55, noise_scale=2.6, seed=3):
    """尾焰材质：噪声驱动的白热→橙红渐变 + 半透明。
    平涂的自发光锥体看起来就是"一根奶油筒"，必须加噪声与渐变才像火。"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'DITHERED'
    m.blend_method = 'BLEND'
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.location = (300, 0)
    emit.inputs['Strength'].default_value = strength
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.location = (80, 0)
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (*c_cool, 1.0)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (*c_hot, 1.0)
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.location = (-260, 0)
    tex.inputs['Scale'].default_value = noise_scale
    tex.inputs['Detail'].default_value = 6.0
    tex.inputs['Roughness'].default_value = 0.62
    nt.links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], emit.inputs['Color'])
    transp = nt.nodes.new('ShaderNodeBsdfTransparent')
    transp.location = (300, -180)
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.location = (520, 0)
    mix.inputs['Fac'].default_value = alpha
    nt.links.new(transp.outputs['BSDF'], mix.inputs[1])
    nt.links.new(emit.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return m


def M():
    """舰体/舰载系统全套材质，键名到处在用，别随手改名"""
    d = {}
    NA = tex_paint_normal()
    ALB = tex_paint_albedo()
    ORM_PAINT = tex_paint_orm()
    ORM_ML = tex_orm_metal()
    NM = tex_metal_normal()
    HEAT = tex_heat_normal()

    # ---- 船壳涂装（主色：暖灰白，漆面绝缘 > 只给 0.1 金属度，靠清漆出光泽）
    HN, HO = tex_hull_normal(), tex_hull_orm()
    d['hull'] = _principled("S_Hull", (0.112, 0.120, 0.136), 0.14, 0.50,
                            normal=HN, orm=HO, spec=0.40, nrm_str=0.55,
                            coat=0.16, uv_scale=0.38,
                            base_map=tex_hull_albedo("hull_albedo", (0.112, 0.120, 0.136), seed=7))
    # 次色：深灰蓝装甲板
    d['hull_dark'] = _principled("S_Hull_Dark", (0.030, 0.034, 0.043), 0.22, 0.46,
                                 normal=HN, orm=HO, spec=0.42, nrm_str=0.52,
                                 coat=0.20, uv_scale=0.36,
                                 base_map=tex_hull_albedo("hull_dark_albedo", (0.030, 0.034, 0.043), seed=13, mottle=0.10))
    # 结构加强件 / 梁架：裸金属
    d['frame'] = _principled("S_Frame", (0.245, 0.250, 0.262), 1.0, 0.34,
                             normal=NM, orm=ORM_ML, spec=0.55, nrm_str=0.22, uv_scale=1.4)
    # 机加工铝（进气口内壁、桁条）
    d['alu'] = _principled("S_Alu", (0.520, 0.528, 0.540), 1.0, 0.26,
                           normal=NM, orm=ORM_ML, spec=0.6, nrm_str=0.18, uv_scale=2.2)
    # 深色枪金属（炮塔、机炮、挂架）
    d['gunmetal'] = _principled("S_Gunmetal", (0.072, 0.074, 0.080), 1.0, 0.30,
                                normal=NM, orm=ORM_ML, spec=0.55, nrm_str=0.20, uv_scale=1.8)
    # 黑阳极氧化（喷口环、光学罩）
    d['black'] = _principled("S_Black", (0.016, 0.017, 0.019), 0.85, 0.24,
                             normal=NM, orm=ORM_ML, spec=0.5, nrm_str=0.16, uv_scale=2.6)
    # 热区钢（喷口内壁：氧化色 + 高粗糙）
    d['heat_steel'] = _principled("S_HeatSteel", (0.150, 0.140, 0.140), 1.0, 0.38,
                                  normal=HEAT, orm=ORM_ML, spec=0.5, nrm_str=0.42, uv_scale=1.6)
    # 陶瓷隔热瓦（喷口外侧、腹部）
    d['ceramic'] = _principled("S_Ceramic", (0.030, 0.030, 0.032), 0.0, 0.68,
                               normal=NA, nrm_str=0.5, spec=0.25, uv_scale=2.0)
    # 金色多层隔热膜 MLI（老式航天器质感，局部小块用）
    d['foil'] = _principled("S_Foil", (0.760, 0.545, 0.180), 1.0, 0.28,
                            normal=NM, orm=ORM_ML, spec=0.65, nrm_str=0.55, uv_scale=3.0)
    # 座舱玻璃（蓝绿反光，透射 + 清漆）
    d['canopy'] = _principled("S_Canopy", (0.075, 0.115, 0.130), 0.0, 0.04,
                              alpha=0.30, transmission=0.86, spec=1.0, ior=1.52,
                              coat=1.0, clearcoat_rough=0.02)
    # 座舱内衬（哑光深色）
    d['interior'] = _principled("S_Interior", (0.028, 0.029, 0.032), 0.25, 0.62,
                                normal=NA, nrm_str=0.3, spec=0.3, uv_scale=2.4)
    # 面板缝/黑边
    d['seam'] = _principled("S_Seam", (0.008, 0.008, 0.010), 0.6, 0.52)
    # 红色警示涂装
    d['accent'] = _principled("S_Accent", (0.235, 0.030, 0.020), 0.18, 0.42,
                              normal=HN, orm=HO, spec=0.55, nrm_str=0.45,
                              coat=0.38, uv_scale=0.42,
                              base_map=tex_hull_albedo("accent_albedo", (0.235, 0.030, 0.020), seed=19))
    # 橙黄腰线
    d['stripe'] = _principled("S_Stripe", (0.560, 0.240, 0.028), 0.18, 0.42,
                              normal=HN, orm=HO, spec=0.55, nrm_str=0.45,
                              coat=0.38, uv_scale=0.42,
                              base_map=tex_hull_albedo("stripe_albedo", (0.560, 0.240, 0.028), seed=23))
    # 白色编号/文字
    d['decal'] = _principled("S_Decal", (0.700, 0.700, 0.690), 0.0, 0.42,
                             normal=NA, nrm_str=0.2, uv_scale=1.2)
    d['decal_dark'] = _principled("S_Decal_Dark", (0.020, 0.022, 0.026), 0.2, 0.45)
    # 发光：冷白灯带
    d['led'] = _principled("S_LED", (0.85, 0.94, 1.0), 0.0, 0.25,
                           emission=(0.72, 0.90, 1.0, 9.0))
    # 发光：警示红 / 航行绿
    d['led_red'] = _principled("S_LED_Red", (1.0, 0.10, 0.06), 0.0, 0.30,
                               emission=(1.0, 0.09, 0.05, 12.0))
    d['led_green'] = _principled("S_LED_Green", (0.15, 1.0, 0.35), 0.0, 0.30,
                                 emission=(0.12, 1.0, 0.30, 12.0))
    d['led_amber'] = _principled("S_LED_Amber", (1.0, 0.55, 0.10), 0.0, 0.30,
                                 emission=(1.0, 0.48, 0.06, 10.0))
    # 引擎：燃烧室内部辉光（强，用于尾焰内芯）
    d['engine_core'] = _plume_material("S_EngineCore", (1.0, 0.93, 0.80), (1.0, 0.34, 0.05),
                                       strength=26.0, alpha=0.92, noise_scale=3.4, seed=3)
    d['engine_ring'] = _plume_material("S_EngineRing", (1.0, 0.72, 0.42), (0.85, 0.20, 0.05),
                                       strength=14.0, alpha=0.52, noise_scale=2.4, seed=7)
    # 激光：青色发光晶体/透镜
    d['laser'] = _principled("S_Laser", (0.10, 0.75, 1.0), 0.0, 0.15,
                             emission=(0.10, 0.72, 1.0, 30.0))
    d['laser_glow'] = _plume_material("S_LaserGlow", (0.55, 0.95, 1.0), (0.10, 0.45, 1.0),
                                      strength=10.0, alpha=0.34, noise_scale=1.4, seed=11)
    # 橡胶密封条
    d['rubber'] = _principled("S_Rubber", (0.014, 0.014, 0.015), 0.0, 0.88,
                              normal=NA, nrm_str=0.45, spec=0.2, uv_scale=3.0)
    # 散热器面（暗金属、高粗糙，读起来像辐射板）
    d['radiator'] = _principled("S_Radiator", (0.115, 0.120, 0.130), 1.0, 0.52,
                                normal=NM, orm=ORM_ML, spec=0.4, nrm_str=0.35, uv_scale=1.2)
    # 光学镜头（蓝色镀膜）
    d['lens'] = _principled("S_Lens", (0.020, 0.075, 0.135), 0.0, 0.06,
                            alpha=0.75, transmission=0.7, spec=1.0, ior=1.62,
                            emission=(0.02, 0.10, 0.18, 1.2))
    return d


def assign_all_uv(objs):
    from kit import uv_box
    for o in objs:
        if o.type == 'MESH':
            uv_box(o, 1.0)


def tex_hull_normal(size=512, cells=2, seed=7):
    if 'hull_normal' in _cache:
        return _cache['hull_normal']
    seam = _seam_mask(size, cells, seed=seed)
    hm = (1.0 - seam) * 0.55 + _fbm(size, size, 5, seed + 23, base=40) * 0.32
    hm = (hm - hm.min()) / max(1e-6, hm.max() - hm.min())
    nrm = _normal_from_height(hm, size * 0.0042)
    img = _save_image("hull_normal", nrm * 0.5 + 0.5, noncolor=True)
    _cache['hull_normal'] = img
    return img


def tex_hull_orm(size=512, cells=2, seed=7):
    if 'hull_orm' in _cache:
        return _cache['hull_orm']
    seam = _seam_mask(size, cells, seed=seed)
    v = _fbm(size, size, 5, seed + 31, base=26)
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    rough = 0.30 + (1.0 - seam) * 0.22 + v * 0.16
    metal = 0.10 + (1.0 - seam) * 0.14
    ao = 0.70 + 0.30 * seam
    arr = np.stack([np.clip(ao, 0, 1), np.clip(rough, 0, 1), np.clip(metal, 0, 1)], -1)
    img = _save_image("hull_orm", arr, noncolor=True)
    _cache['hull_orm'] = img
    return img
