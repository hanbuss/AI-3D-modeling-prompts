# -*- coding: utf-8 -*-
"""室内家具软装 —— 每间房按 LAYOUT.md §3 的 X/Y 盒与楼层 Z 带布置。

约定
- 只写几何：所有图元走 lib.furni 既有构件，累积进一个 GB，每间房出一个 mesh。
- 家具局部原点在落地中心，Z 向上；落位统一用 place()。
- 房间内地坪 z：1F 0.15 / 2F 3.60 / 3F 6.90；露台 6.90。
- 材质名只允许来自 lib/mats.py 与 lib/mats2.py。
"""
import math
import random
from mathutils import Matrix, Vector

from .kit import GB, D, TAU
from . import furni as F
from . import nature as N

RNG = random.Random(20261106)

# ---------------------------------------------------------------- 楼层基准
# 楼面结构标高 0.15 / 3.60 / 6.90；面层 +0.02，家具坐落在面层上。
SLAB1, SLAB2, SLAB3, SLABT = 0.15, 3.60, 6.90, 6.90
FT = 0.02          # 面层厚
Z1 = SLAB1 + FT    # 0.17
Z2 = SLAB2 + FT    # 3.62
Z3 = SLAB3 + FT    # 6.92
ZT = SLABT + FT    # 露台 6.92
# 各层天花面（楼面 + 层高）
CH1 = 3.30
CH2 = 6.60
CH3 = 9.90


# ---------------------------------------------------------------- 落位工具
def place(gb, x, y, lvl=0.0, rot=0.0, fn=None, *a, **kw):
    """在 (x,y,lvl) 处、绕 Z 转 rot 度调用 fn(gb, ...)。

    参数名不叫 z：furni 的多个构件自身带 z 形参，同名会在调用处重复赋值。
    """
    with gb.frame(Matrix.Translation((x, y, lvl)) @ Matrix.Rotation(D(rot), 4, "Z")):
        fn(gb, *a, **kw)


def floor_plane(gb, x0, x1, y0, y1, z, mat):
    """房间面层：从结构板顶铺到 z（家具落座标高），2 cm 厚。"""
    gb.boxb(((x0, x1), (y0, y1), (z - FT, z)), mat=mat)


def skirt(gb, x0, x1, y0, y1, z, h=0.075, mat="M_PlasterWhite", t=0.018):
    """踢脚线：沿矩形四边各一条，往内收 t。"""
    gb.boxb(((x0 + t, x1 - t), (y0 + t, y0 + t + 0.012), (z, z + h)), mat=mat)
    gb.boxb(((x0 + t, x1 - t), (y1 - t - 0.012, y1 - t), (z, z + h)), mat=mat)
    gb.boxb(((x0 + t, x0 + t + 0.012), (y0 + t, y1 - t), (z, z + h)), mat=mat)
    gb.boxb(((x1 - t - 0.012, x1 - t), (y0 + t, y1 - t), (z, z + h)), mat=mat)


def downlight(gb, x, y, z_ceil, r=0.075):
    """嵌入式筒灯：深色盘 + 发光面。"""
    gb.cyl(r, 0.022, (x, y, z_ceil - 0.011), seg=18, mat="M_MetalBlack")
    gb.cyl(r * 0.80, 0.004, (x, y, z_ceil - 0.022), seg=18, mat="M_LampShade")


def downlight_ring(gb, x0, x1, y0, y1, z_ceil, nx, ny, inset=0.85):
    """在房间内按网格撒筒灯。"""
    for i in range(nx):
        for j in range(ny):
            x = x0 + inset + (x1 - x0 - 2 * inset) * (i / max(1, nx - 1) if nx > 1 else 0.5)
            y = y0 + inset + (y1 - y0 - 2 * inset) * (j / max(1, ny - 1) if ny > 1 else 0.5)
            downlight(gb, x, y, z_ceil)


def curtain_pair(gb, x, y, rot, z, w=0.85, h=2.55):
    """窗边窗帘：两幅分挂在两侧。"""
    for s in (-1, 1):
        dx = math.cos(D(rot)) * s * 0.0
        place(gb, x + s * w * 0.0, y, z, rot, F.curtain, w=w, h=h)


def art(gb, x, y, z, rot, w=1.1, h=0.78, mat="M_WoodDark", artm="M_Canvas"):
    """挂画：rot 决定朝向，画心贴墙。"""
    place(gb, x, y, z, rot, F.art_frame, w=w, h=h, mat=mat, art=artm)


def plant(gb, x, y, z, s=1.0, leaf="M_LeafGreen", big=False, seed=1):
    place(gb, x, y, z, 0, F.potted_plant, r=0.24 * s, h=0.42 * s, leaf=leaf, big=big)


# ================================================================ 1F
def build_foyer(ctx):
    """门厅 X −1.60…1.60, Y −1.50…4.20, z 0.15。"""
    gb = GB("INT_1F_Foyer")
    x0, x1, y0, y1 = -1.50, 1.50, -1.16, 4.10
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_OakFloor")
    skirt(gb, -1.50, 1.50, -1.20, 4.10, Z1)

    # 玄关柜 1.8×0.40×1.10（贴东墙）
    gb.boxb(((1.05, 1.45), (0.10, 1.90), (0.22, 1.02)), mat="M_Wood")
    gb.boxb(((1.03, 1.47), (0.10, 1.92), (1.02, 1.06)), mat="M_StoneLight")
    for i in range(2):
        gb.boxb(((1.05, 1.45), (0.16, 0.18), (0.30 + i * 0.30, 0.90 + i * 0.30)),
                mat="M_MetalGrey")
        gb.cyl(0.014, 0.20, (1.20, 0.175, 0.62 + i * 0.30), axis="X", seg=8,
               mat="M_Brass")
    # 柜面物件：托盘 + 钥匙 + 伞立
    gb.boxb(((1.10, 1.42), (0.28, 0.86), (1.06, 1.085)), mat="M_WoodDark")
    for i, (kx, ky) in enumerate(((1.18, 0.40), (1.30, 0.52), (1.22, 0.62))):
        gb.box((0.055, 0.018, 0.008), (kx, ky, 1.09), mat="M_Brass")
    gb.cyl(0.075, 0.10, (1.26, 1.60, 1.11), seg=16, mat="M_Celadon")
    gb.lathe([(0.035, 0), (0.05, 0.36), (0.06, 0.40)], seg=12,
             center=(1.26, 1.60, 1.12), mat="M_MetalBlack")
    # 伞立（地摆）
    gb.cyl(0.11, 0.46, (1.28, 2.10, 0.38), seg=18, mat="M_MetalBlack")
    for i in range(3):
        gb.cyl(0.014, 0.72, (1.28 + (i - 1) * 0.035, 2.10, 0.60), seg=6, mat="M_WoodDark")
    gb.sphere(0.05, (1.28, 2.10, 1.26), seg=8, rings=5, mat="M_Wood")  # 折断一次

    # 换鞋凳
    place(gb, -0.72, -0.55, Z1, 0, F.bench, w=1.05, d=0.40, mat="M_Wood")
    gb.box((0.70, 0.34, 0.09), (-0.72, -0.55, 0.62), mat="M_FabricOat")

    # 全身镜（贴西墙）
    gb.boxb(((-1.49, -1.455), (0.20, 1.05), (0.20, 2.25)), mat="M_WoodDark")
    gb.boxb(((-1.454, -1.440), (0.26, 0.99), (0.26, 2.19)), mat="M_Mirror")
    gb.boxb(((-1.49, -1.43), (0.20, 1.05), (2.25, 2.28)), mat="M_Brass")

    # 衣帽钩
    gb.boxb(((-1.45, -1.40), (1.30, 2.20), (1.60, 1.70)), mat="M_WoodDark")
    for i in range(4):
        gb.cyl(0.014, 0.11, (-1.38, 1.42 + i * 0.24, 1.60), axis="X", seg=8,
               mat="M_Brass")
    # 挂着的外套
    gb.boxb(((-1.36, -1.24), (1.44, 1.74), (1.10, 1.62)), mat="M_FabricGrey")
    gb.boxb(((-1.36, -1.24), (1.80, 2.04), (1.16, 1.60)), mat="M_FabricInk")

    # 门垫
    gb.boxb(((-0.62, 0.62), (-1.14, 0.16), (Z1, Z1 + 0.016)), mat="M_FabricGrey")
    for i in range(7):
        gb.boxb(((-0.56, 0.56), (-1.08 + i * 0.18, -1.02 + i * 0.18), (Z1 + 0.016, Z1 + 0.018)),
                mat="M_FabricOat")

    # 两盏吊灯（沿门厅中线，压缩下垂）
    for yy in (0.55, 2.55):
        place(gb, 0.0, yy, CH1, 0, F.pendant, z=0.0, drop=0.42, r=0.19)

    # 一株高植
    plant(gb, -1.10, 3.35, Z1, s=1.15, big=True, leaf="M_LeafDeep")

    # 筒灯
    downlight_ring(gb, -1.50, 1.50, -1.16, 4.10, CH1, 2, 4)

    ctx.mesh(gb, "INT_1F_Foyer")
    ctx.room("foyer", "门厅", "Entrance Foyer", 1, (0.0, Z1, 1.35), 22,
             "玄关柜＋换鞋凳＋全身镜，两盏小吊灯压着窄长的入户轴线。")


def build_living(ctx):
    """客厅 X −7.20…−1.60, Y −1.50…6.40, z 0.15；电视墙贴西墙。"""
    gb = GB("INT_1F_Living")
    x0, x1, y0, y1 = -6.88, -1.70, -1.16, 6.30
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_OakFloor")
    skirt(gb, -6.90, -1.70, -1.20, 6.30, Z1)

    # --- 电视墙（西墙 2.8 m，沿 Y 走）---
    gb.boxb(((-6.88, -6.74), (0.60, 3.40), (Z1, CH1 - 0.30)), mat="M_WoodDark")
    for i in range(10):
        yy = 0.72 + i * 0.28
        gb.boxb(((-6.72, -6.68), (yy, yy + 0.055), (Z1, CH1 - 0.30)), mat="M_Wood")
    # 悬浮橡木柜
    gb.boxb(((-6.88, -6.42), (0.62, 3.38), (0.42, 0.76)), mat="M_WoodLight")
    gb.boxb(((-6.90, -6.40), (0.60, 3.40), (0.76, 0.80)), mat="M_StoneLight")
    for i in range(5):
        yy = 0.68 + i * 0.54
        gb.boxb(((-6.44, -6.40), (yy, yy + 0.012), (0.46, 0.72)), mat="M_MetalGrey")
        gb.cyl(0.012, 0.14, (-6.395, yy + 0.27, 0.59), axis="X", seg=8, mat="M_Brass")
    # 电视 1.6 m + 声吧
    gb.boxb(((-6.76, -6.70), (0.96, 3.04), (1.16, 2.10)), mat="M_MetalBlack")
    gb.boxb(((-6.715, -6.702), (1.02, 2.98), (1.22, 2.04)), mat="M_Screen")
    gb.boxb(((-6.64, -6.46), (1.30, 2.70), (0.80, 0.88)), mat="M_MetalBlack")
    # 三层搁物板
    for i, zz in enumerate((1.05, 1.55, 2.05)):
        yy0 = 2.55 if i % 2 == 0 else 3.00
        gb.boxb(((-6.84, -6.54), (yy0, yy0 + 0.42), (zz, zz + 0.035)), mat="M_Wood")
    gb.lathe([(0.05, 0), (0.08, 0.06), (0.075, 0.20), (0.04, 0.26)], seg=14,
             center=(-6.69, 2.74, 2.085), mat="M_Ceramic")
    gb.box((0.20, 0.16, 0.14), (-6.69, 3.20, 1.62), mat="M_BookSpineB")
    gb.box((0.16, 0.14, 0.18), (-6.69, 3.18, 1.12), mat="M_CeramicDark")

    # --- 沙发组：三人沙发朝西 ---
    place(gb, -4.55, 2.05, Z1, 0, F.sofa, w=2.50, d=0.95, seats=3, pillows=True)
    # 编织搭毯挂在扶手
    gb.box((0.09, 0.62, 0.30), (-3.32, 1.80, 0.60), mat="M_FabricRust")
    gb.box((0.07, 0.52, 0.06), (-3.31, 1.80, 0.78), mat="M_FabricOat")

    # 两把休闲椅（斜对沙发）
    place(gb, -4.95, 0.55, Z1, 158, F.armchair, w=0.86, d=0.86, mat="M_Leather")
    place(gb, -4.85, 3.60, Z1, -160, F.armchair, w=0.86, d=0.86, mat="M_FabricGrey")

    # 地毯 3.2×2.4
    place(gb, -5.30, 2.10, Z1, 0, F.rug, w=2.40, d=3.20, mat="M_Rug",
          border="M_FabricGrey")

    # 茶几 1.4 m
    place(gb, -5.55, 2.10, Z1, 90, F.coffee_table, w=1.40, d=0.82, h=0.38)
    # 茶几上再补：杯子 + 摊开的书 + 碗
    gb.cyl(0.045, 0.09, (-5.55, 1.55, Z1 + 0.47), seg=14, mat="M_Ceramic")
    gb.cyl(0.035, 0.012, (-5.55, 1.55, Z1 + 0.48), seg=12, mat="M_WoodDark")
    gb.box((0.26, 0.20, 0.012), (-5.55, 2.62, Z1 + 0.395), mat="M_BookPage")
    gb.box((0.24, 0.18, 0.010), (-5.53, 2.66, Z1 + 0.408), mat="M_BookSpine")

    # 边几 ×2
    place(gb, -3.05, 2.05, Z1, 0, F.side_table, r=0.26, h=0.52)
    place(gb, -5.05, 4.45, Z1, 0, F.side_table, r=0.24, h=0.52)
    gb.lathe([(0.055, 0), (0.085, 0.07), (0.09, 0.16), (0.05, 0.20)], seg=14,
             center=(-3.05, 2.05, Z1 + 0.54), mat="M_Ceramic")

    # 两盏落地灯
    place(gb, -6.10, 4.55, Z1, 0, F.floor_lamp, h=1.66)
    place(gb, -2.10, 0.30, Z1, 0, F.floor_lamp, h=1.58)

    # 书架（贴南墙，靠东）
    place(gb, -2.35, -1.04, Z1, 180, F.bookshelf, w=1.30, d=0.32, h=2.10, shelves=5,
          seed=11)

    # 4 盏筒灯
    for xx in (-6.10, -4.30, -2.60):
        downlight(gb, xx, 1.10, CH1)
        downlight(gb, xx, 3.30, CH1)
    downlight(gb, -4.60, 5.30, CH1)
    downlight(gb, -3.20, 5.30, CH1)

    # 窗帘（南向落地玻璃内侧）
    for xx in (-6.15, -5.45, -3.10, -2.45):
        place(gb, xx, -1.14, Z1, 0, F.curtain, w=0.80, h=2.60, mat="M_Linen")

    # 大植
    plant(gb, -6.20, 5.45, Z1, s=1.25, big=True, leaf="M_LeafDeep")
    # 两幅挂画（东墙内侧朝西？——贴南墙）
    art(gb, -5.95, -1.17, 1.65, 0, w=1.10, h=0.76, mat="M_WoodDark", artm="M_Canvas")
    art(gb, -3.30, 4.05, 1.70, 180, w=0.96, h=1.30, mat="M_WoodDark", artm="M_Silk")

    ctx.mesh(gb, "INT_1F_Living")
    ctx.room("living", "客厅", "Living Room", 1, (-4.40, Z1, 2.45), 43,
             "三人沙发＋两把休闲椅围一张 1.4 m 茶几，西墙木格栅电视墙与悬浮橡木柜。")


def build_dining(ctx):
    """餐厅 X 1.60…7.20, Y −1.50…4.00, z 0.15。"""
    gb = GB("INT_1F_Dining")
    x0, x1, y0, y1 = 1.70, 6.88, -1.16, 3.90
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_OakFloor")
    skirt(gb, 1.70, 6.90, -1.20, 3.90, Z1)

    # 8 人长桌 2.6×1.05
    place(gb, 4.35, 1.30, Z1, 0, F.dining_table, w=2.60, d=1.05, h=0.75)

    # 8 把椅子：南/北各三把，东西各一把；两把拉出 15°
    chair_spots = [
        (3.35, 0.58, 0), (4.35, 0.58, 0), (5.35, 0.58, 0),
        (3.35, 2.02, 180), (4.35, 2.02, 180), (5.35, 2.02, 180),
        (2.92, 1.30, 90), (5.78, 1.30, -90),
    ]
    for i, (cx, cy, cr) in enumerate(chair_spots):
        rot = cr + (16 if i == 1 else -13 if i == 5 else 0)
        place(gb, cx, cy, Z1, rot, F.dining_chair, mat="M_Wood", seat="M_FabricOat")

    # 桌旗 + 2 烛台 + 碗 + 8 套位餐具
    gb.boxb(((3.10, 5.60), (1.16, 1.44), (Z1 + 0.78, Z1 + 0.792)), mat="M_Linen")
    for sx in (3.40, 5.30):
        gb.cyl(0.045, 0.03, (sx, 1.30, Z1 + 0.806), seg=14, mat="M_Brass")
        gb.cyl(0.016, 0.24, (sx, 1.30, Z1 + 0.93), seg=10, mat="M_Brass")
        gb.cyl(0.012, 0.10, (sx, 1.30, Z1 + 1.10), seg=8, mat="M_Ceramic")
    gb.lathe([(0.10, 0), (0.15, 0.05), (0.16, 0.10), (0.145, 0.12)], seg=20,
             center=(4.35, 1.30, Z1 + 0.795), mat="M_Celadon")
    for i in range(4):
        a = TAU * i / 4
        gb.sphere(0.035, (4.35 + math.cos(a) * 0.06, 1.30 + math.sin(a) * 0.06,
                          Z1 + 0.885), seg=8, rings=5, mat="M_LeafOlive")
    # 位餐具：每人一个盘 + 一副刀叉
    seats = [(3.35, 0.86), (4.35, 0.86), (5.35, 0.86),
             (3.35, 1.74), (4.35, 1.74), (5.35, 1.74),
             (3.02, 1.30), (5.68, 1.30)]
    for (px, py) in seats:
        gb.cyl(0.13, 0.014, (px, py, Z1 + 0.797), seg=20, mat="M_Porcelain")
        gb.cyl(0.095, 0.008, (px, py, Z1 + 0.806), seg=18, mat="M_Ceramic")
    for i, (px, py) in enumerate(seats[:6]):
        for s in (-1, 1):
            gb.box((0.012, 0.135, 0.008), (px + s * 0.175, py, Z1 + 0.80),
                   mat="M_Chrome")

    # 线性吊灯（餐桌上方，两段）
    gb.boxb(((3.05, 5.65), (1.24, 1.36), (2.06, 2.14)), mat="M_MetalBlack")
    for sx in (3.30, 5.40):
        gb.cyl(0.008, 0.72, (sx, 1.30, 2.50), seg=6, mat="M_MetalBlack")
    gb.boxb(((3.12, 5.58), (1.26, 1.34), (2.045, 2.055)), mat="M_LampShade")

    # 地毯
    place(gb, 4.35, 1.30, Z1, 0, F.rug, w=3.60, d=2.70, mat="M_Rug", border="M_FabricGrey")

    # 边柜 2.0 m（贴东墙）
    gb.boxb(((6.54, 6.88), (0.35, 2.35), (0.20, 0.86)), mat="M_Wood")
    gb.boxb(((6.52, 6.90), (0.33, 2.37), (0.86, 0.90)), mat="M_StoneLight")
    for i in range(3):
        yy = 0.45 + i * 0.66
        gb.boxb(((6.52, 6.55), (yy, yy + 0.008), (0.24, 0.82)), mat="M_MetalGrey")
    # 边柜三件物：陶罐、书立、香薰
    gb.lathe([(0.08, 0), (0.13, 0.10), (0.14, 0.26), (0.09, 0.34)], seg=18,
             center=(6.70, 0.70, Z1 + 0.90), mat="M_Ceramic")
    gb.box((0.22, 0.16, 0.20), (6.70, 1.45, Z1 + 1.00), mat="M_BookSpine")
    gb.cyl(0.055, 0.14, (6.70, 2.05, Z1 + 0.97), seg=14, mat="M_Celadon")

    # 墙面挂画 + 一株植物
    art(gb, 4.35, -1.17, 1.85, 0, w=1.60, h=0.92, mat="M_WoodDark", artm="M_Canvas")
    plant(gb, 1.95, -0.86, Z1, s=0.95, leaf="M_LeafGreen")

    # 筒灯
    downlight_ring(gb, 1.74, 6.86, -1.14, 3.86, CH1, 3, 3)

    ctx.mesh(gb, "INT_1F_Dining")
    ctx.room("dining", "餐厅", "Dining Room", 1, (4.40, Z1, 1.25), 29,
             "2.6 m 橡木长桌配八把餐椅（两把拉出），线性吊灯压桌，东墙两米边柜。")


def build_kitchen(ctx):
    """厨房 X 1.60…7.20, Y 4.00…7.60, z 0.15；L 形沿东墙 + 北墙。"""
    gb = GB("INT_1F_Kitchen")
    x0, x1, y0, y1 = 1.72, 6.88, 4.12, 7.48
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_TileFloorGrey")
    skirt(gb, 1.70, 6.90, 4.10, 7.50, Z1, h=0.06, mat="M_StoneDark")

    # --- L 形：北墙 3.0 m + 东墙 2.4 m 转角 ---
    # 北墙段：贴 Y=7.52 往南出 0.62
    gb.boxb(((2.30, 5.35), (6.90, 7.50), (Z1 + 0.10, Z1 + 0.88)), mat="M_WoodLight")
    gb.boxb(((2.28, 5.37), (6.88, 7.52), (Z1 + 0.88, Z1 + 0.925)), mat="M_MarbleWhite")
    gb.boxb(((2.30, 5.35), (7.44, 7.50), (Z1, Z1 + 0.12)), mat="M_MetalBlack")
    # 东墙段：贴 X=7.12 往西出 0.62
    gb.boxb(((6.24, 6.86), (4.55, 6.90), (Z1 + 0.10, Z1 + 0.88)), mat="M_WoodLight")
    gb.boxb(((6.22, 6.88), (4.53, 6.92), (Z1 + 0.88, Z1 + 0.925)), mat="M_MarbleWhite")
    gb.boxb(((6.80, 6.86), (4.55, 6.90), (Z1, Z1 + 0.12)), mat="M_MetalBlack")

    # 14 樘门板 + 拉手（北 8 + 东 6）
    for i in range(8):
        xx = 2.36 + i * 0.372
        gb.boxb(((xx, xx + 0.008), (6.895, 6.905), (Z1 + 0.14, Z1 + 0.84)),
                mat="M_MetalGrey")
        gb.boxb(((xx + 0.10, xx + 0.24), (6.87, 6.885), (Z1 + 0.74, Z1 + 0.755)),
                mat="M_Brass")
    for i in range(6):
        yy = 4.60 + i * 0.372
        gb.boxb(((6.49, 6.50), (yy, yy + 0.008), (Z1 + 0.14, Z1 + 0.84)),
                mat="M_MetalGrey")
        gb.boxb(((6.465, 6.48), (yy + 0.10, yy + 0.24), (Z1 + 0.74, Z1 + 0.755)),
                mat="M_Brass")

    # 吊柜 + 背板
    gb.boxb(((2.30, 5.35), (7.10, 7.50), (Z1 + 1.46, Z1 + 2.18)), mat="M_WoodLight")
    for i in range(8):
        xx = 2.36 + i * 0.372
        gb.boxb(((xx, xx + 0.008), (7.09, 7.10), (Z1 + 1.48, Z1 + 2.16)),
                mat="M_MetalGrey")
    gb.boxb(((2.30, 5.35), (7.46, 7.50), (Z1 + 0.94, Z1 + 1.44)), mat="M_MarbleGrey")
    # 东墙吊柜
    gb.boxb(((6.62, 6.86), (4.55, 6.40), (Z1 + 1.46, Z1 + 2.18)), mat="M_WoodLight")
    gb.boxb(((6.48, 6.52), (4.55, 6.40), (Z1 + 0.94, Z1 + 1.44)), mat="M_MarbleGrey")

    # 水槽 + 龙头（北墙段）
    gb.boxb(((3.05, 3.75), (6.96, 7.34), (Z1 + 0.90, Z1 + 0.925)), mat="M_MetalGrey")
    gb.boxb(((3.12, 3.68), (7.02, 7.28), (Z1 + 0.90, Z1 + 0.917)), mat="M_StoneDark")
    gb.cyl(0.018, 0.30, (3.40, 7.32, Z1 + 1.08), seg=10, mat="M_Chrome")
    gb.cyl(0.014, 0.16, (3.40, 7.24, Z1 + 1.23), axis="Y", seg=8, mat="M_Chrome")
    # 灶台 + 油烟机（东墙段）
    gb.boxb(((6.28, 6.82), (5.05, 5.75), (Z1 + 0.925, Z1 + 0.945)), mat="M_MetalBlack")
    for (dx, dy) in ((-0.13, -0.16), (0.13, -0.16), (-0.13, 0.16), (0.13, 0.16)):
        gb.cyl(0.055, 0.012, (6.55 + dx, 5.40 + dy, Z1 + 0.952), seg=12, mat="M_MetalGrey")
    gb.boxb(((6.34, 6.84), (5.00, 5.80), (Z1 + 1.90, Z1 + 2.06)), mat="M_MetalGrey")
    gb.boxb(((6.48, 6.82), (5.18, 5.62), (Z1 + 2.06, Z1 + 2.52)), mat="M_MetalGrey")

    # --- 中岛 2.6 m + 3 凳 ---
    place(gb, 4.35, 5.35, Z1, 0, F.island, w=2.60, d=0.94, mat="M_WoodLight")
    for dx in (-0.95, 0.0, 0.95):
        gb.cyl(0.035, 0.62, (4.35 + dx, 4.90, Z1 + 0.31), seg=10, mat="M_MetalBlack")
        gb.cyl(0.17, 0.055, (4.35 + dx, 4.90, Z1 + 0.64), seg=20, mat="M_Leather")
        gb.cyl(0.15, 0.02, (4.35 + dx, 4.90, Z1 + 0.20), seg=16, mat="M_MetalBlack")
    # 中岛两盏吊灯
    for dx in (-0.65, 0.65):
        place(gb, 4.35 + dx, 5.35, CH1, 0, F.pendant, z=0.0, drop=1.05, r=0.20)

    # 中岛台面：砧板、四碗、两罐、咖啡机、水壶、沥水架
    gb.boxb(((3.72, 4.20), (5.20, 5.50), (Z1 + 0.94, Z1 + 0.965)), mat="M_WoodPale")
    for i in range(4):
        gb.cyl(0.075, 0.055, (4.72 + (i % 2) * 0.19, 5.18 + (i // 2) * 0.20, Z1 + 0.97),
               seg=16, mat="M_Porcelain")
    for i, (jx, jy) in enumerate(((5.30, 5.16), (5.44, 5.42))):
        gb.cyl(0.055, 0.19, (jx, jy, Z1 + 1.06), seg=14, mat="M_Ceramic")
        gb.cyl(0.058, 0.02, (jx, jy, Z1 + 1.16), seg=14, mat="M_MetalBlack")
    gb.boxb(((5.52, 5.86), (5.10, 5.42), (Z1 + 0.94, Z1 + 1.28)), mat="M_MetalGrey")
    gb.boxb(((5.56, 5.82), (5.08, 5.10), (Z1 + 1.02, Z1 + 1.16)), mat="M_CeramicDark")
    place(gb, 3.30, 5.42, Z1 + 0.94, 0, F.dish_rack)
    # 咖啡机旁边的小托盘：水壶
    gb.lathe([(0.06, 0), (0.085, 0.05), (0.08, 0.16), (0.05, 0.19)], seg=16,
             center=(5.05, 5.36, Z1 + 0.94), mat="M_Chrome")

    # 冰箱（东北角）+ 烤箱塔
    gb.boxb(((2.30, 2.92), (7.00, 7.48), (Z1, Z1 + 1.92)), mat="M_MetalGrey")
    gb.boxb(((2.32, 2.90), (6.99, 7.00), (Z1 + 0.98, Z1 + 0.99)), mat="M_MetalBlack")
    gb.cyl(0.014, 0.30, (2.86, 6.985, Z1 + 1.30), axis="Z", seg=8, mat="M_Chrome")
    gb.boxb(((5.42, 6.10), (7.00, 7.48), (Z1, Z1 + 2.24)), mat="M_WoodLight")
    gb.boxb(((5.46, 6.06), (6.98, 7.00), (Z1 + 0.86, Z1 + 1.42)), mat="M_CeramicDark")
    gb.boxb(((5.48, 6.04), (6.965, 6.98), (Z1 + 0.92, Z1 + 1.36)), mat="M_Screen")
    gb.boxb(((5.50, 5.90), (6.97, 6.985), (Z1 + 1.54, Z1 + 1.565)), mat="M_Brass")

    # 北墙挂钩排
    for i in range(5):
        gb.cyl(0.010, 0.16, (2.90 + i * 0.20, 7.40, Z1 + 1.20), axis="Y", seg=6,
               mat="M_MetalGrey")

    # 筒灯
    downlight_ring(gb, 1.74, 6.86, 4.16, 7.44, CH1, 3, 2, inset=0.80)

    ctx.mesh(gb, "INT_1F_Kitchen")
    ctx.room("kitchen", "厨房", "Kitchen", 1, (4.35, Z1, 5.80), 20,
             "沿东墙与北墙的 L 形橱柜 5.4 m，2.6 m 岩板中岛配三只皮凳，两盏吊灯。")


def build_pantry(ctx):
    """储藏 X 1.60…4.40, Y 7.60…9.00, z 0.15。"""
    gb = GB("INT_1F_Pantry")
    x0, x1, y0, y1 = 1.70, 4.28, 7.70, 8.66
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_TileFloorGrey")
    skirt(gb, 1.70, 4.30, 7.70, 8.70, Z1, h=0.06, mat="M_StoneDark")

    # 4 组货架（两组贴西，两组贴北）
    for i, xx in enumerate((1.86, 2.62)):
        gb.boxb(((xx, xx + 0.60), (7.74, 8.66), (Z1, Z1 + 0.06)), mat="M_WoodDark")
        gb.boxb(((xx, xx + 0.60), (7.74, 8.66), (Z1 + 1.88, Z1 + 1.92)), mat="M_WoodDark")
        for s in (0, 1):
            gb.boxb(((xx + s * 0.545, xx + s * 0.575), (7.74, 8.66), (Z1, Z1 + 1.92)),
                    mat="M_MetalGrey")
        for lvl in range(4):
            zz = Z1 + 0.08 + lvl * 0.46
            gb.boxb(((xx, xx + 0.60), (7.74, 8.66), (zz, zz + 0.03)), mat="M_WoodLight")
    for j, yy in enumerate((7.80, 8.24)):
        gb.boxb(((3.50, 4.28), (yy, yy + 0.46), (Z1, Z1 + 1.86)), mat="M_WoodDark")
        for lvl in range(4):
            zz = Z1 + 0.08 + lvl * 0.44
            gb.boxb(((3.50, 4.28), (yy, yy + 0.46), (zz, zz + 0.03)), mat="M_WoodLight")

    # 12 个罐/盒，分布在架子上
    rng = random.Random(31)
    slots = []
    for i, xx in enumerate((1.86, 2.62)):
        for lvl in range(4):
            slots.append((xx + 0.30, 8.24, Z1 + 0.11 + lvl * 0.46))
    for j, yy in enumerate((7.80, 8.24)):
        for lvl in range(4):
            slots.append((3.89, yy + 0.23, Z1 + 0.11 + lvl * 0.44))
    for i, (sx, sy, sz) in enumerate(slots[:12]):
        hh = rng.uniform(0.14, 0.24)
        rr = rng.uniform(0.045, 0.075)
        if i % 3 == 2:
            gb.box((0.13, 0.11, hh), (sx, sy, sz + hh / 2),
                   mat=rng.choice(["M_Ceramic", "M_BookPage", "M_WoodDark"]))
        else:
            gb.cyl(rr, hh, (sx, sy, sz + hh / 2), seg=12,
                   mat=rng.choice(["M_Ceramic", "M_Celadon", "M_Porcelain"]))
            gb.cyl(rr * 1.06, 0.018, (sx, sy, sz + hh), seg=12, mat="M_MetalBlack")

    # 踏步梯
    gb.boxb(((2.10, 2.46), (8.28, 8.38), (Z1, Z1 + 0.44)), mat="M_MetalGrey")
    gb.boxb(((2.10, 2.46), (8.28, 8.38), (Z1 + 0.44, Z1 + 0.47)), mat="M_Wood")
    gb.boxb(((2.10, 2.46), (8.38, 8.48), (Z1, Z1 + 0.86)), mat="M_Wood")

    downlight(gb, 2.95, 8.10, CH1)
    downlight(gb, 2.95, 7.90, CH1)

    ctx.mesh(gb, "INT_1F_Pantry")
    ctx.room("pantry", "储藏", "Pantry", 1, (3.00, Z1, 8.10), 6,
             "四组通顶货架摆满玻璃罐与纸盒，角落靠一把两步梯。")


def build_wc(ctx):
    """客卫 X 4.40…7.20, Y 7.60…9.00, z 0.15。"""
    gb = GB("INT_1F_WC")
    x0, x1, y0, y1 = 4.32, 6.88, 7.70, 8.66
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_TileFloorGrey")
    skirt(gb, 4.30, 6.90, 7.70, 8.70, Z1, h=0.06, mat="M_StoneDark")

    # 马桶（贴北墙）
    place(gb, 5.05, 8.36, Z1, 180, F.toilet)
    # 台盆 + 镜
    place(gb, 6.40, 8.24, Z1, 0, F.basin, w=0.90, d=0.46, h=0.82)
    # 毛巾环
    gb.cyl(0.010, 0.34, (6.05, 7.66, Z1 + 1.20), axis="X", seg=8, mat="M_Chrome")
    for s in (-1, 1):
        gb.cyl(0.010, 0.07, (6.05 + s * 0.17, 7.63, Z1 + 1.17), axis="Y", seg=8,
               mat="M_Chrome")
    gb.box((0.24, 0.03, 0.26), (6.05, 7.62, Z1 + 1.06), mat="M_Linen")
    # 垃圾桶 + 小植
    place(gb, 4.62, 7.86, Z1, 0, F.trash_bin, r=0.12, h=0.30)
    plant(gb, 4.62, 8.36, Z1, s=0.55, leaf="M_LeafPale")
    place(gb, 6.20, 8.05, Z1, 0, F.bath_mat, w=0.62, d=0.42)

    downlight(gb, 5.20, 8.30, CH1)
    downlight(gb, 6.40, 8.30, CH1)

    ctx.mesh(gb, "INT_1F_WC")
    ctx.room("wc", "客卫", "Guest WC", 1, (5.80, Z1, 8.30), 6,
             "一线型客卫：马桶、小台盆与镜、毛巾环，灰色大板砖通铺。")


def build_service(ctx):
    """后勤 X −7.20…−1.60, Y 6.40…9.00, z 0.15。"""
    gb = GB("INT_1F_Service")
    x0, x1, y0, y1 = -6.88, -1.70, 6.52, 8.66
    floor_plane(gb, x0, x1, y0, y1, Z1, "M_TileFloorGrey")
    skirt(gb, -6.90, -1.70, 6.50, 8.70, Z1, h=0.06, mat="M_StoneDark")

    # 洗衣机 + 烘干机（东侧贴墙）
    place(gb, -2.35, 8.30, Z1, 180, F.washer)
    place(gb, -3.05, 8.30, Z1, 180, F.washer)
    gb.boxb(((-3.38, -2.02), (7.99, 8.61), (Z1 + 0.86, Z1 + 0.90)), mat="M_StoneLight")
    # 洗衣篮
    place(gb, -4.05, 8.45, Z1, 0, F.laundry_basket, r=0.24, h=0.44)
    # 水槽（贴北墙）
    gb.boxb(((-5.90, -4.90), (8.16, 8.66), (Z1, Z1 + 0.86)), mat="M_MetalGrey")
    gb.boxb(((-5.94, -4.86), (8.12, 8.68), (Z1 + 0.86, Z1 + 0.90)), mat="M_StoneDark")
    gb.boxb(((-5.78, -5.02), (8.22, 8.62), (Z1 + 0.90, Z1 + 0.915)), mat="M_MetalBlack")
    gb.cyl(0.016, 0.28, (-5.40, 8.62, Z1 + 1.06), seg=10, mat="M_Chrome")
    # 烫衣板（立在西墙）
    gb.boxb(((-6.88, -6.82), (7.10, 7.95), (Z1, Z1 + 1.42)), mat="M_WoodPale")
    gb.boxb(((-6.84, -6.80), (7.14, 7.91), (Z1 + 0.28, Z1 + 0.32)), mat="M_FabricGrey")
    gb.boxb(((-6.78, -6.72), (7.15, 7.20), (Z1, Z1 + 0.42)), mat="M_MetalGrey")
    # 六个储物箱（南侧地摆 + 上叠）
    boxes = [(-6.45, 6.72), (-5.85, 6.72), (-5.25, 6.72),
             (-6.45, 7.32), (-5.85, 7.32), (-5.25, 7.32)]
    for i, (bx, by) in enumerate(boxes):
        gb.boxb(((bx - 0.27, bx + 0.27), (by - 0.26, by + 0.26), (Z1, Z1 + 0.42)),
                mat="M_FabricGrey" if i % 2 else "M_CeramicDark")
        gb.boxb(((bx - 0.29, bx + 0.29), (by - 0.28, by + 0.28), (Z1 + 0.40, Z1 + 0.44)),
                mat="M_WoodDark")
        gb.boxb(((bx - 0.10, bx + 0.10), (by - 0.29, by - 0.27), (Z1 + 0.20, Z1 + 0.26)),
                mat="M_BookPage")
    # 四个挂钩 + 挂衣
    gb.boxb(((-2.30, -1.85), (8.34, 8.38), (Z1 + 1.55, Z1 + 1.65)), mat="M_WoodDark")
    for i in range(4):
        gb.cyl(0.012, 0.09, (-2.26 + i * 0.13, 8.30, Z1 + 1.60), axis="Y", seg=8,
               mat="M_Brass")
    gb.boxb(((-2.26, -2.14), (8.18, 8.28), (Z1 + 1.15, Z1 + 1.58)), mat="M_FabricInk")
    # 扫帚 + 拖把
    gb.cyl(0.014, 1.30, (-6.80, 8.58, Z1 + 0.65), seg=8, mat="M_WoodPale")
    gb.box((0.20, 0.06, 0.14), (-6.78, 8.58, Z1 + 0.10), mat="M_Bamboo")
    gb.cyl(0.014, 1.24, (-6.76, 8.50, Z1 + 0.62), seg=8, mat="M_MetalGrey")
    gb.box((0.14, 0.14, 0.10), (-6.76, 8.50, Z1 + 0.08), mat="M_MetalGrey")

    downlight(gb, -6.30, 7.70, CH1)
    downlight(gb, -4.20, 7.70, CH1)
    downlight(gb, -2.60, 7.70, CH1)

    ctx.mesh(gb, "INT_1F_Service")
    ctx.room("service", "后勤", "Utility & Laundry", 1, (-4.40, Z1, 7.70), 18,
             "洗衣烘干并排、水槽、六只储物箱，烫衣板靠在西墙，扫帚立在角上。")


def build_stair(ctx):
    """楼梯间 X −1.60…1.60, Y 4.20…9.00：只放一枚地毯收边与一具小边柜。"""
    gb = GB("INT_1F_Stair")
    floor_plane(gb, -1.50, 1.50, 4.30, 8.66, Z1, "M_OakFloor")
    # 踏步下地毯收边
    gb.boxb(((-1.15, 1.05), (4.30, 5.05), (Z1, Z1 + 0.015)), mat="M_Rug")
    # 立式小柜（贴东墙）
    gb.boxb(((1.05, 1.48), (5.30, 6.10), (Z1, Z1 + 0.78)), mat="M_Wood")
    gb.boxb(((1.03, 1.50), (5.28, 6.12), (Z1 + 0.78, Z1 + 0.82)), mat="M_StoneLight")
    gb.lathe([(0.06, 0), (0.10, 0.06), (0.11, 0.20), (0.06, 0.26)], seg=16,
             center=(1.26, 5.62, Z1 + 0.84), mat="M_Ceramic")
    downlight(gb, 0.0, 5.90, CH1)
    downlight(gb, 0.0, 7.60, CH1)
    ctx.mesh(gb, "INT_1F_Stair")


# ================================================================ 2F
def hang_clothes(gb, x, y0, y1, z_rail, n=12, seed=7):
    """衣柜通杆 + 一排挂衣：薄片状可读体块，宽度/颜色有变化。"""
    rng = random.Random(seed)
    mats_ = ["M_FabricCream", "M_FabricGrey", "M_FabricInk", "M_VelvetInk",
             "M_FabricRust", "M_Linen", "M_VelvetRust", "M_FabricOat"]
    span = y1 - y0
    for i in range(n):
        yy = y0 + span * (i + 0.5) / n
        ww = span / n * rng.uniform(0.55, 0.80)
        hh = rng.uniform(0.62, 0.95)
        gb.cyl(0.008, ww, (x, yy, z_rail - 0.055), axis="Y", seg=5, mat="M_Brass")
        gb.box((0.30, ww, hh), (x, yy, z_rail - 0.06 - hh / 2),
               mat=rng.choice(mats_))
        gb.box((0.315, ww * 0.92, 0.05), (x, yy, z_rail - 0.06 - hh * 0.42),
               mat="M_MetalBlack")


def shoe_pairs(gb, x, y, z, n=8, seed=5):
    """鞋架 + 8 双鞋（每双两只，鞋头朝外）。"""
    rng = random.Random(seed)
    gb.boxb(((x - 0.22, x + 0.22), (y - 0.55, y + 0.55), (z, z + 0.04)), mat="M_WoodDark")
    for lvl in range(2):
        zz = z + 0.04 + lvl * 0.30
        gb.boxb(((x - 0.20, x + 0.20), (y - 0.55, y + 0.55), (zz, zz + 0.025)),
                mat="M_WoodLight")
    for lvl in range(2):
        for i in range(4):
            yy = y - 0.42 + i * 0.28
            zz = z + 0.065 + lvl * 0.30
            for s in (-1, 1):
                gb.box((0.10, 0.22, 0.07), (x + s * 0.055, yy, zz + 0.035),
                       mat=rng.choice(["M_Leather", "M_FabricInk", "M_WoodDark",
                                       "M_FabricOat"]))


def build_master(ctx):
    """主卧 X −7.20…−1.60, Y −1.50…5.60, z 3.62。"""
    gb = GB("INT_2F_Master")
    floor_plane(gb, -6.88, -1.72, -1.16, 5.48, Z2, "M_OakFloor")
    skirt(gb, -6.90, -1.70, -1.20, 5.50, Z2)

    # 床：床头贴北墙（rot 180），1.9×2.1，床头板 + 床头柜 + 台灯随 bed() 一起出
    place(gb, -4.40, 4.34, Z2, 180, F.bed, w=1.90, l=2.10,
          mat="M_Linen", head="M_FabricGrey")
    # 两只额外抱枕
    for dx, m in ((-0.52, "M_VelvetRust"), (0.52, "M_VelvetInk")):
        place(gb, -4.40 + dx, 5.04, Z2 + 0.66, -8 if dx < 0 else 8,
              F.cushion, r=0.20, h=0.13, mat=m)
    # 床头柜上的书
    gb.box((0.26, 0.18, 0.032), (-3.11, 5.23, Z2 + 0.51), mat="M_BookPage")
    gb.box((0.27, 0.15, 0.028), (-3.11, 5.23, Z2 + 0.54), mat="M_BookSpine")

    # 床尾长凳 + 搭毯
    place(gb, -4.40, 2.98, Z2, 0, F.bench, w=1.75, d=0.42, mat="M_WoodDark")
    gb.box((1.60, 0.40, 0.08), (-4.40, 2.98, Z2 + 0.49), mat="M_FabricOat")
    gb.box((0.52, 0.36, 0.05), (-3.82, 2.98, Z2 + 0.55), mat="M_VelvetRust")

    # 地毯 3.4×2.6
    place(gb, -4.40, 3.05, Z2, 0, F.rug, w=3.40, d=2.60, mat="M_Rug",
          border="M_FabricGrey")

    # 斗柜（贴西墙）+ 台面物件
    gb.boxb(((-6.88, -6.34), (0.95, 2.55), (Z2, Z2 + 0.82)), mat="M_Wood")
    gb.boxb(((-6.90, -6.32), (0.93, 2.57), (Z2 + 0.82, Z2 + 0.86)), mat="M_StoneLight")
    for i in range(3):
        gb.boxb(((-6.36, -6.33), (1.02, 1.05), (Z2 + 0.08 + i * 0.25,
                                                 Z2 + 0.30 + i * 0.25)), mat="M_MetalGrey")
    for i in range(3):
        gb.cyl(0.012, 0.16, (-6.31, 1.75, Z2 + 0.19 + i * 0.25), axis="X", seg=8,
               mat="M_Brass")
    gb.lathe([(0.06, 0), (0.09, 0.08), (0.10, 0.22), (0.05, 0.30)], seg=18,
             center=(-6.61, 1.30, Z2 + 0.87), mat="M_Ceramic")
    gb.boxb(((-6.86, -6.56), (2.05, 2.35), (Z2 + 0.87, Z2 + 1.02)), mat="M_WoodDark")

    # 休闲椅（近南窗）
    place(gb, -6.15, 0.30, Z2, 138, F.armchair, w=0.86, d=0.86, mat="M_FabricGrey")
    place(gb, -2.35, 0.35, Z2, 0, F.floor_lamp, h=1.60)

    # 窗帘（南向落地窗内侧）
    for xx in (-6.42, -5.72, -3.05, -2.30):
        place(gb, xx, -1.14, Z2, 0, F.curtain, w=0.85, h=2.65, mat="M_Linen")

    # 拖鞋 + 两幅挂画
    place(gb, -3.35, 3.15, Z2, -22, F.slippers)
    art(gb, -4.40, 5.46, Z2 + 1.95, 180, w=1.55, h=0.85, mat="M_WoodDark", artm="M_Canvas")
    art(gb, -1.68, 1.85, Z2 + 1.55, 90, w=0.80, h=1.60, mat="M_WoodDark", artm="M_Silk")

    downlight_ring(gb, -6.86, -1.74, -1.16, 5.46, CH2, 3, 3, inset=0.95)

    ctx.mesh(gb, "INT_2F_Master")
    ctx.room("master", "主卧", "Master Bedroom", 2, (-4.40, Z2, 2.10), 37,
             "1.9 m 大床对南向落地窗，床头软包、床尾长凳，西墙斗柜与扶手椅。")


def build_master_bath(ctx):
    """主卫 X −7.20…−4.60, Y 5.60…9.00, z 3.62。"""
    gb = GB("INT_2F_MasterBath")
    floor_plane(gb, -6.88, -4.72, 5.54, 8.66, Z2, "M_TileFloorGrey")
    skirt(gb, -6.90, -4.70, 5.50, 8.70, Z2, h=0.06, mat="M_StoneDark")

    # 独立浴缸（贴北墙）
    place(gb, -6.05, 8.28, Z2, 0, F.bathtub, l=1.68, w=0.80, h=0.56)
    # 双台盆（贴西墙，两只盆各带镜）
    place(gb, -6.63, 6.25, Z2, 90, F.basin, w=0.88, d=0.50, h=0.82)
    place(gb, -6.63, 7.18, Z2, 90, F.basin, w=0.88, d=0.50, h=0.82)
    # 台面三瓶
    for i, (bx, by) in enumerate(((-6.56, 6.05), (-6.52, 7.35), (-6.60, 7.55))):
        gb.cyl(0.035, 0.15 + i * 0.03, (bx, by, Z2 + 0.90), seg=12,
               mat="M_Ceramic" if i % 2 else "M_Celadon")
    # 步入淋浴（玻璃隔断）
    place(gb, -5.20, 6.30, Z2, 0, F.shower, w=1.00, d=1.34, h=2.20)
    # 马桶
    place(gb, -4.98, 8.36, Z2, 180, F.toilet)
    # 毛巾杆 + 两条毛巾
    place(gb, -4.78, 7.62, Z2, 90, F.towel_bar, w=0.70, z=1.05, cloth="M_Linen")
    gb.box((0.34, 0.24, 0.09), (-4.86, 8.05, Z2 + 1.16), mat="M_Linen")
    gb.box((0.34, 0.24, 0.09), (-4.86, 8.05, Z2 + 1.26), mat="M_FabricOat")
    # 浴垫 + 小植
    place(gb, -6.00, 7.75, Z2, 0, F.bath_mat, w=0.72, d=0.48)
    plant(gb, -4.95, 5.95, Z2, s=0.70, leaf="M_LeafPale")

    downlight_ring(gb, -6.86, -4.74, 5.54, 8.64, CH2, 2, 3, inset=0.75)

    ctx.mesh(gb, "INT_2F_MasterBath")
    ctx.room("master_bath", "主卫", "Master Bath", 2, (-5.90, Z2, 7.30), 11,
             "独立浴缸、1.8 m 双台盆各带一面镜，玻璃隔断淋浴与马桶分列两端。")


def build_walkin(ctx):
    """衣帽间 X −4.60…−1.60, Y 5.60…9.00, z 3.62。"""
    gb = GB("INT_2F_WalkIn")
    floor_plane(gb, -4.68, -1.72, 5.54, 8.66, Z2, "M_OakFloor")
    skirt(gb, -4.70, -1.70, 5.50, 8.70, Z2, h=0.06, mat="M_StoneDark")

    # --- 第 1 组：西墙开敞挂衣（2.6 m，通顶 2.40）---
    gb.boxb(((-4.70, -4.68), (5.78, 8.38), (Z2, Z2 + 2.40)), mat="M_WoodDark")
    for yy in (5.78, 8.38):
        gb.boxb(((-4.68, -4.12), (yy, yy + 0.025), (Z2, Z2 + 2.40)), mat="M_Wood")
    gb.boxb(((-4.68, -4.12), (5.78, 8.38), (Z2 + 2.36, Z2 + 2.40)), mat="M_Wood")
    gb.boxb(((-4.68, -4.12), (5.78, 8.38), (Z2 + 1.96, Z2 + 2.00)), mat="M_WoodDark")
    gb.boxb(((-4.68, -4.12), (5.78, 8.38), (Z2 + 0.02, Z2 + 0.06)), mat="M_Wood")
    gb.cyl(0.012, 2.56, (-4.38, 7.08, Z2 + 1.90), axis="Y", seg=8, mat="M_Brass")
    hang_clothes(gb, -4.38, 5.86, 8.30, Z2 + 1.90, n=12, seed=13)
    # 顶层叠放
    for i in range(4):
        gb.box((0.36, 0.44, 0.16), (-4.38, 6.10 + i * 0.56, Z2 + 2.14),
               mat="M_FabricCream" if i % 2 else "M_FabricOat")

    # --- 第 2 组：东墙封闭衣柜（2.6 m）---
    place(gb, -2.02, 7.30, Z2, -90, F.wardrobe, w=2.60, d=0.62, h=2.45, mat="M_Wood")

    # --- 第 3 组：北墙封闭衣柜（1.5 m）---
    place(gb, -3.30, 8.38, Z2, 0, F.wardrobe, w=1.50, d=0.60, h=2.45, mat="M_Wood")

    # --- 2 组竖向搁板柱（东北角，叠陶瓷与包）---
    for i, yy in enumerate((8.44, 7.96)):
        gb.boxb(((-2.22, -1.72), (yy - 0.21, yy + 0.21), (Z2, Z2 + 2.20)), mat="M_Wood")
        for lvl in range(1, 5):
            zz = Z2 + lvl * 0.46
            gb.boxb(((-2.22, -1.72), (yy - 0.21, yy + 0.21), (zz, zz + 0.025)),
                    mat="M_WoodLight")
            gb.lathe([(0.05, 0), (0.075, 0.06), (0.07, 0.16), (0.04, 0.20)], seg=12,
                     center=(-1.97, yy, zz + 0.025),
                     mat="M_Ceramic" if (lvl + i) % 2 else "M_Celadon")

    # 鞋架（8 双）+ 长凳 + 镜 + 小地毯
    shoe_pairs(gb, -3.05, 6.35, Z2, n=8, seed=17)
    place(gb, -3.35, 7.55, Z2, 0, F.bench, w=1.35, d=0.42, mat="M_Wood")
    gb.box((1.30, 0.38, 0.07), (-3.35, 7.55, Z2 + 0.46), mat="M_FabricOat")
    gb.boxb(((-2.62, -1.72), (5.56, 5.60), (Z2 + 0.10, Z2 + 2.30)), mat="M_WoodDark")
    gb.boxb(((-2.58, -1.74), (5.60, 5.62), (Z2 + 0.16, Z2 + 2.24)), mat="M_Mirror")
    place(gb, -3.35, 6.95, Z2, 0, F.round_rug, r=0.90, mat="M_Rug")

    downlight_ring(gb, -4.68, -1.72, 5.54, 8.64, CH2, 2, 3, inset=0.70)

    ctx.mesh(gb, "INT_2F_WalkIn")
    ctx.room("walkin", "衣帽间", "Walk-in Closet", 2, (-3.10, Z2, 7.30), 11,
             "三面通顶衣柜，西侧开敞挂衣区十二件衣物成排，东北角双搁板柱收陶瓷。")


def build_landing(ctx):
    """过厅 X −1.60…1.60, Y −1.50…4.20, z 3.62。"""
    gb = GB("INT_2F_Landing")
    floor_plane(gb, -1.50, 1.50, -1.16, 4.10, Z2, "M_OakFloor")
    skirt(gb, -1.50, 1.50, -1.20, 4.10, Z2)

    # 窄边柜（贴东墙）+ 挂画 + 植物
    gb.boxb(((1.16, 1.52), (1.10, 2.90), (Z2, Z2 + 0.80)), mat="M_Wood")
    gb.boxb(((1.14, 1.54), (1.08, 2.92), (Z2 + 0.80, Z2 + 0.84)), mat="M_StoneLight")
    gb.lathe([(0.07, 0), (0.10, 0.07), (0.11, 0.22), (0.06, 0.30)], seg=16,
             center=(1.34, 1.55, Z2 + 0.85), mat="M_Ceramic")
    gb.box((0.20, 0.15, 0.14), (1.34, 2.45, Z2 + 0.92), mat="M_BookSpineB")
    art(gb, -1.66, 2.00, Z2 + 1.55, 90, w=0.76, h=1.10, mat="M_WoodDark", artm="M_Silk")
    plant(gb, -1.15, 3.55, Z2, s=0.95, leaf="M_LeafGreen")

    # 长条地毯
    gb.boxb(((-0.85, 0.85), (-1.05, 2.35), (Z2, Z2 + 0.014)), mat="M_Rug")
    for i in range(9):
        gb.boxb(((-0.78, 0.78), (-1.00 + i * 0.36, -0.96 + i * 0.36),
                 (Z2 + 0.014, Z2 + 0.016)), mat="M_FabricGrey")

    downlight(gb, 0.0, 0.20, CH2)
    downlight(gb, 0.0, 2.60, CH2)
    place(gb, 0.0, 1.55, CH2 - 0.07, 0, F.ceiling_lamp, z=0.0, r=0.30)

    ctx.mesh(gb, "INT_2F_Landing")
    ctx.room("landing", "过厅", "Landing", 2, (0.0, Z2, 1.30), 20,
             "楼梯厅：一条长地毯铺到窗前，东墙窄边柜压一幅绢面挂画。")


def build_bed2(ctx):
    """次卧 X 1.60…7.20, Y −1.50…4.00, z 3.62。"""
    gb = GB("INT_2F_Bed2")
    floor_plane(gb, 1.72, 6.88, -1.16, 3.88, Z2, "M_OakFloor")
    skirt(gb, 1.70, 6.90, -1.20, 3.90, Z2)

    # 1.5×2.0 双人床，床头贴北墙
    place(gb, 4.30, 2.85, Z2, 180, F.bed, w=1.50, l=2.00,
          mat="M_FabricOat", head="M_Linen")
    gb.box((0.24, 0.17, 0.03), (3.21, 3.69, Z2 + 0.47), mat="M_BookPage")
    # 书堆（床上 5 本，散放）
    place(gb, 5.05, 3.15, Z2 + 0.55, 12, F.book_stack, n=3, size=(0.24, 0.18), z0=0)

    # 书桌 + 椅（南窗下）
    place(gb, 2.70, -0.85, Z2, 180, F.desk, w=1.45, d=0.66, h=0.75)
    place(gb, 2.70, -0.30, Z2, 0, F.office_chair, mat="M_Leather")

    # 衣柜（贴西墙）
    place(gb, 1.92, 1.25, Z2, 90, F.wardrobe, w=2.00, d=0.60, h=2.40, mat="M_Wood")

    # 地毯 + 两幅画 + 背包 + 植物
    place(gb, 4.55, 1.55, Z2, 0, F.rug, w=2.60, d=1.90, mat="M_Rug",
          border="M_FabricGrey")
    art(gb, 4.30, 3.94, Z2 + 1.85, 180, w=1.20, h=0.70, mat="M_WoodDark", artm="M_Canvas")
    art(gb, 6.84, 1.60, Z2 + 1.45, -90, w=0.70, h=0.95, mat="M_WoodDark", artm="M_Silk")
    # 背包（靠在床尾）
    gb.box((0.30, 0.20, 0.42), (3.05, 2.02, Z2 + 0.21), mat="M_FabricInk")
    gb.box((0.26, 0.10, 0.10), (3.05, 2.10, Z2 + 0.42), mat="M_FabricGrey")
    gb.box((0.06, 0.05, 0.30), (2.92, 2.02, Z2 + 0.34), mat="M_FabricGrey")
    plant(gb, 6.52, -0.86, Z2, s=0.90, leaf="M_LeafGreen")

    # 5 本书竖立在桌上
    place(gb, 3.05, -1.10, Z2 + 0.775, 0, F.books_row, n=5, w=0.30, seed=23)

    downlight_ring(gb, 1.74, 6.86, -1.16, 3.86, CH2, 3, 2, inset=0.85)

    ctx.mesh(gb, "INT_2F_Bed2")
    ctx.room("bed2", "次卧", "Guest Bedroom", 2, (4.30, Z2, 1.20), 29,
             "1.5 m 双人床配软包墙，南窗下一张书桌，西墙整排衣柜。")


def build_bath2(ctx):
    """次卫 X 1.60…4.40, Y 4.00…6.80, z 3.62。"""
    gb = GB("INT_2F_Bath2")
    floor_plane(gb, 1.72, 4.28, 4.12, 6.68, Z2, "M_TileFloorGrey")
    skirt(gb, 1.70, 4.30, 4.10, 6.70, Z2, h=0.06, mat="M_StoneDark")

    place(gb, 4.10, 5.95, Z2, -90, F.basin, w=0.95, d=0.48, h=0.82)
    place(gb, 2.05, 6.52, Z2, 180, F.toilet)
    place(gb, 3.05, 4.70, Z2, 0, F.shower, w=1.30, d=1.20, h=2.20)
    place(gb, 1.86, 5.35, Z2, 90, F.towel_bar, w=0.62, z=1.05, cloth="M_Linen")
    gb.box((0.30, 0.22, 0.08), (1.82, 5.95, Z2 + 1.20), mat="M_FabricOat")
    place(gb, 3.05, 5.35, Z2, 0, F.bath_mat, w=0.68, d=0.44)
    place(gb, 2.02, 4.18, Z2, 0, F.trash_bin, r=0.11, h=0.28)

    downlight(gb, 2.85, 5.90, CH2)
    downlight(gb, 3.05, 4.75, CH2)

    ctx.mesh(gb, "INT_2F_Bath2")
    ctx.room("bath2", "次卫", "Bath 2", 2, (3.00, Z2, 5.40), 8,
             "台盆靠东墙、淋浴在窗侧，毛巾杆与浴垫把干湿区拉开。")


def build_laundry(ctx):
    """洗衣房 X 4.40…7.20, Y 4.00…6.80, z 3.62。"""
    gb = GB("INT_2F_Laundry")
    floor_plane(gb, 4.52, 6.88, 4.12, 6.68, Z2, "M_TileFloorGrey")
    skirt(gb, 4.50, 6.90, 4.10, 6.70, Z2, h=0.06, mat="M_StoneDark")

    # 洗烘并排（贴南墙，机门朝北）
    place(gb, 4.95, 4.55, Z2, 180, F.washer)
    place(gb, 5.65, 4.55, Z2, 180, F.washer)
    gb.boxb(((4.62, 5.98), (4.20, 4.88), (Z2 + 0.86, Z2 + 0.90)), mat="M_StoneLight")
    # 柜体 + 水槽（贴北墙）
    gb.boxb(((6.05, 6.88), (6.16, 6.68), (Z2, Z2 + 0.85)), mat="M_WoodLight")
    gb.boxb(((6.03, 6.90), (6.14, 6.70), (Z2 + 0.85, Z2 + 0.89)), mat="M_StoneLight")
    gb.boxb(((6.24, 6.88), (6.30, 6.64), (Z2 + 0.89, Z2 + 0.905)), mat="M_MetalGrey")
    gb.cyl(0.016, 0.26, (6.62, 6.68, Z2 + 1.03), seg=10, mat="M_Chrome")
    for i in range(2):
        gb.boxb(((6.22 + i * 0.30, 6.24 + i * 0.30), (6.19, 6.20), (Z2 + 0.10,
                                                                   Z2 + 0.80)),
                mat="M_MetalGrey")
    # 篮子 + 四个箱子
    place(gb, 4.72, 6.30, Z2, 0, F.laundry_basket, r=0.23, h=0.44)
    for i, (bx, by) in enumerate(((5.35, 6.42), (5.95, 6.42), (5.35, 5.85), (5.95, 5.85))):
        gb.boxb(((bx - 0.24, bx + 0.24), (by - 0.24, by + 0.24), (Z2, Z2 + 0.38)),
                mat="M_FabricGrey" if i % 2 else "M_Linen")
        gb.boxb(((bx - 0.26, bx + 0.26), (by - 0.26, by + 0.26), (Z2 + 0.36, Z2 + 0.40)),
                mat="M_WoodDark")

    downlight(gb, 5.80, 5.40, CH2)

    ctx.mesh(gb, "INT_2F_Laundry")
    ctx.room("laundry", "洗衣", "Laundry Room", 2, (5.80, Z2, 5.40), 8,
             "洗烘并排加一台水槽柜，四只布箱与藤篮堆在中间。")


def build_nook(ctx):
    """书房角 X 1.60…7.20, Y 6.80…9.00, z 3.62。"""
    gb = GB("INT_2F_Nook")
    floor_plane(gb, 1.72, 6.88, 6.92, 8.66, Z2, "M_OakFloor")
    skirt(gb, 1.70, 6.90, 6.90, 8.70, Z2)

    # 1.4 m 书桌贴北窗
    place(gb, 3.05, 8.36, Z2, 180, F.desk, w=1.40, d=0.62, h=0.75)
    place(gb, 3.05, 7.92, Z2, 0, F.office_chair, mat="M_FabricGrey")
    # 杯子 + 摊开的笔记本
    gb.cyl(0.042, 0.09, (3.48, 8.30, Z2 + 0.79), seg=14, mat="M_Ceramic")
    gb.box((0.26, 0.20, 0.012), (2.62, 8.36, Z2 + 0.776), mat="M_BookPage")
    # 两组搁板柱（带书）
    for i, xx in enumerate((5.55, 6.15)):
        gb.boxb(((xx - 0.24, xx + 0.24), (8.30, 8.66), (Z2, Z2 + 1.90)), mat="M_Wood")
        for lvl in range(1, 4):
            zz = Z2 + lvl * 0.46
            gb.boxb(((xx - 0.24, xx + 0.24), (8.28, 8.68), (zz, zz + 0.025)),
                    mat="M_WoodLight")
            place(gb, xx, 8.48, zz + 0.025, 0, F.books_row, n=6, w=0.36, seed=30 + i * 7 + lvl)
    # 地毯
    place(gb, 3.35, 7.55, Z2, 0, F.rug, w=2.40, d=1.30, mat="M_Rug",
          border="M_FabricGrey")

    downlight(gb, 3.05, 8.30, CH2)
    downlight(gb, 5.85, 8.30, CH2)
    downlight(gb, 3.05, 7.30, CH2)

    ctx.mesh(gb, "INT_2F_Nook")
    ctx.room("nook", "书房角", "Study Nook", 2, (4.40, Z2, 7.90), 9,
             "北窗下一张 1.4 m 书桌配办公椅，两组书架收书，垫一块小地毯。")


# ================================================================ 3F
def build_study(ctx):
    """书房 X −7.20…−1.60, Y −1.50…4.40, z 6.92。"""
    gb = GB("INT_3F_Study")
    floor_plane(gb, -6.88, -1.72, -1.16, 4.26, Z3, "M_OakFloor")
    skirt(gb, -6.90, -1.70, -1.20, 4.30, Z3)

    # 2.4 m 大书桌朝南窗
    place(gb, -4.40, -0.80, Z3, 180, F.desk, w=2.40, d=0.78, h=0.75)
    place(gb, -4.40, -0.02, Z3, 180, F.office_chair, mat="M_Leather")
    # 桌面上：笔电、纸叠、台灯已在 desk() 内，再补一摞纸与茶杯
    gb.box((0.30, 0.22, 0.05), (-3.20, -0.90, Z3 + 0.80), mat="M_BookPage")
    gb.box((0.28, 0.21, 0.04), (-3.18, -0.94, Z3 + 0.86), mat="M_Ceramic")
    gb.cyl(0.045, 0.09, (-5.35, -0.95, Z3 + 0.79), seg=14, mat="M_Celadon")
    # 两把客椅
    place(gb, -3.05, 0.95, Z3, 202, F.armchair, w=0.80, d=0.80, mat="M_FabricGrey")
    place(gb, -5.75, 0.95, Z3, 158, F.armchair, w=0.80, d=0.80, mat="M_FabricOat")

    # 3.6 m 书架墙（贴西墙，沿 Y）
    place(gb, -6.71, 2.10, Z3, 90, F.bookshelf, w=3.60, d=0.34, h=2.55, shelves=6, seed=41)
    # 地球仪
    gb.cyl(0.16, 0.02, (-2.35, 3.55, Z3 + 0.01), seg=20, mat="M_WoodDark")
    gb.cyl(0.02, 0.34, (-2.35, 3.55, Z3 + 0.18), seg=8, mat="M_Brass")
    gb.sphere(0.26, (-2.35, 3.55, Z3 + 0.60), seg=18, rings=12, mat="M_Celadon")
    gb.cyl(0.014, 0.50, (-2.35, 3.55, Z3 + 0.60), axis="Y", seg=8, mat="M_Brass",
           rot=Matrix.Rotation(D(20), 4, "X"))

    # 茶台 + 两个落地坐垫
    place(gb, -3.40, 3.30, Z3, 0, F.kang_table, w=1.40, d=0.80, h=0.34)
    place(gb, -3.40, 2.55, Z3, 0, F.cushion, r=0.26, h=0.15, mat="M_FabricRust")
    place(gb, -3.40, 4.02, Z3, 0, F.cushion, r=0.26, h=0.15, mat="M_VelvetInk")

    # 地毯 + 落地灯 + 两株植物 + 三幅画
    place(gb, -4.30, 2.20, Z3, 0, F.rug, w=3.20, d=2.40, mat="M_Rug",
          border="M_FabricGrey")
    place(gb, -1.95, 3.85, Z3, 0, F.floor_lamp, h=1.68)
    plant(gb, -6.22, -0.58, Z3, s=1.02, big=True, leaf="M_LeafDeep")
    plant(gb, -1.95, -0.86, Z3, s=0.95, leaf="M_LeafGreen")
    art(gb, -4.40, 4.26, Z3 + 1.90, 180, w=2.10, h=0.90, mat="M_WoodDark", artm="M_Canvas")
    art(gb, -1.68, 2.30, Z3 + 1.65, 90, w=0.85, h=1.20, mat="M_WoodDark", artm="M_Silk")
    art(gb, -1.68, 0.55, Z3 + 1.65, 90, w=0.85, h=1.20, mat="M_WoodDark", artm="M_Canvas")
    # 窗帘（南向横窗）
    for xx in (-6.37, -5.75, -2.85, -2.20):
        place(gb, xx, -1.14, Z3, 0, F.curtain, w=0.80, h=2.30, mat="M_Linen")

    downlight_ring(gb, -6.86, -1.74, -1.16, 4.26, CH3, 3, 3, inset=0.95)

    ctx.mesh(gb, "INT_3F_Study")
    ctx.room("study", "书房", "Study", 3, (-4.40, Z3, 1.40), 34,
             "2.4 m 长桌正对南向横窗，西墙 3.6 m 书架，茶台配两只落地坐垫。")


def build_guest(ctx):
    """客卧 X −7.20…−1.60, Y 4.40…9.00, z 6.92。"""
    gb = GB("INT_3F_Guest")
    floor_plane(gb, -6.88, -1.72, 4.54, 8.66, Z3, "M_OakFloor")
    skirt(gb, -6.90, -1.70, 4.50, 8.70, Z3)

    place(gb, -4.40, 7.50, Z3, 180, F.bed, w=1.60, l=2.05,
          mat="M_Linen", head="M_FabricGrey")
    # 衣柜（贴西墙）
    place(gb, -6.58, 6.20, Z3, 90, F.wardrobe, w=2.20, d=0.60, h=2.40, mat="M_Wood")
    # 行李架 + 行李箱
    gb.boxb(((-3.45, -2.85), (5.05, 5.45), (Z3 + 0.40, Z3 + 0.45)), mat="M_WoodDark")
    for s in (-1, 1):
        gb.boxb(((-3.40, -3.36), (5.02, 5.48), (Z3, Z3 + 0.40)), mat="M_MetalBlack")
        gb.boxb(((-2.94, -2.90), (5.02, 5.48), (Z3, Z3 + 0.40)), mat="M_MetalBlack")
    gb.box((0.52, 0.34, 0.66), (-3.15, 5.25, Z3 + 0.78), mat="M_FabricInk")
    gb.box((0.54, 0.36, 0.06), (-3.15, 5.25, Z3 + 1.08), mat="M_Leather")
    gb.box((0.10, 0.06, 0.10), (-3.15, 5.05, Z3 + 1.16), mat="M_MetalGrey")
    # 地毯 + 一幅画
    place(gb, -4.30, 6.45, Z3, 0, F.rug, w=2.70, d=1.90, mat="M_Rug",
          border="M_FabricGrey")
    art(gb, -4.40, 8.62, Z3 + 1.90, 0, w=1.30, h=0.80, mat="M_WoodDark", artm="M_Canvas")
    gb.box((0.22, 0.16, 0.03), (-3.11, 8.39, Z3 + 0.50), mat="M_BookPage")

    downlight_ring(gb, -6.86, -1.74, 4.54, 8.66, CH3, 2, 3, inset=0.85)

    ctx.mesh(gb, "INT_3F_Guest")
    ctx.room("guest", "客卧", "Guest Room", 3, (-4.40, Z3, 6.50), 27,
             "一张双人床靠北墙，西墙衣柜，行李架上敞着一只行李箱。")


def build_landing3(ctx):
    """三层过厅 X −1.60…1.60, Y −1.50…4.20, z 6.92。"""
    gb = GB("INT_3F_Landing")
    floor_plane(gb, -1.50, 1.50, -1.16, 4.10, Z3, "M_OakFloor")
    skirt(gb, -1.50, 1.50, -1.20, 4.10, Z3)

    gb.boxb(((-1.50, -1.16), (0.85, 2.45), (Z3, Z3 + 0.78)), mat="M_Wood")
    gb.boxb(((-1.50, -1.14), (0.83, 2.47), (Z3 + 0.78, Z3 + 0.82)), mat="M_StoneLight")
    gb.lathe([(0.06, 0), (0.10, 0.07), (0.11, 0.20), (0.06, 0.27)], seg=16,
             center=(-1.34, 1.10, Z3 + 0.83), mat="M_Ceramic")
    gb.box((0.20, 0.15, 0.16), (-1.34, 1.95, Z3 + 0.90), mat="M_BookSpineB")
    art(gb, 1.72, 1.70, Z3 + 1.55, -90, w=0.72, h=1.05, mat="M_WoodDark", artm="M_Silk")
    plant(gb, 1.10, 3.50, Z3, s=0.95, leaf="M_LeafDeep")
    gb.boxb(((-0.80, 0.80), (-1.00, 2.30), (Z3, Z3 + 0.014)), mat="M_Rug")
    for i in range(9):
        gb.boxb(((-0.73, 0.73), (-0.95 + i * 0.35, -0.91 + i * 0.35),
                 (Z3 + 0.014, Z3 + 0.016)), mat="M_FabricGrey")

    downlight(gb, 0.0, 0.30, CH3)
    downlight(gb, 0.0, 2.70, CH3)
    place(gb, 0.0, 1.50, CH3 - 0.07, 0, F.ceiling_lamp, z=0.0, r=0.32)

    ctx.mesh(gb, "INT_3F_Landing")
    ctx.room("landing3", "三层过厅", "Upper Landing", 3, (0.0, Z3, 1.30), 20,
             "顶层楼梯厅，地毯铺到北端，边柜与一株垂枝绿植守着过道。")


def build_tea(ctx):
    """茶室 X 1.60…3.60, Y −1.50…5.00, z 6.92（窄长 2.0×6.5）。"""
    gb = GB("INT_3F_Tea")
    floor_plane(gb, 1.72, 3.28, -1.16, 4.86, Z3, "M_OakFloor")
    skirt(gb, 1.70, 3.30, -1.20, 4.90, Z3)

    # 低茶台 1.4×0.7
    place(gb, 2.60, 1.95, Z3, 0, F.kang_table, w=1.36, d=0.70, h=0.32)
    # 茶具：托盘 + 壶 + 四杯
    place(gb, 2.60, 1.95, Z3 + 0.40, 0, F.tray_tea)
    # 四只坐垫
    for (cx, cy) in ((2.60, 1.20), (2.60, 2.70), (1.95, 1.95), (3.25, 1.95)):
        place(gb, cx, cy, Z3, 0, F.cushion, r=0.24, h=0.14,
              mat="M_FabricRust" if cy < 2.0 else "M_FabricOat")
    # 两组搁板（贴东墙，收陶瓷）
    for i, yy in enumerate((0.10, 4.10)):
        gb.boxb(((3.10, 3.52), (yy - 0.55, yy + 0.55), (Z3, Z3 + 1.70)), mat="M_Wood")
        for lvl in range(1, 4):
            zz = Z3 + lvl * 0.40
            gb.boxb(((3.08, 3.54), (yy - 0.55, yy + 0.55), (zz, zz + 0.022)),
                    mat="M_WoodLight")
            gb.lathe([(0.045, 0), (0.075, 0.05), (0.08, 0.14), (0.04, 0.18)], seg=12,
                     center=(3.30, yy - 0.20, zz + 0.022),
                     mat="M_Celadon" if lvl % 2 else "M_Ceramic")
            gb.lathe([(0.05, 0), (0.09, 0.06), (0.085, 0.20), (0.05, 0.24)], seg=12,
                     center=(3.30, yy + 0.22, zz + 0.022),
                     mat="M_Porcelain" if lvl % 2 else "M_Celadon")
    # 屏风 + 植物
    place(gb, 2.10, 3.55, Z3, 16, F.screen, w=1.70, h=1.80, panels=3, mat="M_WoodDark")
    place(gb, 2.55, -0.48, Z3, 0, F.round_rug, r=0.68, mat="M_Rug")
    plant(gb, 1.95, -0.88, Z3, s=0.70, leaf="M_LeafPale")

    downlight(gb, 2.60, 0.60, CH3)
    downlight(gb, 2.60, 2.20, CH3)
    downlight(gb, 2.60, 3.80, CH3)
    place(gb, 2.60, 1.95, CH3, 0, F.pendant, z=0.0, drop=0.85, r=0.20)

    ctx.mesh(gb, "INT_3F_Tea")
    ctx.room("tea", "茶室", "Tea Room", 3, (2.60, Z3, 1.80), 13,
             "低茶台配四只坐垫，一具三折屏风隔出里侧，东墙两组搁板收青瓷。")


def build_bath3(ctx):
    """三层卫浴 X 1.60…3.60, Y 5.00…9.00, z 6.92。"""
    gb = GB("INT_3F_Bath3")
    floor_plane(gb, 1.72, 3.28, 5.14, 8.66, Z3, "M_TileFloorGrey")
    skirt(gb, 1.70, 3.30, 5.10, 8.70, Z3, h=0.06, mat="M_StoneDark")

    place(gb, 2.60, 5.80, Z3, 0, F.shower, w=1.40, d=1.30, h=2.20)
    place(gb, 1.98, 8.30, Z3, 180, F.toilet)
    place(gb, 3.05, 8.40, Z3, 0, F.basin, w=0.85, d=0.46, h=0.82)
    place(gb, 2.62, 6.65, Z3, 0, F.bath_mat, w=0.66, d=0.44)
    place(gb, 1.86, 7.15, Z3, 90, F.towel_bar, w=0.62, z=1.05, cloth="M_Linen")
    gb.box((0.28, 0.22, 0.08), (1.82, 7.70, Z3 + 1.20), mat="M_FabricOat")

    downlight(gb, 2.60, 5.90, CH3)
    downlight(gb, 2.60, 8.20, CH3)

    ctx.mesh(gb, "INT_3F_Bath3")
    ctx.room("bath3", "三层卫浴", "Bath 3", 3, (2.60, Z3, 7.00), 12,
             "淋浴靠南、台盆与马桶并排靠北，一条毛巾杆挂在西墙上。")


def build_terrace(ctx):
    """露台 X 3.60…7.20, Y −1.50…9.00, z 6.92（露天，无顶）。

    家具组整体朝西南：两把户外沙发椅对南院开口（旋转 126°/135°，
    即开口指向 216°/225° 方位），矮几在两椅前方，地毯压在整组下面。
    通行带：北侧 Y ≥ 8.10、东侧 X ≥ 6.60 全空，可绕家具走一圈。
    """
    gb = GB("INT_3F_Terrace")
    ZF = ZT - 0.002            # 家具落座面：压进铺装 2 mm，避免与铺装顶面共面
    FAB, FAB2, FAB3 = "M_FabricSage", "M_FabricOutdoor", "M_FabricClay"

    def cush(gb, size, center, mat, r=0.03):
        """三层错台的软垫（自带圆角观感）。不用 F.rbox：它用两块十字盒，
        两块盒的顶面/底面完全共面，铺装里会闪。"""
        sx, sy, sz = size
        cx, cy, cz = center
        gb.box((sx, sy, sz * 0.46), (cx, cy, cz - sz * 0.25), mat=mat)
        gb.box((sx - r, sy - r, sz * 0.58), (cx, cy, cz - sz * 0.07), mat=mat)
        gb.box((sx - 2.2 * r, sy - 2.2 * r, sz * 0.40),
               (cx, cy, cz + sz * 0.26), mat=mat)

    # ------------------------------------------------ 本地构件（仅露台使用）
    def sofa_chair(gb, w=0.82, d=0.82):
        """低背户外沙发椅：座高 0.38、背高 0.78、深座 0.74，开口朝 +Y。"""
        base, fr, cu = 0.20, 0.10, 0.08
        for sx in (-1, 1):
            for sy in (-1, 1):
                gb.box((0.06, 0.06, base),
                       (sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), base / 2),
                       mat="M_TeakFurnDark")
        gb.box((w, d, fr), (0, 0, base + fr / 2), mat="M_TeakFurn")
        cush(gb, (w - 0.10, d - 0.08, cu), (0, 0.02, base + fr + cu / 2 - 0.002),
             FAB, r=0.035)
        with gb.frame(Matrix.Translation((0, -d / 2 + 0.05, base + fr)) @
                      Matrix.Rotation(D(9), 4, "X")):
            gb.box((w, 0.055, 0.49), (0, 0, 0.245), mat="M_TeakFurn")
            cush(gb, (w - 0.14, 0.10, 0.40), (0, 0.075, 0.215), FAB, r=0.03)
        for s in (-1, 1):
            gb.box((0.07, d - 0.02, 0.264), (s * (w / 2 - 0.035), 0,
                   base + fr + 0.128), mat="M_TeakFurn")
            gb.box((0.09, d, 0.035), (s * (w / 2 - 0.035), 0,
                   base + fr + 0.275), mat="M_TeakFurnDark")
        with gb.frame(Matrix.Translation((0, -d / 2 + 0.17, base + fr + 0.14)) @
                      Matrix.Rotation(D(17), 4, "X")):
            cush(gb, (0.34, 0.11, 0.30), (0, 0, 0), FAB3, r=0.03)

    def low_table(gb, w=0.95, d=0.55, h=0.34):
        """低矮户外矮几：柚木台面 + 深色金属腿。"""
        gb.box((w, d, 0.055), (0, 0, h - 0.028), mat="M_TeakFurn")
        gb.box((w - 0.16, d - 0.14, 0.05), (0, 0, h - 0.086),
               mat="M_TeakFurnDark")
        for sx in (-1, 1):
            for sy in (-1, 1):
                gb.box((0.042, 0.042, h - 0.06),
                       (sx * (w / 2 - 0.06), sy * (d / 2 - 0.06),
                        (h - 0.06) / 2), mat="M_MetalBlack")

    def tray_cups(gb):
        """矮几上的托盘 + 两只杯子。"""
        gb.box((0.36, 0.26, 0.024), (0, 0, 0.010), mat="M_TeakFurnDark")
        for cx, cy in ((-0.085, 0.030), (0.095, -0.020)):
            gb.cyl(0.042, 0.077, (cx, cy, 0.058), seg=14, mat="M_Ceramic")
        gb.cyl(0.052, 0.028, (0.012, -0.088, 0.034), seg=16, mat="M_Celadon")

    # ------------------------------------------------ 铺装
    # 从结构面 6.90 铺到 6.92，底面 6.87 埋进 3F 屋面板顶（6.88），不留缝
    gb.boxb(((3.64, 6.88), (-1.18, 8.68), (ZT - 0.05, ZT)), mat="M_DeckTeak")
    for i in range(24):
        yy = -1.14 + i * ((8.63 + 1.14) / 23.0)
        gb.boxb(((3.66, 6.86), (yy, yy + 0.030), (ZT - 0.006, ZT + 0.008)),
                mat="M_DeckTeakGap")
    # 玻璃栏板内侧收边石（底压进铺装）
    gb.boxb(((3.66, 3.80), (-1.18, 8.68), (ZT - 0.004, ZT + 0.02)),
            mat="M_StoneLight")

    # ------------------------------------------------ 家具组（朝西南）
    # 地毯 2.20 × 1.70（长边沿南北），压在整组下面
    place(gb, 5.35, 3.30, ZF, 90, F.rug, w=2.20, d=1.70,
          mat=FAB2, border=FAB, z=0.008)
    # 两把户外沙发椅：开口指向 216° / 225° 方位（place 的 rot=126° / 135°）
    place(gb, 5.55, 2.55, ZF, 126, sofa_chair)
    place(gb, 5.55, 4.05, ZF, 135, sofa_chair)
    # 矮几（0.95 × 0.55 × 0.34，柚木台面）+ 托盘两只杯
    place(gb, 4.55, 3.30, ZF, 135, low_table)
    with gb.frame(Matrix.Translation((4.55, 3.30, ZF + 0.34)) @
                  Matrix.Rotation(D(135), 4, "Z")):
        tray_cups(gb)
    # 边几 + 盆栽
    place(gb, 6.10, 3.30, ZT - 0.012, 0, F.side_table, r=0.22, h=0.42)
    place(gb, 6.20, 4.95, ZF, 0, F.potted_plant, r=0.22, h=0.40,
          leaf="M_LeafOlive")

    # ------------------------------------------------ 靠 3F 山墙的种植槽
    for i, py in enumerate((5.90, 6.70, 7.50)):
        gb.boxb(((3.70, 4.20), (py - 0.32, py + 0.32), (ZT - 0.03, ZT + 0.52)),
                mat="M_ConcretePot")
        gb.boxb(((3.74, 4.16), (py - 0.28, py + 0.28), (ZT + 0.44, ZT + 0.515)),
                mat="M_Soil")
        with gb.frame(Matrix.Translation((3.95, py, ZT + 0.46))):
            N.shrub(gb, r=0.24, leaf="M_LeafGreen" if i % 2 else "M_LeafOlive",
                    seed=60 + i)
    # 东南角一株盆栽松（挪出通行带）
    gb.lathe([(0.28, 0), (0.33, 0.05), (0.35, 0.42), (0.31, 0.50)], seg=20,
             center=(6.20, -0.55, ZT - 0.03), mat="M_ConcretePot")
    with gb.frame(Matrix.Translation((6.20, -0.55, ZT + 0.43))):
        N.pine(gb, h=1.12, r=0.34, seed=64)

    # 四盏落地灯笼（东侧两盏内收到 X=6.45，让出东向通行带）
    for lx, ly in ((3.95, 0.60), (6.45, 0.60), (3.95, 4.60), (6.45, 4.60)):
        gb.cyl(0.10, 0.05, (lx, ly, ZF + 0.025), seg=14, mat="M_MetalBlack")
        gb.lathe([(0.085, 0), (0.115, 0.05), (0.11, 0.36), (0.06, 0.42)], seg=14,
                 center=(lx, ly, ZF + 0.047), mat="M_LampShade")
        gb.cyl(0.12, 0.02, (lx, ly, ZF + 0.462), seg=14, mat="M_MetalBlack")

    ctx.mesh(gb, "INT_3F_Terrace")
    ctx.room("terrace", "露台", "Roof Terrace", 3, (5.40, ZT, 2.60), 38,
             "2F 屋面上的露天露台：柚木铺装，两把户外沙发椅朝西南对坐矮几，"
             "地毯、边几、盆栽与四盏落地灯笼；沿北/东玻璃栏板留 0.60 m 通行带。")


# ================================================================ 入口
def build(ctx):
    """三层室内：每间房一个 GB → 一个 mesh，挂在对应 INT_* 层下。"""
    ctx.use("INT_1F")
    build_foyer(ctx)
    build_living(ctx)
    build_dining(ctx)
    build_kitchen(ctx)
    build_pantry(ctx)
    build_wc(ctx)
    build_service(ctx)
    build_stair(ctx)

    ctx.use("INT_2F")
    build_master(ctx)
    build_master_bath(ctx)
    build_walkin(ctx)
    build_landing(ctx)
    build_bed2(ctx)
    build_bath2(ctx)
    build_laundry(ctx)
    build_nook(ctx)

    ctx.use("INT_3F")
    build_study(ctx)
    build_guest(ctx)
    build_landing3(ctx)
    build_tea(ctx)
    build_bath3(ctx)
    build_terrace(ctx)

