# -*- coding: utf-8 -*-
"""参数化汽车（街景用）。真比例，不是"盒子 + 两块黑饼"。

几何思路：车身按**水平截面层**堆，玻璃舱用**棱台**（frustum）自然做出 A/C 柱倾角，
轮子单独做轮胎 + 轮辋 + 5 根辐条。整车 ≈ 700–900 面，远看近看都站得住。

局部坐标：车头朝 +X，原点在**车底中心**（z=0 落地），宽沿 Y。
"""
import math
from mathutils import Matrix
from .kit import GB, TAU

# ---------------------------------------------------------------- 原语
def _fr(gb, z0, z1, bot, top, mat):
    """棱台：bot/top = (x0, x1, y0, y1)。"""
    x0, x1, y0, y1 = bot
    tx0, tx1, ty0, ty1 = top
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (tx0, ty0, z1), (tx1, ty0, z1), (tx1, ty1, z1), (tx0, ty1, z1)]
    gb.quad(p[0], p[3], p[2], p[1], mat)      # 底
    gb.quad(p[4], p[5], p[6], p[7], mat)      # 顶
    gb.quad(p[0], p[1], p[5], p[4], mat)      # -Y 侧
    gb.quad(p[1], p[2], p[6], p[5], mat)      # +X 端
    gb.quad(p[2], p[3], p[7], p[6], mat)      # +Y 侧
    gb.quad(p[3], p[0], p[4], p[7], mat)      # -X 端


def _ring(gb, r0, r1, w, cx, cy, cz, mat, seg=10):
    """轮拱 / 装饰环：沿 XZ 平面的一圈薄环（轴向 Y）。"""
    for i in range(seg):
        a0 = TAU * i / seg
        a1 = TAU * (i + 1) / seg
        am = (a0 + a1) / 2
        rm = (r0 + r1) / 2
        rr = (r1 - r0) / 2
        L = math.hypot(rm * (a1 - a0), rr) * 1.15
        mm = (Matrix.Translation((cx + math.cos(am) * rm, cy,
                                  cz + math.sin(am) * rm)) @
              Matrix.Rotation(-am, 4, "Y"))
        with gb.frame(mm):
            gb.box((L, w, (r1 - r0)), (0, 0, 0), mat=mat)


def _wheel(gb, cx, cy, r=0.33, w=0.225, spokes=5):
    """轮胎 + 轮辋 + 辐条。"""
    # 轮胎
    gb.cyl(r, w, (cx, cy, r), axis="Y", seg=16, mat="M_Tyre")
    # 轮辋盘（两面各一片）
    for s in (-1, 1):
        gb.cyl(r * 0.60, 0.020, (cx, cy + s * (w / 2 + 0.008), r),
               axis="Y", seg=14, mat="M_Rim")
    # 辐条
    for i in range(spokes):
        a = TAU * i / spokes
        mm = (Matrix.Translation((cx, cy, r)) @ Matrix.Rotation(a, 4, "Y"))
        with gb.frame(mm):
            gb.box((r * 1.05, w * 0.92, 0.036), (0, 0, 0), mat="M_RimDark")
    # 中心盖
    gb.cyl(r * 0.16, w + 0.05, (cx, cy, r), axis="Y", seg=10, mat="M_Rim")


def _arch(gb, cx, cy, r, w, mat="M_Tyre"):
    """轮眉：贴在车身侧面、比轮胎大一圈的暗色块（不要画成浮在体外的弧线）。"""
    gb.cyl(r + 0.045, w, (cx, cy, r), axis="Y", seg=18, mat=mat)


# ---------------------------------------------------------------- 轿车
def sedan(gb, x, y, rot=0.0, z=0.0, paint="M_CarPaintWhite", tint="M_CarGlass"):
    """紧凑型三厢轿车：4.72 × 1.84 × 1.44 m，轴距 2.80。"""
    L, W = 4.72, 1.84
    hx, hy = L / 2, W / 2
    mm = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")
    with gb.frame(mm):
        # ---- 车身下部（两道棱台做出下裙内收 + 腰线外扩）
        _fr(gb, 0.17, 0.46,
            (-hx + 0.10, hx - 0.06, -hy + 0.13, hy - 0.13),
            (-hx + 0.02, hx - 0.02, -hy + 0.02, hy - 0.02), paint)
        _fr(gb, 0.46, 0.80,
            (-hx + 0.02, hx - 0.02, -hy + 0.02, hy - 0.02),
            (-hx + 0.09, hx - 0.16, -hy + 0.06, hy - 0.06), paint)
        # ---- 发动机罩（前段压低）
        _fr(gb, 0.80, 0.90,
            (hx - 1.36, hx - 0.16, -hy + 0.06, hy - 0.06),
            (hx - 1.44, hx - 0.20, -hy + 0.10, hy - 0.10), paint)
        # ---- 行李箱盖
        _fr(gb, 0.80, 0.88,
            (-hx + 0.09, -hx + 1.02, -hy + 0.06, hy - 0.06),
            (-hx + 0.13, -hx + 1.00, -hy + 0.09, hy - 0.09), paint)

        # ---- 玻璃舱（棱台下段 = 侧窗/风挡）
        gx0, gx1 = -hx + 1.02, hx - 1.44       # 座舱长度
        _fr(gb, 0.80, 1.30,
            (gx0, gx1, -hy + 0.06, hy - 0.06),
            (gx0 + 0.20, gx1 - 0.34, -hy + 0.13, hy - 0.13), tint)
        # ---- 车顶盖
        _fr(gb, 1.30, 1.42,
            (gx0 + 0.20, gx1 - 0.34, -hy + 0.13, hy - 0.13),
            (gx0 + 0.30, gx1 - 0.46, -hy + 0.19, hy - 0.19), paint)

        # ---- A / B / C 柱（车身色细柱，压在玻璃上）
        for sy in (-1, 1):
            yy = sy * (hy - 0.105)
            # A 柱（前）
            _fr(gb, 0.82, 1.30, (gx1 - 0.30, gx1 - 0.16, yy - 0.035, yy + 0.035),
                (gx1 - 0.44, gx1 - 0.32, yy - 0.030, yy + 0.030), paint)
            # C 柱（后）
            _fr(gb, 0.82, 1.30, (gx0 + 0.04, gx0 + 0.20, yy - 0.040, yy + 0.040),
                (gx0 + 0.18, gx0 + 0.30, yy - 0.034, yy + 0.034), paint)
            # B 柱
            bx = (gx0 + gx1) / 2 - 0.10
            gb.box((0.075, 0.030, 0.46), (bx, yy, 1.06), mat="M_GrilleBlack")

        # ---- 腰线镀铬
        for sy in (-1, 1):
            gb.box((L - 1.30, 0.020, 0.028),
                   (0.02, sy * (hy - 0.035), 0.815), mat="M_Chrome")

        # ---- 门缝
        for sy in (-1, 1):
            for dx in ((gx0 + gx1) / 2 - 0.10, gx0 + 0.16):
                gb.box((0.012, 0.014, 0.56), (dx, sy * (hy - 0.028), 0.50),
                       mat="M_GrilleBlack")
            gb.box((0.90, 0.014, 0.012), (-0.42, sy * (hy - 0.028), 0.70),
                   mat="M_GrilleBlack")

        # ---- 门把手
        for sy in (-1, 1):
            for dx in (0.10, -0.78):
                gb.box((0.16, 0.030, 0.045), (dx, sy * (hy - 0.030), 0.755),
                       mat="M_Chrome")

        # ---- 前脸：格栅 + 大灯 + 下唇
        gb.box((0.05, 1.06, 0.20), (hx - 0.045, 0, 0.55), mat="M_GrilleBlack")
        for i in range(5):
            gb.box((0.03, 1.00, 0.014), (hx - 0.018, 0, 0.47 + i * 0.042),
                   mat="M_Chrome")
        for sy in (-1, 1):
            gb.box((0.055, 0.40, 0.13), (hx - 0.040, sy * 0.62, 0.69),
                   mat="M_HeadLamp")
            gb.box((0.050, 0.30, 0.075), (hx - 0.055, sy * 0.40, 0.40),
                   mat="M_GrilleBlack")     # 雾灯槽
        gb.box((0.10, 1.50, 0.10), (hx - 0.055, 0, 0.27), mat="M_GrilleBlack")

        # ---- 尾部：尾灯 + 后保
        for sy in (-1, 1):
            gb.box((0.055, 0.46, 0.11), (-hx + 0.030, sy * 0.58, 0.70),
                   mat="M_TailLamp")
        gb.box((0.09, 1.44, 0.13), (-hx + 0.050, 0, 0.30), mat="M_GrilleBlack")

        # ---- 牌照
        gb.box((0.030, 0.44, 0.13), (hx - 0.020, 0, 0.355), mat="M_RoadLine")
        gb.box((0.030, 0.44, 0.13), (-hx + 0.020, 0, 0.60), mat="M_RoadLine")

        # ---- 后视镜
        for sy in (-1, 1):
            gb.box((0.075, 0.115, 0.085),
                   (gx1 - 0.10, sy * (hy - 0.02), 0.985), mat=paint)
            gb.box((0.045, 0.16, 0.045),
                   (gx1 - 0.09, sy * (hy - 0.09), 0.955), mat=paint)

        # ---- 排气
        gb.cyl(0.035, 0.10, (-hx + 0.02, -0.44, 0.20), axis="X", seg=8,
               mat="M_Chrome")

        # ---- 四轮 + 轮拱
        for wx in (hx - 0.95, -hx + 0.97):
            for sy in (-1, 1):
                wy = sy * (hy - 0.145)
                _wheel(gb, wx, wy, r=0.355, w=0.235)
                _arch(gb, wx, sy * (hy - 0.085), 0.355, 0.075)


# ---------------------------------------------------------------- SUV
def suv(gb, x, y, rot=0.0, z=0.0, paint="M_CarPaintInk", tint="M_CarGlassDeep"):
    """城市 SUV：4.65 × 1.92 × 1.66 m，坐姿高、轮大、车尾方。"""
    L, W = 4.65, 1.92
    hx, hy = L / 2, W / 2
    mm = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")
    with gb.frame(mm):
        _fr(gb, 0.30, 0.62,
            (-hx + 0.12, hx - 0.08, -hy + 0.14, hy - 0.14),
            (-hx + 0.02, hx - 0.02, -hy + 0.02, hy - 0.02), paint)
        _fr(gb, 0.62, 1.02,
            (-hx + 0.02, hx - 0.02, -hy + 0.02, hy - 0.02),
            (-hx + 0.04, hx - 0.10, -hy + 0.05, hy - 0.05), paint)
        # 舱（SUV 更方：A 柱更陡、车顶更长）
        gx0, gx1 = -hx + 0.30, hx - 1.30
        _fr(gb, 1.02, 1.53,
            (gx0, gx1, -hy + 0.05, hy - 0.05),
            (gx0 + 0.10, gx1 - 0.40, -hy + 0.10, hy - 0.10), tint)
        _fr(gb, 1.53, 1.66,
            (gx0 + 0.10, gx1 - 0.40, -hy + 0.10, hy - 0.10),
            (gx0 + 0.16, gx1 - 0.48, -hy + 0.15, hy - 0.15), paint)
        # 车顶行李架
        for sy in (-1, 1):
            gb.box((gx1 - gx0 - 0.62, 0.045, 0.045),
                   ((gx0 + gx1) / 2 - 0.14, sy * (hy - 0.155), 1.685),
                   mat="M_SteelDarker")
        # 柱
        for sy in (-1, 1):
            yy = sy * (hy - 0.085)
            _fr(gb, 1.04, 1.53, (gx1 - 0.36, gx1 - 0.22, yy - 0.035, yy + 0.035),
                (gx1 - 0.46, gx1 - 0.34, yy - 0.030, yy + 0.030), paint)
            _fr(gb, 1.04, 1.53, (gx0 + 0.02, gx0 + 0.16, yy - 0.040, yy + 0.040),
                (gx0 + 0.08, gx0 + 0.20, yy - 0.034, yy + 0.034), paint)
            bx = (gx0 + gx1) / 2 + 0.06
            gb.box((0.075, 0.030, 0.48), (bx, yy, 1.28), mat="M_GrilleBlack")
        # 前脸
        gb.box((0.05, 1.14, 0.24), (hx - 0.045, 0, 0.80), mat="M_GrilleBlack")
        for i in range(4):
            gb.box((0.03, 1.08, 0.016), (hx - 0.018, 0, 0.72 + i * 0.052),
                   mat="M_Chrome")
        for sy in (-1, 1):
            gb.box((0.055, 0.42, 0.15), (hx - 0.040, sy * 0.64, 0.90),
                   mat="M_HeadLamp")
        gb.box((0.10, 1.56, 0.14), (hx - 0.055, 0, 0.36), mat="M_GrilleBlack")
        # 尾灯（竖向）
        for sy in (-1, 1):
            gb.box((0.060, 0.13, 0.34), (-hx + 0.032, sy * 0.72, 0.94),
                   mat="M_TailLamp")
        gb.box((0.09, 1.50, 0.16), (-hx + 0.050, 0, 0.42), mat="M_GrilleBlack")
        # 牌照 + 后视镜 + 排气
        gb.box((0.030, 0.44, 0.13), (hx - 0.020, 0, 0.55), mat="M_RoadLine")
        gb.box((0.030, 0.44, 0.13), (-hx + 0.020, 0, 0.82), mat="M_RoadLine")
        for sy in (-1, 1):
            gb.box((0.080, 0.125, 0.095),
                   (gx1 - 0.06, sy * (hy - 0.02), 1.245), mat=paint)
        gb.cyl(0.040, 0.10, (-hx + 0.02, -0.46, 0.28), axis="X", seg=8,
               mat="M_Chrome")
        # 四轮（更大）
        for wx in (hx - 0.95, -hx + 0.95):
            for sy in (-1, 1):
                wy = sy * (hy - 0.150)
                _wheel(gb, wx, wy, r=0.395, w=0.250, spokes=5)
                _arch(gb, wx, sy * (hy - 0.090), 0.395, 0.080)


def parking(gb, x, y, rot=0.0, kind="sedan", paint=None):
    """便捷入口：kind = sedan / suv。"""
    if kind == "suv":
        suv(gb, x, y, rot=rot,
            paint=paint or "M_CarPaintInk")
    else:
        sedan(gb, x, y, rot=rot,
              paint=paint or "M_CarPaintWhite")
