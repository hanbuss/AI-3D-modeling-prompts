# -*- coding: utf-8 -*-
"""南院（小院）—— 铺装 / 柚木平台 / 岛台 / 沙发组 / 格栅亭 / 水幕 / 枯山水 /
西草坪 / 围墙院门 / 灯具 / 街景。

坐标真源：LAYOUT.md §5（11 要素）。全部几何在本文件内，写 lib/court.py 一层。
z 基准：院内地坪 0.00；铺装面 0.02；平台面 0.30；砂床面 0.14。
"""
import math
import random

from mathutils import Matrix, Vector

from .kit import GB, TAU, lerp
from . import nature, assets, cars

# ---------------------------------------------------------------- 关键标高
Z_PAVE = 0.02      # 铺装面
Z_JOINT = 0.006    # 板缝
Z_DECK = 0.30      # 柚木平台面
Z_BED = 0.14       # 砂床 / 种植池土面
Z_WALL = 2.10      # 院墙高

# 铺装分格
PITCH = 0.80
TH_PAVE = 0.09

# 围合范围
XW, XE = -9.00, 9.00      # 院墙内皮
YS = -14.00               # 南院墙内皮
YN = -1.50                # 建筑南立面


# ================================================================ 小工具

# ---------------------------------------------------------------- 真模型种植
def _plant(ctx, name, tag, x, y, h=None, rot=None, z=None, max_w=None):
    """往 COURT 层放一份 PolyHaven 真三维植物（实例共享 mesh，GLB 只写一份几何）。"""
    from . import assets2
    return assets2.instance(ctx, "COURT", name, tag, x, y,
                            z=(Z_BED if z is None else z), height=h, rot=rot,
                            max_w=max_w)


def _b(gb, x0, x1, y0, y1, z0, z1, mat, smooth=False):
    gb.boxb(((x0, x1), (y0, y1), (z0, z1)), mat=mat, smooth=smooth)


def _frame(x, y, z=0.0, yaw=0.0):
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, "Z")


def _slabfield(gb, x0, x1, y0, y1, rng, mat_a="M_PaveSand", mat_b="M_PaveGrey",
               dark=0.03, top=Z_PAVE, th=TH_PAVE, pitch=PITCH):
    """大板铺装：每块单独成盒，板缝是真几何（少切 6 mm）。"""
    nx = max(1, int(round((x1 - x0) / pitch)))
    ny = max(1, int(round((y1 - y0) / pitch)))
    dx = (x1 - x0) / nx
    dy = (y1 - y0) / ny
    for i in range(nx):
        for j in range(ny):
            ax = x0 + i * dx
            ay = y0 + j * dy
            mat = mat_b if rng.random() < dark else mat_a
            _b(gb, ax, ax + dx - Z_JOINT, ay, ay + dy - Z_JOINT,
               top - th, top, mat)


def _band(gb, x0, x1, y0, y1, mat="M_GraniteEdge", top=Z_PAVE + 0.004, th=0.10):
    _b(gb, x0, x1, y0, y1, top - th, top, mat)


def _arc_ridge(gb, cx, cy, r, w, z, a0, a1, seg, mat, clip):
    """把一条耙纹做成环状凸起的窄条（quad 带）。"""
    ins, outs = [], []
    for k in range(seg + 1):
        a = a0 + (a1 - a0) * k / seg
        ca, sa = math.cos(a), math.sin(a)
        ins.append((cx + ca * (r - w * 0.5), cy + sa * (r - w * 0.5), z))
        outs.append((cx + ca * (r + w * 0.5), cy + sa * (r + w * 0.5), z))
    for k in range(seg):
        p0, p1 = ins[k], outs[k]
        p2, p3 = outs[k + 1], ins[k + 1]
        if clip and not (clip(p0) and clip(p1) and clip(p2) and clip(p3)):
            continue
        gb.quad(p0, p1, p2, p3, mat=mat)


# ================================================================ 1. 铺装
def _paving(gb, rng):
    """全场大板 + 黑花岗岩镶边 + 入户主轴。"""
    # ---- 入户主轴 X −1.80…1.80（略深的水泥灰砂岩）
    _slabfield(gb, -1.80, 1.80, -14.00, -1.50, rng,
               mat_a="M_PaveSand", mat_b="M_PaveGrey", dark=0.05)
    for y in (-12.60, -11.00, -9.40, -7.80, -6.20, -4.60, -3.00):
        _band(gb, -1.80, 1.80, y - 0.05, y + 0.05, top=Z_PAVE + 0.006, th=0.08)
    # 主轴两侧花岗岩镶边
    _band(gb, -1.92, -1.80, -14.00, -1.50)
    _band(gb, 1.80, 1.92, -14.00, -1.50)

    # ---- 平台与主轴之间的窄铺装带
    _slabfield(gb, -2.20, -1.92, -14.00, -1.50, rng, dark=0.04)

    # ---- 东侧大场地（亭子、水幕所在）
    _slabfield(gb, 1.92, 8.40, -13.40, -2.20, rng, dark=0.03)

    # ---- 亭子四周花岗岩压边
    for (a, b, c, d) in ((2.48, 8.52, -8.72, -8.60), (2.48, 8.52, -3.80, -3.68),
                         (2.48, 2.60, -8.72, -3.68), (8.40, 8.52, -8.72, -3.68)):
        _band(gb, a, b, c, d)

    # ---- 平台东 / 南缘压边
    _band(gb, -2.32, -2.20, -9.00, -2.20)
    _band(gb, -8.40, -2.32, -9.12, -9.00)
    # ---- 草坪四周压边
    _band(gb, -2.32, -2.20, -13.40, -9.12)
    _band(gb, -8.40, -2.20, -13.52, -13.40)
    _band(gb, -8.52, -8.40, -13.40, -9.00)

    # ---- 砂床外围（东侧）压边
    _band(gb, 1.92, 2.00, -13.40, -9.40)
    _band(gb, 7.88, 8.40, -13.40, -9.40, mat="M_GraniteEdge")

    # ---- 南墙根排水沟（一条深色石槽，增加地面层次）
    _b(gb, -8.40, -2.20, -13.42, -13.30, Z_PAVE - 0.06, Z_PAVE + 0.001, "M_GraniteEdge")


# ================================================================ 2. 柚木平台
def _deck(gb, rng):
    """板宽 0.14 / 缝 8 mm / 板长错缝 / 边缘暗藏灯带 / 3 级踏步。"""
    x0, x1 = -8.40, -2.20
    y0, y1 = -9.00, -2.20
    th = 0.045
    # 缝底（暗色），整片铺一层，板缝就有深度
    _b(gb, x0, x1, y0, y1, Z_DECK - 0.075, Z_DECK - 0.048, "M_DeckTeakGap")
    pitch = 0.188
    n = int((y1 - y0) / pitch)
    for j in range(n):
        ay = y0 + j * pitch
        by = ay + 0.180
        if rng.random() < 0.18:
            # 错缝：一条板切成两段
            jx = lerp(x0 + 0.9, x1 - 0.9, rng.random())
            _b(gb, x0, jx - 0.003, ay, by, Z_DECK - th, Z_DECK, "M_DeckTeak")
            _b(gb, jx + 0.003, x1, ay, by, Z_DECK - th, Z_DECK, "M_DeckTeak")
        else:
            _b(gb, x0, x1, ay, by, Z_DECK - th, Z_DECK, "M_DeckTeak")
    # 周边收边压条
    for (a, b, c, d) in ((x0 - 0.06, x0, y0, y1), (x1, x1 + 0.06, y0, y1),
                         (x0 - 0.06, x1 + 0.06, y1, y1 + 0.06)):
        _b(gb, a, b, c, d, Z_DECK - 0.055, Z_DECK + 0.008, "M_SlatTeakDark")
    # 台口立面（深色）+ 暗藏灯带
    _b(gb, x1, x1 + 0.05, y0, y1, 0.06, Z_DECK - 0.055, "M_Fascia")
    _b(gb, x0, x1 + 0.05, y0 - 0.05, y0, 0.06, Z_DECK - 0.055, "M_Fascia")
    _b(gb, x1 + 0.005, x1 + 0.035, y0 + 0.10, y1 - 0.10, 0.075, 0.105, "M_StepLight")
    _b(gb, x0 + 0.10, x1 - 0.10, y0 - 0.045, y0 - 0.015, 0.075, 0.105, "M_StepLight")
    # 结构柱脚
    for cx in (x0 + 0.35, x1 - 0.35):
        for cy in (y0 + 0.35, y1 - 0.35):
            _b(gb, cx - 0.06, cx + 0.06, cy - 0.06, cy + 0.06, 0.0, 0.06, "M_Concrete")

    # ---- 3 级踏步（下到草坪 / 铺装），踢面藏灯
    sx0, sx1 = -4.70, -2.70
    for k, (ty, tz) in enumerate(((-9.00, 0.225), (-9.34, 0.150), (-9.68, 0.075))):
        fy = ty - 0.34
        _b(gb, sx0, sx1, fy, ty, 0.02, tz, "M_PaveGrey")
        _b(gb, sx0, sx1, fy - 0.06, fy, 0.02, tz - 0.03, "M_GraniteEdge")
        _b(gb, sx0 + 0.06, sx1 - 0.06, fy - 0.035, fy - 0.008,
           tz - 0.075, tz - 0.048, "M_StepLight")


# ================================================================ 3. 岛台
def _kitchen(gb):
    """户外厨房：混凝土柜体 + 白大理石台面（外挑）+ 水槽 + 烤炉盖 + 3 凳 + 龙头。"""
    x0, x1 = -8.28, -7.38
    y0, y1 = -7.72, -5.32
    zt = 0.30 + 0.92
    # 柜体（内退 0.04，台面外挑后形成阴影线）
    _b(gb, x0 + 0.04, x1 - 0.04, y0 + 0.04, y1 - 0.04, Z_DECK + 0.10, zt - 0.09,
       "M_ConcretePot")
    # 柜门分缝
    for y in (y0 + 0.60, y0 + 1.20, y0 + 1.80):
        _b(gb, x0 + 0.06, x1 - 0.06, y - 0.006, y + 0.006, Z_DECK + 0.18, zt - 0.15,
           "M_SteelDark")
    # 踢脚内凹（深色）+ 台面下暗影缝
    _b(gb, x0 + 0.14, x1 - 0.16, y0 + 0.12, y1 - 0.12, Z_DECK, Z_DECK + 0.10,
       "M_SteelDarker")
    _b(gb, x0, x1, y0, y1, zt - 0.09, zt - 0.02, "M_SteelDarker")
    # 台面（4 边外挑 0.07，厚 0.06）
    _b(gb, x0 - 0.07, x1 + 0.07, y0 - 0.07, y1 + 0.07, zt, zt + 0.06, "M_MarbleWhite")
    # 水槽（下沉 0.20，内壁深色不锈钢）
    sx, sy = -7.86, -6.78
    _b(gb, sx - 0.26, sx + 0.26, sy - 0.21, sy + 0.21, zt - 0.20, zt - 0.18, "M_SteelDarker")
    for (a, b, c, d) in ((sx - 0.30, sx - 0.26, sy - 0.25, sy + 0.25),
                         (sx + 0.26, sx + 0.30, sy - 0.25, sy + 0.25),
                         (sx - 0.30, sx + 0.30, sy - 0.29, sy - 0.25),
                         (sx - 0.30, sx + 0.30, sy + 0.25, sy + 0.29)):
        _b(gb, a, b, c, d, zt - 0.20, zt + 0.005, "M_SteelDark")
    gb.cyl(0.021, 0.42, (sx, sy - 0.30, zt + 0.21), seg=10, mat="M_Chrome")
    gb.cyl(0.017, 0.30, (sx, sy - 0.17, zt + 0.40), axis="Y", seg=10, mat="M_Chrome")
    gb.cyl(0.014, 0.05, (sx, sy - 0.02, zt + 0.38), seg=10, mat="M_Chrome")
    # 烤炉（下沉火箱 + 铰接不锈钢盖 + 横把手 + 炉排）
    gb.box((0.62, 0.46, 0.06), (x0 + 0.32, y1 - 0.44, zt + 0.03), mat="M_SteelDarker")
    gb.box((0.58, 0.42, 0.10), (x0 + 0.32, y1 - 0.44, zt + 0.11), mat="M_EmberGlow")
    for k in range(5):
        gb.box((0.50, 0.022, 0.022), (x0 + 0.32, y1 - 0.44 + (k - 2) * 0.075, zt + 0.17),
               mat="M_SteelDark")
    gb.box((0.62, 0.46, 0.16), (x0 + 0.32, y1 - 0.44, zt + 0.26), mat="M_AluGrey")
    gb.box((0.60, 0.44, 0.04), (x0 + 0.32, y1 - 0.44, zt + 0.35), mat="M_AluGrey")
    gb.cyl(0.016, 0.34, (x0 + 0.32, y1 - 0.44, zt + 0.40), axis="Y", seg=10,
           mat="M_SteelDark")
    # 台面小物：砧板 + 碗 + 香草盆
    _b(gb, x0 + 0.62, x0 + 1.02, y0 + 0.18, y0 + 0.46, zt + 0.06, zt + 0.085, "M_TeakFurn")
    gb.lathe([(0.02, 0), (0.10, 0.012), (0.13, 0.05), (0.12, 0.07)],
             seg=16, center=(x0 + 0.82, y0 + 1.05, zt + 0.06), mat="M_CeramicDark")
    gb.cyl(0.075, 0.13, (x0 + 0.78, y0 + 1.60, zt + 0.125), seg=12, mat="M_ConcretePot",
           r_top=0.085)
    gb.sphere(0.11, (x0 + 0.78, y0 + 1.60, zt + 0.24), seg=7, rings=5, mat="M_LeafBox",
              scale=(1.0, 1.0, 0.85))
    # 3 张吧凳
    for y in (y0 + 0.62, y0 + 1.20, y0 + 1.78):
        gb.cyl(0.055, 0.02, (x1 + 0.52, y, 0.02), seg=10, mat="M_SteelDark")   # 底盘
        gb.cyl(0.035, 0.66, (x1 + 0.52, y, 0.35), seg=10, mat="M_SteelDark")   # 立柱
        gb.cyl(0.19, 0.055, (x1 + 0.52, y, 0.71), seg=14, mat="M_TeakFurn")    # 座面
        gb.cyl(0.155, 0.035, (x1 + 0.52, y, 0.755), seg=14, mat="M_FabricOutdoor")


# ================================================================ 4. 休闲组
def _cushion(gb, x, y, z, w=0.46, d=0.42, h=0.12, yaw=0.0, mat="M_FabricSage"):
    with gb.frame(_frame(x, y, z, yaw)):
        gb.box((w, d, h), (0, 0, h / 2), mat=mat)


def _sofa(gb, x, y, w=2.60, d=0.92, yaw=0.0, seats=3):
    """户外三人沙发：柚木框架 + 米色坐垫 + 靠枕。朝 −Y（局部前方）。"""
    with gb.frame(_frame(x, y, Z_DECK, yaw)):
        # 框架底座
        gb.box((w, d, 0.16), (0, 0, 0.16), mat="M_TeakFurn")
        # 木腿
        for sx in (-1, 1):
            for sy in (-1, 1):
                gb.box((0.06, 0.06, 0.14), (sx * (w / 2 - 0.09), sy * (d / 2 - 0.09), 0.07),
                       mat="M_SteelDark")
        # 靠背框
        gb.box((w, 0.10, 0.52), (0, d / 2 - 0.05, 0.42), mat="M_TeakFurn")
        # 扶手
        for sx in (-1, 1):
            gb.box((0.09, d, 0.44), (sx * (w / 2 - 0.045), 0, 0.34), mat="M_TeakFurn")
        # 坐垫（分座）
        sw = (w - 0.30) / seats
        for k in range(seats):
            cx = -w / 2 + 0.15 + sw * (k + 0.5)
            gb.box((sw - 0.02, d - 0.16, 0.13), (cx, -0.04, 0.30), mat="M_FabricOutdoor")
        # 靠背垫
        for k in range(seats):
            cx = -w / 2 + 0.15 + sw * (k + 0.5)
            gb.box((sw - 0.06, 0.13, 0.40), (cx, d / 2 - 0.16, 0.47),
                   mat="M_FabricOutdoor")
        # 抱枕
        for (px, mat) in ((-0.72, "M_FabricClay"), (0.66, "M_FabricSage")):
            gb.box((0.36, 0.11, 0.34), (px, d / 2 - 0.27, 0.47), mat=mat)
        # 搭在扶手上的毯子
        gb.box((0.30, 0.62, 0.03), (w / 2 - 0.10, -0.05, 0.575), mat="M_FabricClay")
        gb.box((0.045, 0.62, 0.16), (w / 2 - 0.02, -0.05, 0.50), mat="M_FabricClay")


def _armchair(gb, x, y, yaw=0.0):
    with gb.frame(_frame(x, y, Z_DECK, yaw)):
        gb.box((0.80, 0.80, 0.15), (0, 0, 0.155), mat="M_TeakFurn")
        for sx in (-1, 1):
            for sy in (-1, 1):
                gb.box((0.055, 0.055, 0.14), (sx * 0.33, sy * 0.33, 0.07), mat="M_SteelDark")
        gb.box((0.80, 0.09, 0.46), (0, 0.355, 0.40), mat="M_TeakFurn")
        for sx in (-1, 1):
            gb.box((0.08, 0.80, 0.36), (sx * 0.36, 0, 0.34), mat="M_TeakFurn")
        gb.box((0.66, 0.68, 0.12), (0, -0.03, 0.29), mat="M_FabricOutdoor")
        gb.box((0.64, 0.12, 0.34), (0, 0.26, 0.44), mat="M_FabricOutdoor")
        gb.box((0.32, 0.10, 0.30), (-0.06, 0.18, 0.44), mat="M_FabricSage")


def _firepit(gb, x, y, rng):
    """0.90 直径火盆：钢碗 + 卵石床 + 发光炭床 + 12 片火焰。"""
    gb.cyl(0.47, 0.06, (x, y, Z_DECK + 0.03), seg=24, mat="M_FirePit")
    gb.cyl(0.44, 0.09, (x, y, Z_DECK + 0.10), seg=24, mat="M_FirePit", r_top=0.42)
    gb.cyl(0.40, 0.02, (x, y, Z_DECK + 0.16), seg=22, mat="M_EmberGlow")
    for k in range(14):     # 盆内卵石
        a = TAU * k / 14
        rr = 0.30 + 0.06 * ((k * 7) % 3)
        gb.sphere(0.045, (x + math.cos(a) * rr, y + math.sin(a) * rr, Z_DECK + 0.18),
                  seg=5, rings=4, mat="M_Pebble")
    for k in range(12):     # 火焰片
        a = TAU * k / 12 + rng.uniform(-0.2, 0.2)
        rr = rng.uniform(0.02, 0.20)
        h = rng.uniform(0.16, 0.34)
        px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
        gb.prism([(-0.055, 0), (0.055, 0), (0.028, h), (0.0, h * 0.82), (-0.03, h)],
                 0.012, (px, py, Z_DECK + 0.18), axis="Z", mat="M_Flame",
                 smooth=False, scale=(rng.uniform(0.8, 1.15), 1.0))
    # 侧向玻璃挡风（4 片）
    for k in range(4):
        a = TAU * k / 4 + math.pi / 4
        gb.box((0.34, 0.012, 0.20),
               (x + math.cos(a) * 0.50, y + math.sin(a) * 0.50, Z_DECK + 0.20),
               rot=Matrix.Rotation(a + math.pi / 2, 3, "Z"), mat="M_GlassClear")


def _lounge(gb, rng):
    # 地毯
    _b(gb, -6.75, -2.85, -8.05, -4.55, Z_DECK + 0.001, Z_DECK + 0.012, "M_Rug")
    for (a, b, c, d) in ((-6.75, -6.63, -8.05, -4.55), (-2.97, -2.85, -8.05, -4.55),
                         (-6.75, -2.85, -8.05, -7.93), (-6.75, -2.85, -4.67, -4.55)):
        _b(gb, a, b, c, d, Z_DECK + 0.001, Z_DECK + 0.016, "M_FabricSage")
    # 三人沙发（靠背朝房子一侧 = 北，坐面朝南对火盆）
    _sofa(gb, -4.78, -4.42, w=2.60, d=0.92, yaw=0.0)
    # 两把单椅（南侧，坐面朝北对沙发）
    _armchair(gb, -5.92, -7.55, yaw=math.pi)
    _armchair(gb, -3.64, -7.55, yaw=math.pi)
    # 火盆
    _firepit(gb, -4.78, -6.02, rng)
    # 低几（火盆西侧）
    _b(gb, -7.05, -6.35, -6.42, -5.62, Z_DECK + 0.30, Z_DECK + 0.34, "M_TeakFurn")
    for sx in (-1, 1):
        for sy in (-1, 1):
            _b(gb, -7.02 + sx * 0.0, -7.02 + 0.05, -6.39, -6.34, Z_DECK, Z_DECK + 0.30, "M_TeakFurn")
    for (px, py) in ((-7.00, -6.36), (-6.42, -5.68)):
        _b(gb, px - 0.03, px + 0.03, py - 0.03, py + 0.03, Z_DECK, Z_DECK + 0.30, "M_SteelDark")
    # 低几上的托盘与杯
    _b(gb, -6.92, -6.48, -6.30, -5.86, Z_DECK + 0.34, Z_DECK + 0.355, "M_TeakFurnDark")
    for (dx, dy) in ((-6.82, -6.18), (-6.60, -6.18), (-6.60, -5.98)):
        gb.lathe([(0.012, 0), (0.038, 0.008), (0.042, 0.055)], seg=10,
                 center=(dx, dy, Z_DECK + 0.355), mat="M_Porcelain")
    # 两张边几
    for (sx, sy) in ((-6.42, -4.34), (-3.16, -4.34)):
        gb.cyl(0.24, 0.045, (sx, sy, Z_DECK + 0.46), seg=16, mat="M_TeakFurn")
        gb.cyl(0.045, 0.44, (sx, sy, Z_DECK + 0.22), seg=10, mat="M_SteelDark")
        gb.cyl(0.17, 0.02, (sx, sy, Z_DECK + 0.01), seg=14, mat="M_SteelDark")
    # 边几上的小盆栽与书
    gb.cyl(0.075, 0.12, (-6.42, -4.34, Z_DECK + 0.54), seg=10, mat="M_ConcretePot",
           r_top=0.085)
    gb.sphere(0.11, (-6.42, -4.34, Z_DECK + 0.65), seg=7, rings=5, mat="M_LeafBox",
              scale=(0.9, 0.9, 1.2))
    _b(gb, -3.32, -3.00, -4.44, -4.24, Z_DECK + 0.48, Z_DECK + 0.53, "M_Linen")
    # 靠垫落地两只
    _cushion(gb, -5.30, -3.85, Z_DECK, w=0.44, d=0.44, h=0.14, yaw=0.3, mat="M_FabricSage")
    _cushion(gb, -4.20, -3.82, Z_DECK, w=0.42, d=0.42, h=0.13, yaw=-0.2, mat="M_FabricClay")


# ================================================================ 5. 格栅亭
def _dining_chair(gb, x, y, yaw):
    with gb.frame(_frame(x, y, Z_PAVE, yaw)):
        gb.box((0.44, 0.44, 0.05), (0, 0, 0.43), mat="M_TeakFurn")
        for sx in (-1, 1):
            for sy in (-1, 1):
                gb.box((0.035, 0.035, 0.43), (sx * 0.19, sy * 0.19, 0.215),
                       mat="M_SteelDark")
        gb.box((0.42, 0.04, 0.30), (0, 0.20, 0.60), mat="M_TeakFurn")
        for k in range(3):
            gb.box((0.40, 0.03, 0.05), (0, 0.18, 0.50 + k * 0.09), mat="M_TeakFurn")
        gb.box((0.38, 0.36, 0.05), (0, 0.01, 0.475), mat="M_FabricOutdoor")


def _bench(gb, x0, x1, y0, y1):
    """亭内通长坐凳（石基座 + 木条座面 + 靠背）。"""
    _b(gb, x0 + 0.03, x1 - 0.03, y0 + 0.02, y1 - 0.02, Z_PAVE, 0.36, "M_ConcretePot")
    _b(gb, x0, x1, y0, y1, 0.36, 0.42, "M_TeakFurn")
    _b(gb, x0, x0 + 0.06, y0, y1, 0.42, 0.86, "M_SlatTeakDark")
    for k in range(4):
        _b(gb, x0, x0 + 0.085, y0 + 0.04, y1 - 0.04, 0.47 + k * 0.10,
           0.47 + k * 0.10 + 0.075, "M_TeakFurn")
    for k in range(8):
        yy = y0 + 0.10 + k * (y1 - y0 - 0.20) / 7.0
        _b(gb, x0, x1, yy - 0.022, yy + 0.022, 0.415, 0.435, "M_SlatTeakDark")


def _pergola(gb, rng):
    """深灰钢柱 + 梁格 + 柚木格栅顶（半侧实顶）+ 筒灯 + 长桌 6 椅 + 条凳 + 茶具。"""
    x0, x1 = 2.60, 8.40
    y0, y1 = -8.60, -3.80
    zc = 2.50                       # 梁底
    # 4 根钢柱
    for cx in (x0 + 0.16, x1 - 0.16):
        for cy in (y0 + 0.15, y1 - 0.15):
            _b(gb, cx - 0.06, cx + 0.06, cy - 0.06, cy + 0.06, Z_PAVE, zc, "M_SteelDarker")
            _b(gb, cx - 0.09, cx + 0.09, cy - 0.09, cy + 0.09, Z_PAVE, Z_PAVE + 0.02,
               "M_SteelDark")
            _b(gb, cx - 0.085, cx + 0.085, cy - 0.085, cy + 0.085, zc - 0.10, zc, "M_SteelDark")
    # 主梁（沿 X 两根、沿 Y 两根）
    for cy in (y0 + 0.15, y1 - 0.15):
        _b(gb, x0, x1, cy - 0.09, cy + 0.09, zc, zc + 0.18, "M_SteelDark")
    for cx in (x0 + 0.16, x1 - 0.16):
        _b(gb, cx - 0.09, cx + 0.09, y0, y1, zc, zc + 0.18, "M_SteelDark")
    # 次梁（沿 Y，3 道）
    for k in range(1, 4):
        cx = lerp(x0, x1, k / 4.0)
        _b(gb, cx - 0.05, cx + 0.05, y0, y1, zc + 0.04, zc + 0.16, "M_SteelDark")
    # 顶格栅：0.06 宽 @ 0.12 间距（沿 X 铺板条）
    zs0 = zc + 0.18
    n = int((y1 - y0) / 0.12)
    for j in range(n):
        cy = y0 + j * 0.12 + 0.03
        _b(gb, x0 - 0.05, x1 + 0.05, cy, cy + 0.06, zs0, zs0 + 0.065, "M_SlatTeak")
    # 3 道露明椽（结构感，不做实顶）
    for cy in (-7.86, -6.20, -4.54):
        _b(gb, x0 - 0.03, x1 + 0.03, cy - 0.05, cy + 0.05, zs0 - 0.02, zs0 + 0.085,
           "M_SlatTeakDark")
    # 周边细收边（与格栅留缝，透光）
    _b(gb, x0 - 0.09, x0 - 0.02, y0 - 0.09, y1 + 0.09, zs0 - 0.03, zs0 + 0.075, "M_Fascia")
    _b(gb, x1 + 0.02, x1 + 0.09, y0 - 0.09, y1 + 0.09, zs0 - 0.03, zs0 + 0.075, "M_Fascia")
    _b(gb, x0 - 0.09, x1 + 0.09, y0 - 0.09, y0 - 0.02, zs0 - 0.03, zs0 + 0.075, "M_Fascia")
    _b(gb, x0 - 0.09, x1 + 0.09, y1 + 0.02, y1 + 0.09, zs0 - 0.03, zs0 + 0.075, "M_Fascia")
    # 梁下筒灯
    for (lx, ly) in ((3.60, -7.10), (5.50, -7.10), (7.40, -7.10),
                     (3.60, -5.00), (7.40, -5.00)):
        gb.cyl(0.055, 0.02, (lx, ly, zc - 0.012), seg=12, mat="M_Uplight")
        gb.cyl(0.075, 0.03, (lx, ly, zc + 0.005), seg=12, mat="M_SteelDark")
    # 吊灯（纸灯笼）
    _b(gb, 7.20, 7.24, -4.60, -4.56, zs0 - 0.30, zs0, "M_SteelDark")
    gb.sphere(0.20, (7.22, -4.58, zs0 - 0.52), seg=12, rings=8, mat="M_Linen",
              scale=(1, 1, 1.15))
    gb.cyl(0.205, 0.02, (7.22, -4.58, zs0 - 0.72), seg=12, mat="M_SteelDark")

    # ---- 长桌 2.2 × 1.0
    tx0, tx1 = 4.30, 6.50
    ty0, ty1 = -6.90, -5.90
    zt = 0.74
    _b(gb, tx0, tx1, ty0, ty1, zt, zt + 0.05, "M_TeakFurn")
    for sx in (tx0 + 0.14, tx1 - 0.14):
        for sy in (ty0 + 0.12, ty1 - 0.12):
            _b(gb, sx - 0.04, sx + 0.04, sy - 0.04, sy + 0.04, Z_PAVE, zt, "M_SteelDark")
    _b(gb, tx0 + 0.20, tx1 - 0.20, ty0 + 0.10, ty0 + 0.14, zt + 0.05, zt + 0.09, "M_SlatTeak")
    # 椅子：北 3 / 南 3
    for k in range(3):
        cx = tx0 + 0.42 + k * 0.66
        _dining_chair(gb, cx, ty1 + 0.36, 0.0)      # 北排：背朝北，面向桌
        _dining_chair(gb, cx, ty0 - 0.36, math.pi)  # 南排：背朝南，面向桌
    # 通长条凳（亭西侧）
    _bench(gb, 2.86, 3.34, -7.70, -4.72)
    # 茶具：托盘 + 壶 + 4 杯 + 2 碗
    _b(gb, 5.10, 5.80, -6.72, -6.16, zt + 0.05, zt + 0.062, "M_TeakFurnDark")
    gb.lathe([(0.035, 0), (0.10, 0.02), (0.125, 0.09), (0.10, 0.15), (0.045, 0.17),
              (0.038, 0.20), (0.02, 0.215)], seg=14,
             center=(5.45, -6.44, zt + 0.062), mat="M_Celadon")
    gb.cyl(0.02, 0.07, (5.45, -6.44, zt + 0.30), seg=8, mat="M_Celadon")
    for (dx, dy) in ((5.20, -6.24), (5.32, -6.60), (5.68, -6.26), (5.72, -6.58)):
        gb.lathe([(0.012, 0), (0.036, 0.006), (0.041, 0.052)], seg=10,
                 center=(dx, dy, zt + 0.062), mat="M_Celadon")
    for (dx, dy) in ((4.62, -6.50), (6.10, -6.62)):
        gb.lathe([(0.02, 0), (0.09, 0.01), (0.12, 0.045), (0.115, 0.06)], seg=12,
                 center=(dx, dy, zt + 0.05), mat="M_Porcelain")
    # 亭内边几 + 花瓶
    _b(gb, 7.86, 8.24, -7.78, -7.40, 0.40, 0.44, "M_TeakFurn")
    for (px, py) in ((7.90, -7.74), (8.20, -7.74), (7.90, -7.44), (8.20, -7.44)):
        _b(gb, px - 0.015, px + 0.015, py - 0.015, py + 0.015, Z_PAVE, 0.40, "M_SteelDark")
    gb.lathe([(0.05, 0), (0.09, 0.03), (0.07, 0.18), (0.035, 0.26)], seg=12,
             center=(8.05, -7.59, 0.44), mat="M_Porcelain")
    for k in range(4):
        a = TAU * k / 4
        gb.box((0.012, 0.012, 0.34),
               (8.05 + math.cos(a) * 0.05, -7.59 + math.sin(a) * 0.05, 0.78),
               mat="M_LeafOlive")


# ================================================================ 6. 水幕墙
def _water(gb, rng):
    """石材背板 2.6 高 + 3 道水幕 + 0.45 宽水槽（卵石 / 水下灯 / 溢水口）。"""
    px0, px1 = 8.26, 8.38
    py0, py1 = -4.60, -1.80
    hz = 2.60
    _b(gb, px0, px1, py0, py1, Z_PAVE, hz, "M_SandDark")
    # 石材横缝 + 竖缝（读成深色砌块墙）
    for k in range(1, 6):
        zz = Z_PAVE + hz * k / 6.0
        _b(gb, px0 - 0.006, px1, py0, py1, zz - 0.008, zz + 0.008, "M_GraniteEdge")
    for k in range(1, 5):
        yy = py0 + (py1 - py0) * k / 5.0
        _b(gb, px0 - 0.006, px1, yy - 0.010, yy + 0.010, Z_PAVE, hz, "M_GraniteEdge")
    # 顶部压顶 + 出水口
    _b(gb, px0 - 0.08, px1 + 0.04, py0 - 0.04, py1 + 0.04, hz, hz + 0.08, "M_GraniteEdge")
    _b(gb, px0 - 0.05, px0 + 0.01, py0 + 0.06, py1 - 0.06, hz - 0.05, hz, "M_WaterFall")
    # 3 道水幕
    for (a, b) in ((py0 + 0.18, py0 + 0.72), (py0 + 0.86, py0 + 1.54),
                   (py0 + 1.68, py1 - 0.18)):
        _b(gb, px0 - 0.035, px0 - 0.015, a, b, 0.34, hz - 0.05, "M_WaterFall")
        _b(gb, px0 - 0.05, px0 - 0.045, a, b, 0.34, hz - 0.05, "M_WaterFall")
    # 跌落底部白水（水花带）
    for (a, b) in ((py0 + 0.18, py0 + 0.72), (py0 + 0.86, py0 + 1.54),
                   (py0 + 1.68, py1 - 0.18)):
        _b(gb, px0 - 0.06, px0 - 0.01, a, b, 0.30, 0.40, "M_WaterFall")
    # 水槽（0.46 宽）
    tx0, tx1 = 7.80, 8.26
    tz = 0.36
    _b(gb, tx0, tx1, py0, py1, Z_PAVE, tz, "M_GraniteEdge")
    _b(gb, tx0 + 0.09, tx1, py0 + 0.09, py1 - 0.09, 0.04, 0.06, "M_WaterDark")
    for (a, b, c, d) in ((tx0 + 0.09, tx0, py0, py1),):
        pass
    # 内壁收口
    for (a, b, c, d) in ((tx0, tx0 + 0.09, py0, py1), (tx0, tx1, py0, py0 + 0.09),
                         (tx0, tx1, py1 - 0.09, py1)):
        _b(gb, a, b, c, d, tz - 0.03, tz, "M_GraniteEdge")
    # 水面
    _b(gb, tx0 + 0.09, tx1 - 0.01, py0 + 0.09, py1 - 0.09, 0.20, 0.225, "M_Water")
    # 槽底卵石
    for k in range(26):
        px = tx0 + 0.13 + (tx1 - tx0 - 0.22) * ((k * 37) % 100) / 100.0
        py = py0 + 0.16 + (py1 - py0 - 0.32) * ((k * 61) % 100) / 100.0
        gb.sphere(0.035 + 0.02 * ((k * 13) % 4) / 3.0, (px, py, 0.10),
                  seg=5, rings=4, mat="M_Pebble", scale=(1.3, 1.1, 0.7))
    # 3 盏水下灯
    for py in (-3.98, -3.20, -2.40):
        gb.cyl(0.035, 0.02, (tx0 + 0.16, py, 0.075), seg=10, mat="M_WaterfallLED")
        gb.cyl(0.06, 0.02, (tx0 + 0.16, py, 0.065), seg=10, mat="M_SteelDark")
    # 溢水口与侧向回水石
    _b(gb, tx0 - 0.02, tx0 + 0.02, py0 + 0.30, py0 + 0.42, tz - 0.06, tz + 0.01,
       "M_GraniteEdge")
    _b(gb, tx0 - 0.10, tx0, py1 - 0.30, py1 - 0.10, 0.02, 0.20, "M_StoneDark")


# ================================================================ 7. 枯山水
def _zen(gb, rng):
    """抬高砂床 + 花岗岩缘石 + 环状耙纹 + 3 块景石 + 苔岛造型松 + 2 汀步。"""
    x0, x1 = 2.00, 8.00
    y0, y1 = -13.20, -9.40
    k = 0.12                       # 缘石宽
    zk = Z_PAVE + 0.16             # 缘石顶
    zs = Z_PAVE + 0.125            # 砂面
    # 床体 + 缘石
    _b(gb, x0 + k, x1 - k, y0 + k, y1 - k, Z_PAVE, zs, "M_SandWhite")
    _b(gb, x0, x1, y0, y0 + k, Z_PAVE, zk, "M_GraniteEdge")
    _b(gb, x0, x1, y1 - k, y1, Z_PAVE, zk, "M_GraniteEdge")
    _b(gb, x0, x0 + k, y0 + k, y1 - k, Z_PAVE, zk, "M_GraniteEdge")
    _b(gb, x1 - k, x1, y0 + k, y1 - k, Z_PAVE, zk, "M_GraniteEdge")
    # 砂面（略微起伏）
    ix0, ix1 = x0 + k + 0.004, x1 - k - 0.004
    iy0, iy1 = y0 + k + 0.004, y1 - k - 0.004
    gb.plane(((ix0, ix1), (iy0, iy1)), mat="M_SandWhite", z=zs + 0.004)
    # 耙纹裁剪
    def clip(p):
        return ix0 + 0.03 < p[0] < ix1 - 0.03 and iy0 + 0.03 < p[1] < iy1 - 0.03

    zr = zs + 0.012
    # ---- 3 块景石
    stones = ((5.40, -12.45, 0.62, 3), (6.62, -10.58, 0.44, 5), (4.40, -9.98, 0.30, 8))
    for (sx, sy, rr, sd) in stones:
        with gb.frame(Matrix.Translation((sx, sy, zs + 0.17))):
            nature.rock(gb, r=rr, mat="M_Boulder", seed=sd, squash=0.62)
    # ---- 环状耙纹（以景石为圆心）
    for (sx, sy, rr, sd) in stones:
        radius = rr * 0.95 + 0.16
        idx = 0
        while radius < 1.85:
            seg = int(max(14, min(46, radius * 26)))
            _arc_ridge(gb, sx, sy, radius, 0.055, zr, 0.0, TAU, seg,
                       "M_SandRipple", clip)
            radius += 0.185
            idx += 1
            if idx > 9:
                break
    # ---- 苔岛 + 造型松
    mx, my = 3.18, -11.55
    gb.sphere(0.98, (mx, my, zs + 0.13), seg=18, rings=8, mat="M_Moss",
              scale=(1.0, 1.0, 0.26))
    gb.sphere(0.72, (mx + 0.30, my + 0.34, zs + 0.11), seg=14, rings=6, mat="M_Moss",
              scale=(1.0, 1.0, 0.20))
    # 苔岛耙纹（环绕苔岛）
    radius = 1.14
    while radius < 1.9:
        seg = int(max(16, min(46, radius * 26)))
        _arc_ridge(gb, mx, my, radius, 0.055, zr, 0.0, TAU, seg, "M_SandRipple", clip)
        radius += 0.185
    # 造型松（自写 niwaki：深色针叶 + 横向云片 + 5 层递减）
    _PLANT_NIWAKI = (mx, my, zs + 0.16)   # 由真针叶树替换，见 build()
    # ---- 2 块汀步（穿过砂床）
    for (px, py, rot) in ((4.62, -12.62, 0.10), (5.52, -11.92, -0.14)):
        with gb.frame(_frame(px, py, zs + 0.025, rot)):
            gb.box((0.62, 0.42, 0.05), (0, 0, 0), mat="M_PaveGrey")
    # ---- 砂床里的低位点光 2 盏
    for (px, py) in ((6.90, -12.80), (7.30, -10.10)):
        gb.cyl(0.055, 0.02, (px, py, zs + 0.008), seg=12, mat="M_Uplight")


# ================================================================ 8. 草坪 / 种植
def _maple_small(gb, x, y, h=2.5, r=1.15, leaf="M_LeafMaple", seed=0):
    """小乔木（多干、秋色）：冠用 24+ 个叶团，成本远低于 nature.maple。"""
    rng = random.Random(seed)
    gb.cyl(0.070, h * 0.56, (x, y, h * 0.28), seg=8, mat="M_Bark", r_top=0.050)
    tips = []
    for k in range(3):
        a = TAU * k / 3 + rng.uniform(-0.45, 0.45)
        b0 = Vector((x, y, h * 0.50))
        b1 = Vector((x + math.cos(a) * r * 0.30, y + math.sin(a) * r * 0.30, h * 0.80))
        d = b1 - b0
        M = (Matrix.Translation((b0 + b1) / 2) @
             Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z") @
             Matrix.Rotation(math.atan2(math.hypot(d.x, d.y), d.z), 4, "Y"))
        with gb.frame(M):
            gb.cyl(0.038, d.length, (0, 0, 0), seg=6, mat="M_Bark", r_top=0.024)
        tips.append((b1, a))
    for (base, a0) in tips:
        for _m in range(9):
            rr = rng.uniform(0.06, r * 0.92)
            a2 = a0 + rng.uniform(-1.25, 1.25)
            p = (base.x + math.cos(a2) * rr, base.y + math.sin(a2) * rr,
                 base.z + rng.uniform(-0.05, 0.36))
            gb.sphere(rng.uniform(0.13, 0.22), p, seg=7, rings=5, mat=leaf,
                      scale=(1.55, 1.40, 0.60))


def _niwaki(gb, x, y, z0, h=2.0, r=1.0, seed=0):
    """日式造型松：弯曲主干 + 5 层横向云片（扁平、密集、深色针叶）。

    与 nature.pine 的区别：不做球形叶团，云片 scale z 压到 0.24，
    越往上直径越小，层间留出可见主干 —— 剪影才是黑松，不是一棵绒球。
    """
    rng = random.Random(seed)
    # 主干（4 段 S 弯；局部坐标 + 基座平移，否则会落在世界原点）
    base = Matrix.Translation((x, y, z0))
    seg = 4
    pts = []
    lean = 0.16
    for i in range(seg + 1):
        t = i / seg
        pts.append(Vector((math.sin(t * 2.3) * lean * t, rng.uniform(-0.03, 0.03) * t,
                           h * t)))
    for i in range(seg):
        p0, p1 = pts[i], pts[i + 1]
        d = p1 - p0
        M = (base @ Matrix.Translation((p0 + p1) / 2) @
             Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z") @
             Matrix.Rotation(math.atan2(math.hypot(d.x, d.y), d.z), 4, "Y"))
        rad = lerp(0.085, 0.032, i / seg)
        with gb.frame(M):
            gb.cyl(rad, d.length * 1.04, (0, 0, 0), seg=8, mat="M_Bark", r_top=rad * 0.88)
    # 5 层云片
    tiers = ((0.40, 0.96), (0.55, 0.86), (0.68, 0.70), (0.80, 0.52), (0.92, 0.34))
    for (tt, rk) in tiers:
        cz = h * tt
        rr = r * rk
        n = 7
        for k in range(n):
            a = TAU * k / n + rng.uniform(-0.22, 0.22)
            d = rr * rng.uniform(0.45, 1.0)
            px = x + math.cos(a) * d
            py = y + math.sin(a) * d
            pz = z0 + cz + rng.uniform(-0.03, 0.05)
            # 云片：横向扁球，2–3 个叠成一片
            for m in range(2):
                gb.sphere(rng.uniform(0.10, 0.15),
                          (px + rng.uniform(-0.05, 0.05),
                           py + rng.uniform(-0.05, 0.05), pz + m * 0.035),
                          seg=6, rings=4, mat="M_LeafDeep",
                          scale=(1.75, 1.60, 0.26))
            # 细枝连到主干
            gb.cyl(0.012, max(d, 0.05), (x + math.cos(a) * d * 0.5,
                                         y + math.sin(a) * d * 0.5, z0 + cz - 0.02),
                   axis="Z", seg=4, mat="M_Bark",
                   rot=Matrix.Rotation(-a, 3, "Y"))
    # 顶冠（一片小的）
    gb.sphere(0.15, (x + lean, y, z0 + h + 0.02), seg=7, rings=4, mat="M_LeafDeep",
              scale=(1.5, 1.4, 0.34))


def _shrub_low(gb, x, y, r, seed=0, mat="M_LeafBox"):
    """低矮灌木丛：3 个压扁球堆叠，贴地生长。"""
    rng = random.Random(seed)
    for k in range(3):
        a = TAU * k / 3 + rng.uniform(-0.4, 0.4)
        gb.sphere(r * rng.uniform(0.62, 0.86),
                  (x + math.cos(a) * r * 0.42, y + math.sin(a) * r * 0.36,
                   r * rng.uniform(0.50, 0.72)),
                  seg=8, rings=5, mat=mat, scale=(1.15, 1.05, 0.78))


def _box_ball(gb, x, y, r, seed=0, mat="M_LeafBox"):
    rng = random.Random(seed)
    gb.sphere(r, (x, y, r * 0.86), seg=10, rings=7, mat=mat, scale=(1.0, 1.0, 0.90))
    for k in range(3):
        a = TAU * k / 3 + rng.uniform(-0.3, 0.3)
        gb.sphere(r * 0.42, (x + math.cos(a) * r * 0.62, y + math.sin(a) * r * 0.62,
                             r * 0.62), seg=6, rings=4, mat=mat, scale=(1, 1, 0.85))


def _hydrangea(gb, x, y, r=0.42, bloom="M_BloomWhite", seed=1):
    rng = random.Random(seed)
    for k in range(4):
        a = TAU * k / 4 + rng.uniform(-0.35, 0.35)
        gb.sphere(r * 0.44, (x + math.cos(a) * r * 0.42, y + math.sin(a) * r * 0.42,
                             r * 0.34), seg=6, rings=4, mat="M_LeafDeep",
                  scale=(1.25, 1.25, 0.72))
    for k in range(13):
        a = rng.uniform(0, TAU)
        rr = math.sqrt(rng.random()) * r * 0.86
        gb.sphere(rng.uniform(0.085, 0.145),
                  (x + math.cos(a) * rr, y + math.sin(a) * rr,
                   r * 0.62 + rng.uniform(-0.02, 0.30)),
                  seg=5, rings=4, mat=bloom)


def _grass_fan(gb, x, y, h=0.44, n=11, mat="M_GrassOrn", seed=0):
    rng = random.Random(seed)
    for k in range(n):
        a = TAU * k / n + rng.uniform(-0.25, 0.25)
        lean = rng.uniform(0.10, 0.30)
        hh = h * rng.uniform(0.62, 1.18)
        ca, sa = math.cos(a), math.sin(a)
        px, py = -sa, ca
        bx, by = x + ca * 0.035, y + sa * 0.035
        tx, ty = x + ca * (0.035 + lean), y + sa * (0.035 + lean)
        gb.quad((bx - px * 0.013, by - py * 0.013, 0.02),
                (bx + px * 0.013, by + py * 0.013, 0.02),
                (tx + px * 0.004, ty + py * 0.004, hh),
                (tx - px * 0.004, ty - py * 0.004, hh), mat=mat)


def _lawn_beds(gb, rng, ctx):
    """西侧草坪 + 秋枫 + 绣球 + 球灌木 + 观赏草 + 汀步。"""
    # 草坪
    _b(gb, -8.40, -2.20, -13.40, -9.00, 0.0, 0.015, "M_Lawn")
    # 草坪里的汀步 6 块（通到平台踏步）
    for k, y in enumerate((-9.98, -10.78, -11.58, -12.38, -13.14)):
        px = -3.66 + (0.10 if k % 2 else -0.10)
        with gb.frame(_frame(px, y, 0.045, 0.06 if k % 2 else -0.06)):
            gb.box((0.62, 0.42, 0.06), (0, 0, 0), mat="M_PaveGrey")
    with gb.frame(_frame(-4.55, -9.42, 0.045, 0.0)):
        gb.box((0.62, 0.42, 0.06), (0, 0, 0), mat="M_PaveGrey")

    # ---- 5 棵小乔木（PolyHaven island_tree_01，自然高 5.0 m，压到 2.8–3.3 m 当庭园小树）
    # tree_small_02 自然 4.55 m、密叶，压缩到 4.2–4.6 m 当庭园小乔木
    maples = ((-7.55, -12.55, 4.6, "tree_small_02"),
              (-7.60, -10.10, 4.2, "tree_small_02"),
              (-3.35, -12.60, 4.4, "tree_small_02"))
    for k, (mx, my, mh, mn) in enumerate(maples):
        _plant(ctx, mn, "lawn_t%d" % k, mx, my, h=mh, max_w=3.6)

    # ---- 8 组灌木（shrub_02 自然高 1.22 m，压到 0.58–0.70）
    hyd = ((-8.62, -12.10), (-8.62, -10.55), (-8.62, -9.28), (-2.62, -11.35),
           (-6.85, -13.16), (-4.95, -13.20), (-8.60, -13.24), (-2.58, -12.28))
    for k, (hx, hy) in enumerate(hyd):
        _plant(ctx, "shrub_02", "lawn_h%d" % k, hx, hy, h=1.05 + 0.08 * (k % 3))

    # ---- 6 个修剪球（shrub_03 0.40 m / shrub_01 0.29 m）
    balls = ((-8.60, -11.36, 0.42), (-8.60, -9.86, 0.36), (-2.66, -10.60, 0.40),
             (-4.30, -9.55, 0.34), (-6.55, -9.42, 0.32), (-2.60, -13.10, 0.38))
    for k, (bx, by, br) in enumerate(balls):
        _plant(ctx, "shrub_02", "lawn_b%d" % k, bx, by, h=0.80 + 0.08 * (k % 3))

    # ---- 12 丛观赏草（grass_medium_02 0.26 m，压到 0.36–0.48）
    tufts = ((-8.55, -12.72), (-8.50, -11.85), (-8.52, -10.98), (-8.48, -9.66),
             (-2.55, -9.92), (-2.52, -11.86), (-3.42, -9.40), (-5.25, -9.38),
             (-6.95, -9.36), (-2.56, -12.62), (-7.05, -13.22), (-4.10, -13.22))
    for k, (tx, ty) in enumerate(tufts):
        _plant(ctx, "grass_medium_02", "lawn_g%d" % k, tx, ty,
               h=0.55 + 0.08 * (k % 3))

    # ---- 花色点缀（真花 periwinkle / celandine，压到 0.22 m）
    for k, (fx, fy) in enumerate(((-8.58, -11.60), (-8.58, -10.20),
                                  (-2.60, -11.00), (-5.90, -9.36))):
        _plant(ctx, "periwinkle_plant" if k % 2 else "celandine_01",
               "lawn_f%d" % k, fx, fy, h=0.55)

    # ---- 组合：石缝里的低矮蕨 / 地被
    for k in range(10):
        a = TAU * k / 10
        gb.sphere(0.13, (-8.66 + math.cos(a) * 0.22, -12.15 + math.sin(a) * 0.22, 0.10),
                  seg=6, rings=4, mat="M_LeafDeep", scale=(1, 1, 0.5))


def _wall_beds(gb, rng, ctx):
    """沿墙 0.6 宽种植带：花岗岩缘石 + 苔 + 灌木 + 球 + 观赏草。"""
    beds = (
        # (x0, x1, y0, y1)
        (-9.00, -8.40, -14.00, -1.50),      # 西墙
        (8.40, 9.00, -14.00, -1.50),        # 东墙
        (-8.40, -2.20, -2.20, -1.50),       # 房子南墙（西段）
        (1.80, 7.60, -2.20, -1.50),         # 房子南墙（东段）
    )
    for (x0, x1, y0, y1) in beds:
        _b(gb, x0, x1, y0, y1, Z_PAVE - 0.02, Z_BED, "M_Soil")
        # 缘石（朝院内心那侧）
        along_x = (x1 - x0) > (y1 - y0)
        if along_x:
            yy = y0 if y0 > -2.0 else y0
            _b(gb, x0, x1, y0, y0 + 0.08, Z_PAVE - 0.02, Z_BED + 0.03, "M_GraniteEdge")
        # 苔斑
        n = int(max(2, (x1 - x0 if along_x else y1 - y0) / 0.55))
        for k in range(n):
            t = (k + 0.5) / n
            px = lerp(x0 + 0.08, x1 - 0.08, t) if along_x else (x0 + x1) / 2
            py = (y0 + y1) / 2 if along_x else lerp(y0 + 0.10, y1 - 0.10, t)
            rr = 0.24 + 0.10 * ((k * 7) % 3) / 2.0
            if along_x:
                py = min(py, y1 - 0.22)
            gb.sphere(rr, (px, py, Z_BED - 0.02), seg=8, rings=5, mat="M_Moss",
                      scale=(1.5, 1.0, 0.35))

    # ---- 南墙花带（院门两侧）
    for (x0, x1) in ((-8.40, -2.06), (2.06, 8.40)):
        _b(gb, x0, x1, -14.00, -13.44, Z_PAVE - 0.02, Z_BED, "M_Soil")
        _b(gb, x0, x1, -13.44, -13.36, Z_PAVE - 0.02, Z_BED + 0.03, "M_GraniteEdge")
        n = int((x1 - x0) / 0.62)
        for k in range(n):
            px = lerp(x0 + 0.28, x1 - 0.28, (k + 0.5) / n)
            gb.sphere(0.24, (px, -13.72, Z_BED - 0.03), seg=8, rings=5,
                      mat="M_Moss", scale=(1.6, 1.1, 0.40))

    # ---- 东墙深格栅段的种植（深色背景前的白花与球）
    zs = Z_BED
    for k, (sx, sy, sr) in enumerate(((8.70, -7.90, 0.36), (8.70, -5.10, 0.33),
                                      (8.70, -3.10, 0.30), (8.68, -9.30, 0.38),
                                      (8.70, -12.90, 0.34))):
        _plant(ctx, "shrub_03" if k % 2 else "shrub_01", "eb%d" % k, sx, sy,
               h=1.00 + 0.08 * (k % 2))
    for k, (sx, sy) in enumerate(((8.66, -4.10), (8.66, -6.50), (8.66, -8.60))):
        _plant(ctx, "shrub_04", "ebf%d" % k, sx, sy, h=0.24)

    # ---- 东角高枫：主干高、冠收窄且抬到 2.2 m 以上，压住东墙但不穿格栅
    _plant(ctx, "island_tree_02", "east_tree", 8.36, -11.60, h=3.6)

    # ---- 墙前灌木丛（程序化。assets/ 三个 .blend 实测是平摊标本扫描：
    #      shrub 局部盒 1.36x0.16x0.40、花丛 9.06x9.04x2.50 且对象自带 0.148 缩放，
    #      立栽会塌成薄片，故全院植被改用 nature.py 程序化）
    for k, (sx, sy, sr) in enumerate(((-8.66, -12.40, 0.40), (-8.66, -11.20, 0.34),
                                      (-8.66, -9.90, 0.38), (-8.66, -8.60, 0.32),
                                      (-8.66, -5.30, 0.40), (-8.66, -3.40, 0.36),
                                      (-8.66, -2.10, 0.34), (8.66, -13.30, 0.38),
                                      (8.66, -6.30, 0.34), (2.60, -2.05, 0.34),
                                      (4.90, -2.05, 0.32), (6.90, -2.05, 0.34))):
        _plant(ctx, "shrub_02", "ws%d" % k, sx, sy, h=0.92 + 0.06 * (k % 3),
               max_w=0.85)
    # ---- 花带（绣球 + 白花球，替代 gazania 扫描件）
    for k, (fx, fy) in enumerate(((-8.66, -13.10), (-8.66, -10.60), (-8.66, -7.30),
                                  (-8.66, -4.20), (8.66, -12.20), (8.66, -5.70),
                                  (-5.60, -13.16), (-3.20, -13.16))):
        _plant(ctx, "periwinkle_plant" if k % 2 else "celandine_01",
               "wf%d" % k, fx, fy, h=0.40)
    # ---- 院外行道树 2 株（深绿，压住街景天际线）
    _plant(ctx, "island_tree_02", "street_t1", -8.60, -16.35, h=3.2)
    _plant(ctx, "island_tree_02", "street_t2", 8.05, -16.32, h=3.0)


# ================================================================ 9. 围墙 / 院门
def _wall(gb, x0, x1, y0, y1, h=Z_WALL, dark_core=True):
    """白色横向格栅墙：深色芯 + 白色横板（0.155 高 / 0.026 缝）+ 深灰压顶。"""
    along_x = (x1 - x0) > (y1 - y0)
    # 深色芯（比面层薄，形成阴影凹槽）
    if along_x:
        yc0, yc1 = y0 + (y1 - y0) * 0.28, y1 - (y1 - y0) * 0.28
        _b(gb, x0, x1, yc0, yc1, 0.0, h, "M_SteelDarker")
    else:
        xc0, xc1 = x0 + (x1 - x0) * 0.28, x1 - (x1 - x0) * 0.28
        _b(gb, xc0, xc1, y0, y1, 0.0, h, "M_SteelDarker")
    # 白色横板
    slat, gap = 0.155, 0.026
    z = 0.12
    while z + slat <= h + 0.001:
        _b(gb, x0, x1, y0, y1, z, z + slat, "M_WallWhite")
        z += slat + gap
    # 基座（深色）
    _b(gb, x0, x1, y0, y1, 0.0, 0.12, "M_GraniteEdge")
    # 压顶（深灰，两侧挑出）
    if along_x:
        _b(gb, x0 - 0.03, x1 + 0.03, y0 - 0.04, y1 + 0.04, h, h + 0.10, "M_Fascia")
    else:
        _b(gb, x0 - 0.04, x1 + 0.04, y0 - 0.03, y1 + 0.03, h, h + 0.10, "M_Fascia")


def _east_screen(gb):
    """东段（Y −9…−2）深灰竖向格栅屏。"""
    bx0, bx1 = 9.02, 9.18
    y0, y1 = -9.00, -2.00
    _b(gb, bx0, bx1, y0, y1, 0.0, 0.10, "M_GraniteEdge")
    _b(gb, bx0 + 0.02, bx1 - 0.02, y0, y1, 0.10, 2.10, "M_SteelDarker")
    n = int((y1 - y0) / 0.11)
    for k in range(n):
        cy = y0 + k * 0.11 + 0.025
        _b(gb, 9.00, 9.06, cy, cy + 0.06, 0.10, 2.10, "M_SlatTeak")
    # 顶部与底部横档
    _b(gb, 8.98, 9.08, y0, y1, 2.10, 2.16, "M_SteelDark")
    _b(gb, 9.00, 9.20, y0 - 0.03, y1 + 0.03, 2.16, 2.24, "M_Fascia")


def _fence(gb, rng):
    # 西墙 / 东墙
    _wall(gb, -9.18, -9.00, -14.18, -1.54)
    _wall(gb, 9.00, 9.18, -14.18, -9.02)
    _wall(gb, 9.00, 9.18, -1.98, -1.54)
    _east_screen(gb)
    # 南墙两段（院门两侧）
    _wall(gb, -9.18, -1.95, -14.18, -14.00)
    _wall(gb, 1.95, 9.18, -14.18, -14.00)
    # 门柱 2 根 0.45 sq × 2.60
    for cx in (-1.725, 1.725):
        _b(gb, cx - 0.225, cx + 0.225, -14.23, -13.95, 0.0, 2.60, "M_LimeStone")
        for k in range(4):
            zz = 0.52 * (k + 1)
            _b(gb, cx - 0.226, cx + 0.226, -14.231, -13.949, zz - 0.006, zz + 0.006,
               "M_GraniteEdge")
        _b(gb, cx - 0.245, cx + 0.245, -14.25, -13.93, 2.60, 2.70, "M_Fascia")
        # 柱顶小射灯（照门）
        gb.cyl(0.035, 0.02, (cx, -14.24, 2.56), seg=10, mat="M_Uplight")

    # ---- 玻璃对开院门（X −1.50…1.50）
    gate_w, gate_h = 1.50, 1.90
    for sgn in (-1, 1):
        cx0 = 0.0 if sgn < 0 else 0.0
        xa = -1.50 if sgn < 0 else 0.0
        xb = 0.0 if sgn < 0 else 1.50
        yc = -13.99
        # 上下横档
        _b(gb, xa, xb, yc - 0.03, yc + 0.03, 0.0, 0.07, "M_SteelDarker")
        _b(gb, xa, xb, yc - 0.03, yc + 0.03, gate_h - 0.07, gate_h, "M_SteelDarker")
        _b(gb, xa, xb, yc - 0.03, yc + 0.03, 1.02, 1.09, "M_SteelDarker")
        # 竖框
        for xv in (xa + 0.035, xb - 0.035):
            _b(gb, xv - 0.035, xv + 0.035, yc - 0.03, yc + 0.03, 0.0, gate_h, "M_SteelDarker")
        # 玻璃
        _b(gb, xa + 0.06, xb - 0.06, yc - 0.008, yc + 0.008, 0.07, gate_h - 0.07,
           "M_GlassGate")
        # 长竖拉手（靠门缝一侧）
        hx = (xb - 0.12) if sgn > 0 else (xa + 0.12)
        _b(gb, hx - 0.012, hx + 0.012, yc - 0.075, yc - 0.045, 0.55, 1.55, "M_SteelDark")
        _b(gb, hx - 0.012, hx + 0.012, yc - 0.06, yc - 0.02, 0.55, 0.60, "M_SteelDark")
        _b(gb, hx - 0.012, hx + 0.012, yc - 0.06, yc - 0.02, 1.50, 1.55, "M_SteelDark")
        # 上下枢轴
        gb.cyl(0.022, 0.06, (xa + 0.05, yc, 1.94), seg=10, mat="M_SteelDark")


# ================================================================ 10. 灯具
def _bollard(gb, x, y):
    """0.9 高草坪灯：深灰柱身 + 亚光出光口。"""
    gb.cyl(0.085, 0.02, (x, y, 0.03), seg=12, mat="M_BollardBody")
    gb.cyl(0.052, 0.72, (x, y, 0.40), seg=12, mat="M_BollardBody")
    gb.cyl(0.058, 0.05, (x, y, 0.78), seg=12, mat="M_BollardBody")
    gb.cyl(0.050, 0.13, (x, y, 0.87), seg=12, mat="M_Uplight")
    gb.cyl(0.056, 0.04, (x, y, 0.955), seg=12, mat="M_BollardBody")


def _uplight(gb, x, y, r=0.055):
    gb.cyl(r, 0.055, (x, y, Z_PAVE + 0.028), seg=10, mat="M_BollardBody")
    gb.cyl(r * 0.8, 0.014, (x, y, Z_PAVE + 0.06), seg=10, mat="M_Uplight")


def _wall_washer(gb, x, y, yaw, z=2.05):
    with gb.frame(_frame(x, y, z, yaw)):
        gb.box((0.16, 0.10, 0.07), (0, 0, 0), mat="M_BollardBody")
        gb.box((0.13, 0.012, 0.05), (0, -0.052, -0.008), mat="M_Uplight")


def _lights(gb, rng):
    # 6 盏草坪柱灯
    for (x, y) in ((2.28, -9.10), (2.28, -5.60), (-2.10, -11.20),
                   (-2.10, -6.40), (7.55, -9.25), (7.55, -3.10)):
        _bollard(gb, x, y)
    # 8 盏树下射灯
    for (x, y) in ((-7.62, -12.30), (-7.66, -9.62), (-5.30, -12.86),
                   (-3.20, -12.30), (5.92, -11.10), (2.62, -12.42),
                   (8.36, -10.80), (-2.16, -2.02)):
        _uplight(gb, x, y)
    # 4 盏围墙洗墙灯
    _wall_washer(gb, -5.40, -13.96, 0.0)
    _wall_washer(gb, -3.10, -13.96, 0.0)
    _wall_washer(gb, 3.40, -13.96, 0.0)
    _wall_washer(gb, -8.96, -11.60, math.pi / 2)
    # 亭内 2 盏地埋灯（照柱）
    _uplight(gb, 2.92, -8.34, r=0.05)
    _uplight(gb, 8.10, -8.34, r=0.05)


# ================================================================ 11. 街景
def _car(gb, cx, cy, body, plate, rng):
    """简化但可读的整车：车身 + 玻璃舱 + 4 轮 + 灯 + 后视镜。"""
    z0 = -0.02
    bl, bw = 2.16, 0.92
    # 轮胎
    for sx in (-1.34, 1.34):
        for sy in (-1, 1):
            gb.cyl(0.33, 0.23, (cx + sx, cy + sy * 0.86, z0 + 0.33), axis="Y",
                   seg=16, mat="M_BollardBody")
            gb.cyl(0.185, 0.235, (cx + sx, cy + sy * 0.86, z0 + 0.33), axis="Y",
                   seg=12, mat="M_Chrome")
            gb.cyl(0.34, 0.02, (cx + sx, cy + sy * 0.98, z0 + 0.33), axis="Y",
                   seg=16, mat="M_SteelDarker")
    # 底盘 / 车身
    _b(gb, cx - bl, cx + bl, cy - bw, cy + bw, z0 + 0.22, z0 + 0.52, body)
    _b(gb, cx - bl + 0.06, cx + bl - 0.06, cy - bw - 0.02, cy + bw + 0.02,
       z0 + 0.50, z0 + 0.84, body)
    # 前后收头
    _b(gb, cx + bl - 0.04, cx + bl + 0.02, cy - bw + 0.10, cy + bw - 0.10,
       z0 + 0.30, z0 + 0.72, body)
    _b(gb, cx - bl - 0.02, cx - bl + 0.04, cy - bw + 0.10, cy + bw - 0.10,
       z0 + 0.30, z0 + 0.74, body)
    # 玻璃舱
    _b(gb, cx - 0.94, cx + 1.16, cy - 0.80, cy + 0.80, z0 + 0.82, z0 + 1.30,
       "M_GlassClear")
    # A/C 柱
    for sx in (-0.94, 1.16):
        _b(gb, cx + sx - 0.03, cx + sx + 0.03, cy - 0.82, cy + 0.82,
           z0 + 0.80, z0 + 1.32, body)
    # 车顶
    _b(gb, cx - 0.88, cx + 1.10, cy - 0.74, cy + 0.74, z0 + 1.28, z0 + 1.36, body)
    _b(gb, cx - 0.30, cx + 0.60, cy - 0.60, cy + 0.60, z0 + 1.36, z0 + 1.39, body)
    # 灯
    for sy in (-1, 1):
        _b(gb, cx + bl - 0.14, cx + bl + 0.01, cy + sy * 0.56 - 0.11,
           cy + sy * 0.56 + 0.11, z0 + 0.62, z0 + 0.74, "M_Uplight")
        _b(gb, cx - bl - 0.01, cx - bl + 0.13, cy + sy * 0.56 - 0.13,
           cy + sy * 0.56 + 0.13, z0 + 0.62, z0 + 0.76, "M_EmberGlow")
        # 后视镜
        _b(gb, cx + 0.62, cx + 0.74, cy + sy * (bw + 0.06) - 0.05,
           cy + sy * (bw + 0.06) + 0.05, z0 + 0.92, z0 + 1.02, "M_SteelDarker")
    # 前后保险杠 / 牌照
    _b(gb, cx - bl - 0.02, cx + bl + 0.02, cy - bw + 0.02, cy + bw - 0.02,
       z0 + 0.16, z0 + 0.24, "M_SteelDarker")
    _b(gb, cx - bl - 0.035, cx - bl - 0.01, cy - 0.22, cy + 0.22, z0 + 0.40,
       z0 + 0.54, "M_RoadLine")
    _b(gb, cx + bl + 0.01, cx + bl + 0.035, cy - 0.22, cy + 0.22, z0 + 0.40,
       z0 + 0.54, "M_RoadLine")
    return


def _street_lamp(gb, x, y):
    gb.cyl(0.16, 0.05, (x, y, 0.10), seg=12, mat="M_SteelDarker")
    gb.cyl(0.055, 2.25, (x, y, 1.15), seg=12, mat="M_SteelDarker")
    gb.cyl(0.075, 0.10, (x, y, 0.22), seg=12, mat="M_SteelDarker")
    # 弯臂 + 灯具
    _b(gb, x - 0.02, x + 0.62, y - 0.035, y + 0.035, 2.30, 2.37, "M_SteelDarker")
    _b(gb, x + 0.44, x + 0.78, y - 0.10, y + 0.10, 2.20, 2.30, "M_Fascia")
    _b(gb, x + 0.46, x + 0.76, y - 0.08, y + 0.08, 2.175, 2.20, "M_Uplight")


def _street(gb, rng):
    """人行道 + 路缘石 + 2 辆车 + 路灯 + 墙外绿篱。"""
    # 人行道（0.62 方砖）
    nx = 30
    for i in range(nx):
        ax = -9.20 + i * 0.615
        _b(gb, ax, ax + 0.605, -15.52, -14.84, 0.0, 0.075, "M_PaveGrey")
    # 路缘石
    _b(gb, -9.42, 9.42, -14.84, -14.66, 0.0, 0.14, "M_GraniteEdge")
    _b(gb, -9.42, 9.42, -15.60, -15.52, 0.0, 0.10, "M_GraniteEdge")
    # 墙外低绿篱
    for (a, b) in ((-9.18, -1.98), (1.98, 9.18)):
        _b(gb, a, b, -14.60, -14.24, 0.0, 0.16, "M_Soil")
        n = int((b - a) / 0.42)
        for k in range(n):
            px = a + (k + 0.5) * (b - a) / n
            gb.sphere(0.24, (px, -14.42, 0.16), seg=8, rings=5, mat="M_LeafBox",
                      scale=(1.25, 1.0, 0.85))
    # 2 辆停放车（参数化真比例车，见 lib/cars.py）
    cars.parking(gb, 4.60, -17.15, rot=math.radians(-90), kind="suv")
    cars.parking(gb, -3.10, -17.15, rot=math.radians(90), kind="sedan")
    # 路灯
    _street_lamp(gb, -7.40, -15.18)
    # 行道树池（远景层次）
    _b(gb, -9.10, -8.20, -15.50, -14.86, 0.0, 0.10, "M_Soil")


# ================================================================ 主入口
def build(ctx):
    ctx.use("COURT")
    rng = random.Random(7)

    g = GB("court_paving")
    _paving(g, rng)
    _zen(g, rng)
    ctx.mesh(g, "COURT_Paving")

    g = GB("court_deck")
    _deck(g, rng)
    _kitchen(g)
    _lounge(g, rng)
    ctx.mesh(g, "COURT_Deck")

    g = GB("court_pergola")
    _pergola(g, rng)
    ctx.mesh(g, "COURT_Pergola")

    g = GB("court_water")
    _water(g, rng)
    ctx.mesh(g, "COURT_Water")

    g = GB("court_planting")
    _lawn_beds(g, rng, ctx)
    _wall_beds(g, rng, ctx)
    # 枯山水焦点：真针叶树（fir_tree_01 自然高 18.9 m，压到 2.6 m 当造型松）
    _plant(ctx, "fir_tree_01", "zen_pine", 4.55, -11.05, h=2.6,
           z=Z_BED + 0.16)
    ctx.mesh(g, "COURT_Planting")

    g = GB("court_fence")
    _fence(g, rng)
    ctx.mesh(g, "COURT_Fence")

    g = GB("court_lights")
    _lights(g, rng)
    ctx.mesh(g, "COURT_Lights")

    g = GB("court_street")
    _street(g, rng)
    ctx.mesh(g, "COURT_Street")
