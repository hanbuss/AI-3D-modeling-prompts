# -*- coding: utf-8 -*-
"""新中式三层别墅 · 程序化搭建入口
运行： blender -b --python build_villa.py
产物： villa.blend / villa.glb / rooms.json / previews/*.png
"""
import bpy
import bmesh
import os
import sys
import json
import math
import random
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from lib import kit, mats, arch, furni, nature, details, assets   # noqa: E402
import random as _r                                   # noqa: E402
from lib.kit import GB, D, TAU, lerp                 # noqa: E402

# ---------------------------------------------------------------- 全局尺寸
Z1, Z2, Z3, ZT = 3.40, 6.60, 9.40, 9.40
BX0, BX1 = -8.0, 8.0          # 主体东西
BY0, BY1 = -6.0, 6.0          # 主体南北（-Y 为南，入口+花园）
F3Y0, F3Y1 = -3.4, 6.0        # 三层退台南界
BAL_Y = -8.6                  # 二层阳台南沿
WALL_T = 0.24                 # 外墙厚
PAR_T = 0.14                  # 隔墙厚

CTX = None
WALLS = []          # (axis, a0, a1, b0, b1, c0, c1) 真实墙段，供 audit 用


# ---------------------------------------------------------------- 小工具
def wx(gb, y, x0, x1, z0, z1, t=WALL_T, mat="M_WallWhite", openings=()):
    arch.wall(gb, x0, x1, y - t / 2, y + t / 2, z0, z1, "X", mat, openings)
    WALLS.append(("X", x0, x1, y - t / 2, y + t / 2, z0, z1))


def wy(gb, x, y0, y1, z0, z1, t=WALL_T, mat="M_WallWhite", openings=()):
    arch.wall(gb, y0, y1, x - t / 2, x + t / 2, z0, z1, "Y", mat, openings)
    WALLS.append(("Y", y0, y1, x - t / 2, x + t / 2, z0, z1))


def piece(layer, name, fn, *a, **kw):
    """建一个独立 mesh 并挂到指定层。fn(gb, *a, **kw)"""
    gb = GB(name)
    fn(gb, *a, **kw)
    CTX.use(layer)
    return CTX.mesh(gb, name)


def obj(layer, name, build_fn):
    gb = GB(name)
    build_fn(gb)
    CTX.use(layer)
    return CTX.mesh(gb, name)


def place(layer, name, fn, x, y, z, rot=0.0, **kw):
    """局部坐标家具放到世界：先转过再平移。"""
    def _b(gb):
        with gb.frame(Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")):
            fn(gb, **kw)
    return obj(layer, name, _b)


def place_plant(layer, name, asset, x, y, z, rot=0.0, pot_r=0.26, pot_h=0.42,
                h=1.0):
    """陶盆 + 成品植物模型（PolyHaven），盆落地、植物摆在盆口。"""
    place(layer, name + "_Pot", furni.pot, x, y, z, rot, r=pot_r, h=pot_h)
    assets.instance(CTX, layer, asset, name, x, y, z + pot_h - 0.03,
                    height=h, rot=rot, max_w=pot_r * 3.4)


# ---------------------------------------------------------------- 场景清理
def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.render.fps = 24


def setup_world():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("W_Villa")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs[0].default_value = (0.56, 0.72, 0.92, 1)
    bg.inputs[1].default_value = 0.55
    return w


# ================================================================ 场地
def build_site():
    L = "SITE"
    CTX.use(L)
    # 地面
    gb = GB("SITE_Ground")
    gb.boxb(((-26, 26), (-23, 21), (-0.60, -0.02)), mat="M_GroundSoil")
    gb.boxb(((-22, 22), (-19.5, 18.5), (-0.02, 0.02)), mat="M_Grass")
    CTX.mesh(gb, "SITE_Ground")

    # 建筑基座 + 台阶
    gb = GB("SITE_Plinth")
    gb.boxb(((-8.6, 8.6), (-6.6, 6.6), (0.0, 0.16)), mat="M_StoneDark")
    gb.boxb(((-9.0, 9.0), (-7.0, 7.0), (0.0, 0.06)), mat="M_Stone")
    # 南向大台阶
    for i in range(3):
        gb.boxb(((-3.0, 3.0), (-6.6 - (i + 1) * 0.42, -6.6 - i * 0.42),
                 (0.0, 0.16 - i * 0.05)), mat="M_StoneLight")
    # 北侧服务门小平台
    gb.boxb(((2.6, 4.4), (6.6, 7.6), (0.0, 0.16)), mat="M_StoneLight")
    CTX.mesh(gb, "SITE_Plinth")

    # 院墙（南墙带月亮门，其余素墙压瓦）
    gb = GB("SITE_PerimeterWall")
    arch.moon_gate_wall(gb, -20.0, 20.0, -17.4, 0.02, 2.85, 0.0, 1.25, t=0.40)
    wy(gb, -20.0, -17.6, 16.0, 0.02, 2.85, 0.40, "M_WallWhite")
    wy(gb, 20.0, -17.6, 16.0, 0.02, 2.85, 0.40, "M_WallWhite")
    wx(gb, 16.0, -20.0, 20.0, 0.02, 2.85, 0.40, "M_WallWhite")
    # 侧墙压顶
    for (x0, x1, y0, y1) in ((-20.2, -19.8, -17.6, 16.2), (19.8, 20.2, -17.6, 16.2),
                             (-20.2, 20.2, 15.8, 16.2)):
        gb.boxb(((x0, x1), (y0, y1), (2.85, 2.95)), mat="M_Tile")
        gb.boxb(((x0 - 0.10, x1 + 0.10), (y0 - 0.10, y1 + 0.10), (2.95, 3.02)),
                mat="M_TileEdge")
    CTX.mesh(gb, "SITE_PerimeterWall")

    # 车道 + 停车铺装（南院东侧）
    gb = GB("SITE_Paving")
    gb.boxb(((9.5, 19.6), (-17.2, -6.8), (0.02, 0.06)), mat="M_Gravel")
    for i in range(9):
        gb.boxb(((9.7 + i * 1.1, 10.5 + i * 1.1), (-17.0, -7.0), (0.06, 0.075)),
                mat="M_StoneLight")
    # 建筑周边檐廊铺地
    gb.boxb(((-9.2, 9.2), (-9.4, -6.6), (0.02, 0.08)), mat="M_StoneLight")
    CTX.mesh(gb, "SITE_Paving")


# ================================================================ 主体外壳
def build_shell():
    # ---------------- 一层：外墙 ----------------
    L = "F1"
    CTX.use(L)
    gb = GB("F1_Walls")
    # 南墙 y=-6
    wx(gb, BY0, BX0, BX1, 0.16, Z1, openings=[
        (-6.9, -2.4, 0.30, 2.95),      # 客厅落地窗
        (0.10, 1.55, 0.16, 2.60),      # 入户门
        (1.85, 2.95, 0.70, 2.60),      # 玄关窗
    ])
    # 北墙 y=+6
    wx(gb, BY1, BX0, BX1, 0.16, Z1, openings=[
        (-7.2, -4.6, 0.90, 2.60),      # 茶室窗
        (-1.0, 1.0, 0.16, 2.60),       # 后门
        (4.4, 6.6, 1.10, 2.70),        # 厨房窗
    ])
    # 东墙 x=+8
    wy(gb, BX1, BY0, BY1, 0.16, Z1, openings=[
        (-5.4, -1.6, 0.40, 2.80),      # 餐厅窗
        (1.4, 3.4, 1.10, 2.70),        # 厨房窗
    ])
    # 西墙 x=-8
    wy(gb, BX0, BY0, BY1, 0.16, Z1, openings=[
        (-4.8, -1.2, 0.90, 2.70),      # 客厅侧窗
        (2.2, 5.2, 0.50, 2.85),        # 茶室大窗
    ])
    # 门窗构件
    arch.glasswall(gb, -6.85, -2.45, 0.30, 2.95, BY0 - 0.06, BY0 + 0.06, "X", cols=4)
    arch.window(gb, -6.85, -2.45, 0.30, 2.95, BY0 - 0.06, BY0 + 0.06, "X", "plain", cols=4, rows=1, glass="M_Glass", sill=False, surround=True) if False else None
    arch.door(gb, 0.10, 1.55, 0.16, 2.60, BY0 - 0.10, BY0 + 0.10, "X", "M_WoodDark", 0.8)
    arch.window(gb, 1.85, 2.95, 0.70, 2.60, BY0 - 0.06, BY0 + 0.06, "X", "lattice", cols=2, rows=2, surround=True)
    arch.window(gb, -7.2, -4.6, 0.90, 2.60, BY1 - 0.06, BY1 + 0.06, "X", "lattice", cols=3, rows=2, surround=True)
    arch.door(gb, -1.0, 1.0, 0.16, 2.60, BY1 - 0.10, BY1 + 0.10, "X", "M_WoodDark", 0.15)
    arch.window(gb, 4.4, 6.6, 1.10, 2.70, BY1 - 0.06, BY1 + 0.06, "X", "plain", cols=2, rows=1, surround=True)
    arch.window(gb, -5.4, -1.6, 0.40, 2.80, BX1 - 0.06, BX1 + 0.06, "Y", "plain", cols=3, rows=2, surround=True)
    arch.window(gb, 1.4, 3.4, 1.10, 2.70, BX1 - 0.06, BX1 + 0.06, "Y", "plain", cols=2, rows=1, surround=True)
    arch.window(gb, -4.8, -1.2, 0.90, 2.70, BX0 - 0.06, BX0 + 0.06, "Y", "lattice", cols=2, rows=2, surround=True)
    arch.glasswall(gb, 2.2, 5.2, 0.50, 2.85, BX0 - 0.06, BX0 + 0.06, "Y", cols=3)

    # ---------------- 一层：内隔墙 ----------------
    # 餐厅/客厅 之间：木格栅 + 开口
    wy(gb, 2.4, BY0, -1.0, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(-5.0, -2.0, 0.16, 2.60)])
    # 厨房/餐厅
    wx(gb, -1.0, 2.4, BX1, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(2.9, 5.1, 0.16, 2.60)])
    # 茶室南墙
    wx(gb, 1.4, BX0, -1.8, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(-7.2, -6.4, 0.16, 2.40)])
    # 茶室/楼梯
    wy(gb, -1.8, 1.4, BY1, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(2.0, 4.4, 0.16, 3.0)])
    # 楼梯/厨房
    wy(gb, 1.8, 1.4, 5.8, 0.16, Z1, PAR_T, "M_WallInner")
    # 家政/储藏 与 厨房
    wx(gb, 4.0, 1.8, BX1, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(2.2, 3.4, 0.16, 2.30)])
    wy(gb, 5.4, 4.0, BY1, 0.16, Z1, PAR_T, "M_WallInner",
       openings=[(4.6, 5.6, 0.16, 2.30)])
    CTX.mesh(gb, "F1_Walls")

    # 楼板（含楼梯洞口）
    obj(L, "F1_Slab", lambda gb: arch.slab(
        gb, BX0 - 0.30, BX1 + 0.30, BY0 - 0.30, BY1 + 0.30, Z1, 0.22,
        "M_Concrete", None,
        holes=[(-1.8, 1.8, 1.4, 5.8)]))

    # 首层地坪面层
    obj(L, "F1_FloorFinish", lambda gb: (
        gb.boxb(((BX0, BX1), (BY0, BY1), (0.16, 0.18)), mat="M_StoneLight"),
        gb.boxb(((-8.0, 2.4), (-4.0, 1.4), (0.18, 0.20)), mat="M_WoodPale"),
        gb.boxb(((2.4, 8.0), (-6.0, -1.0), (0.18, 0.20)), mat="M_WoodPale"),
        gb.boxb(((-8.0, -1.8), (1.4, 6.0), (0.18, 0.21)), mat="M_Wood"),))

    # 踢脚线（沿外墙内表面）
    def skirt(gb, x0, x1, y0, y1, z0, mat="M_WoodDark", h=0.11, t=0.03):
        gb.boxb(((x0, x1), (y0, y0 + t), (z0, z0 + h)), mat=mat)
        gb.boxb(((x0, x1), (y1 - t, y1), (z0, z0 + h)), mat=mat)
        gb.boxb(((x0, x0 + t), (y0, y1), (z0, z0 + h)), mat=mat)
        gb.boxb(((x1 - t, x1), (y0, y1), (z0, z0 + h)), mat=mat)

    obj("F1", "F1_Skirt", lambda gb: skirt(gb, BX0 + 0.12, BX1 - 0.12,
                                          BY0 + 0.12, BY1 - 0.12, 0.20))
    obj("F2", "F2_Skirt", lambda gb: skirt(gb, BX0 + 0.12, BX1 - 0.12,
                                          BY0 + 0.12, BY1 - 0.12, Z1 + 0.03))
    obj("F3", "F3_Skirt", lambda gb: skirt(gb, BX0 + 0.12, BX1 - 0.12,
                                          F3Y0 + 0.12, BY1 - 0.12, Z2 + 0.03))

    # 腰线与转角木饰带
    obj("F1", "F1_Belts", lambda gb: (
        arch.belts(gb, BX0, BX1, BY0, BY1, Z1 - 0.40, 0.09, 0.05, "M_StoneLight"),
        arch.belts(gb, BX0, BX1, BY0, BY1, 0.30, 0.07, 0.04, "M_StoneLight"),
        # 转角木饰带
        [gb.boxb(((x - 0.13, x + 0.13), (y - 0.13, y + 0.13), (0.20, Z1 - 0.10)),
                 mat="M_WoodDark")
         for x in (BX0 - 0.02, BX1 + 0.02) for y in (BY0 - 0.02, BY1 + 0.02)],
        # 入口上方木格栅雨棚
        gb.boxb(((-1.9, 3.2), (BY0 - 1.5, BY0 - 1.35), (Z1 - 0.62, Z1 - 0.30)),
                mat="M_WoodDark"),
        [gb.boxb(((-1.85 + i * 0.42, -1.73 + i * 0.42),
                  (BY0 - 1.5005 - 0.02, BY0 - 1.3495 + 0.02),
                  (Z1 - 0.62, Z1 - 0.30)), mat="M_WoodDark") for i in range(13)]))

    obj("F2", "F2_Belts", lambda gb: (
        arch.belts(gb, BX0, BX1, BY0, BY1, Z2 - 0.40, 0.09, 0.05, "M_StoneLight"),
        [gb.boxb(((x - 0.13, x + 0.13), (y - 0.13, y + 0.13), (Z1, Z2 - 0.06)),
                 mat="M_WoodDark")
         for x in (BX0 - 0.02, BX1 + 0.02) for y in (BY0 - 0.02, BY1 + 0.02)]))

    obj("F3", "F3_Belts", lambda gb: (
        arch.belts(gb, BX0, BX1, F3Y0, BY1, Z3 - 0.42, 0.09, 0.05, "M_StoneLight"),
        [gb.boxb(((x - 0.13, x + 0.13), (y - 0.13, y + 0.13), (Z2, Z3 - 0.08)),
                 mat="M_WoodDark")
         for x in (BX0 - 0.02, BX1 + 0.02) for y in (F3Y0 - 0.02, BY1 + 0.02)]))

    # 楼梯 + 扶手
    obj(L, "F1_Stair", lambda gb: arch.stair(gb, -1.7, 1.7, 1.5, 5.7, 0.0, Z1,
                                             steps=20, handrail=True))
    # 楼梯井玻璃栏板（二层洞口）

    # 一层吊顶（局部）
    obj(L, "F1_Ceiling", lambda gb: (
        gb.boxb(((BX0, BX1), (BY0, BY1), (Z1 - 0.24, Z1 - 0.14)), mat="M_Ceiling")))

    # ---------------- 二层 ----------------
    L = "F2"
    CTX.use(L)
    gb = GB("F2_Walls")
    wx(gb, BY0, BX0, BX1, Z1, Z2, openings=[
        (-7.1, -2.4, Z1 + 0.55, Z2 - 0.35),    # 主卧窗
        (2.4, 7.1, Z1 + 0.55, Z2 - 0.35),      # 次卧窗
        (-1.3, 1.3, Z1 + 0.10, Z2 - 0.30),     # 阳台门
    ])
    wx(gb, BY1, BX0, BX1, Z1, Z2, openings=[
        (-7.0, -4.2, Z1 + 0.95, Z2 - 0.55),
        (1.2, 3.2, Z1 + 0.95, Z2 - 0.55),
        (5.2, 7.0, Z1 + 1.15, Z2 - 0.55),
    ])
    wy(gb, BX1, BY0, BY1, Z1, Z2, openings=[
        (-5.2, -2.0, Z1 + 0.75, Z2 - 0.55),
        (2.0, 4.0, Z1 + 0.95, Z2 - 0.55),
    ])
    wy(gb, BX0, BY0, BY1, Z1, Z2, openings=[
        (-4.8, -1.4, Z1 + 0.75, Z2 - 0.55),
        (2.0, 5.2, Z1 + 1.10, Z2 - 0.50),
    ])
    arch.window(gb, -7.1, -2.4, Z1 + 0.55, Z2 - 0.35, BY0 - 0.06, BY0 + 0.06, "X", "plain", cols=4, rows=2, surround=True)
    arch.window(gb, 2.4, 7.1, Z1 + 0.55, Z2 - 0.35, BY0 - 0.06, BY0 + 0.06, "X", "plain", cols=4, rows=2, surround=True)
    arch.glasswall(gb, -1.3, 1.3, Z1 + 0.10, Z2 - 0.30, BY0 - 0.06, BY0 + 0.06, "X", cols=2)
    arch.window(gb, -7.0, -4.2, Z1 + 0.95, Z2 - 0.55, BY1 - 0.06, BY1 + 0.06, "X", "plain", cols=2, rows=1, surround=True)
    arch.window(gb, 1.2, 3.2, Z1 + 0.95, Z2 - 0.55, BY1 - 0.06, BY1 + 0.06, "X", "lattice", cols=2, rows=1, surround=True)
    arch.window(gb, 5.2, 7.0, Z1 + 1.15, Z2 - 0.55, BY1 - 0.06, BY1 + 0.06, "X", "plain", cols=1, rows=1, surround=True)
    arch.window(gb, -5.2, -2.0, Z1 + 0.75, Z2 - 0.55, BX1 - 0.06, BX1 + 0.06, "Y", "plain", cols=3, rows=2, surround=True)
    arch.window(gb, 2.0, 4.0, Z1 + 0.95, Z2 - 0.55, BX1 - 0.06, BX1 + 0.06, "Y", "plain", cols=2, rows=1, surround=True)
    arch.window(gb, -4.8, -1.4, Z1 + 0.75, Z2 - 0.55, BX0 - 0.06, BX0 + 0.06, "Y", "plain", cols=3, rows=2, surround=True)
    arch.glasswall(gb, 2.0, 5.2, Z1 + 1.10, Z2 - 0.50, BX0 - 0.06, BX0 + 0.06, "Y", cols=2)

    # 二层内隔墙
    wx(gb, 0.6, BX0, -1.8, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(-3.4, -2.2, Z1 + 0.16, Z2 - 0.40)])
    wy(gb, -1.8, 0.6, BY1, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(2.2, 4.0, Z1 + 0.16, Z2 - 0.40)])
    wy(gb, -4.8, 0.6, 3.4, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(1.50, 2.55, Z1 + 0.16, Z2 - 0.40)])
    wx(gb, 3.4, BX0, -1.8, Z1, Z2, PAR_T, "M_WallInner")
    wy(gb, -1.8, BY0, -1.0, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(-3.6, -2.4, Z1 + 0.16, Z2 - 0.40)])
    wx(gb, -1.0, -1.8, 1.8, Z1, Z2, PAR_T, "M_WallInner")
    wx(gb, -1.0, 1.8, BX1, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(3.4, 4.6, Z1 + 0.16, Z2 - 0.40)])
    wx(gb, 1.2, 1.8, BX1, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(2.4, 4.4, Z1 + 0.16, Z2 - 0.40)])
    wy(gb, 1.8, -1.0, 4.4, Z1, Z2, PAR_T, "M_WallInner")
    wx(gb, 4.4, 1.8, 4.6, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(2.4, 3.6, Z1 + 0.16, Z2 - 0.40)])
    wx(gb, 4.4, 4.6, BX1, Z1, Z2, PAR_T, "M_WallInner",
       openings=[(5.4, 6.6, Z1 + 0.16, Z2 - 0.40)])
    CTX.mesh(gb, "F2_Walls")

    obj(L, "F2_Slab", lambda gb: arch.slab(
        gb, BX0 - 0.30, BX1 + 0.30, BY0 - 0.30, BY1 + 0.30, Z2, 0.22,
        "M_Concrete", None, holes=[(-1.8, 1.8, 1.4, 5.8)]))
    obj(L, "F2_FloorFinish", lambda gb: (
        gb.boxb(((-8.0, -1.8), (-6.0, 0.6), (Z1 + 0.20, Z1 + 0.03)), mat="M_WoodPale"),
        gb.boxb(((1.8, 8.0), (-6.0, 1.2), (Z1 + 0.20, Z1 + 0.03)), mat="M_WoodPale"),
        gb.boxb(((-8.0, 8.0), (1.2, 6.0), (Z1 + 0.20, Z1 + 0.03)), mat="M_StoneLight"),
        gb.boxb(((-4.8, -1.8), (0.6, 3.4), (Z1 + 0.20, Z1 + 0.03)), mat="M_StoneLight")))
    obj(L, "F2_Stair", lambda gb: arch.stair(gb, -1.7, 1.7, 1.5, 5.7, Z1, Z2,
                                             steps=20, handrail=True))
    obj(L, "F2_Ceiling", lambda gb: gb.boxb(
        ((BX0, BX1), (BY0, BY1), (Z2 - 0.24, Z2 - 0.14)), mat="M_Ceiling"))

    # 阳台板 + 栏杆 + 挑檐
    obj(L, "F2_Balcony", lambda gb: (
        gb.boxb(((-6.6, 6.6), (BAL_Y, BY0), (Z1 - 0.20, Z1 + 0.04)), mat="M_Concrete"),
        gb.boxb(((-6.6, 6.6), (BAL_Y, BY0), (Z1 + 0.04, Z1 + 0.06)), mat="M_WoodPale"),
        gb.boxb(((-6.7, 6.7), (BAL_Y - 0.12, BAL_Y + 0.02), (Z1 - 0.02, Z1 + 0.30)), mat="M_StoneLight"),
        gb.boxb(((-6.7, -6.55), (BAL_Y, BY0), (Z1 + 0.06, Z1 + 0.20)), mat="M_StoneLight"),
        gb.boxb(((6.55, 6.7), (BAL_Y, BY0), (Z1 + 0.06, Z1 + 0.20)), mat="M_StoneLight"),
        arch.railing(gb, -6.62, 6.62, BAL_Y + 0.10, Z1 + 0.06, "X", 1.05, "M_WoodDark", "wood"),
))

    obj(L, "F2_BalconyRail", lambda gb: (
        arch.railing(gb, BAL_Y + 0.10, BY0 - 0.10, -6.62, Z1 + 0.06, "Y", 1.05, "M_WoodDark", "wood"),
        arch.railing(gb, BAL_Y + 0.10, BY0 - 0.10, 6.62, Z1 + 0.06, "Y", 1.05, "M_WoodDark", "wood")))

    # ---------------- 三层 ----------------
    L = "F3"
    CTX.use(L)
    gb = GB("F3_Walls")
    wx(gb, F3Y0, BX0, BX1, Z2, Z3, openings=[
        (-7.2, -3.0, Z2 + 0.45, Z3 - 0.35),
        (-1.0, 2.0, Z2 + 0.45, Z3 - 0.35),
    ])
    wx(gb, BY1, BX0, BX1, Z2, Z3, openings=[
        (-7.0, -2.4, Z2 + 0.85, Z3 - 0.55),
        (5.0, 7.0, Z2 + 1.10, Z3 - 0.55),
    ])
    wy(gb, BX1, F3Y0, BY1, Z2, Z3, openings=[
        (-2.4, 0.6, Z2 + 0.55, Z3 - 0.50),
        (2.4, 4.6, Z2 + 1.10, Z3 - 0.55),
    ])
    wy(gb, BX0, F3Y0, BY1, Z2, Z3, openings=[
        (-2.6, 0.4, Z2 + 0.55, Z3 - 0.50),
        (2.0, 5.0, Z2 + 0.95, Z3 - 0.55),
    ])
    arch.glasswall(gb, -7.2, -3.0, Z2 + 0.45, Z3 - 0.35, F3Y0 - 0.06, F3Y0 + 0.06, "X", cols=4)
    arch.glasswall(gb, -1.0, 2.0, Z2 + 0.45, Z3 - 0.35, F3Y0 - 0.06, F3Y0 + 0.06, "X", cols=2)
    arch.window(gb, -7.0, -2.4, Z2 + 0.85, Z3 - 0.55, BY1 - 0.06, BY1 + 0.06, "X", "lattice", cols=3, rows=2, surround=True)
    arch.window(gb, 5.0, 7.0, Z2 + 1.10, Z3 - 0.55, BY1 - 0.06, BY1 + 0.06, "X", "plain", cols=1, rows=1, surround=True)
    arch.glasswall(gb, -2.4, 0.6, Z2 + 0.55, Z3 - 0.50, BX1 - 0.06, BX1 + 0.06, "Y", cols=3)
    arch.window(gb, 2.4, 4.6, Z2 + 1.10, Z3 - 0.55, BX1 - 0.06, BX1 + 0.06, "Y", "plain", cols=1, rows=1, surround=True)
    arch.window(gb, -2.6, 0.4, Z2 + 0.55, Z3 - 0.50, BX0 - 0.06, BX0 + 0.06, "Y", "plain", cols=3, rows=2, surround=True)
    arch.window(gb, 2.0, 5.0, Z2 + 0.95, Z3 - 0.55, BX0 - 0.06, BX0 + 0.06, "Y", "lattice", cols=2, rows=1, surround=True)

    # 三层内隔墙
    wy(gb, -2.2, F3Y0, 0.8, Z2, Z3, PAR_T, "M_WallInner",
       openings=[(-2.6, -1.4, Z2 + 0.16, Z3 - 0.40)])
    wx(gb, 0.8, BX0, -1.8, Z2, Z3, PAR_T, "M_WallInner",
       openings=[(-6.4, -5.2, Z2 + 0.16, Z3 - 0.40)])
    wy(gb, -1.8, 0.8, BY1, Z2, Z3, PAR_T, "M_WallInner",
       openings=[(2.4, 4.2, Z2 + 0.16, Z3 - 0.40)])
    wx(gb, 1.2, -2.2, BX1, Z2, Z3, PAR_T, "M_WallInner",
       openings=[(2.6, 5.0, Z2 + 0.16, Z3 - 0.40)])
    wy(gb, 1.8, 1.4, 5.8, Z2, Z3, PAR_T, "M_WallInner")
    wx(gb, 3.4, 1.8, BX1, Z2, Z3, PAR_T, "M_WallInner",
       openings=[(5.2, 6.6, Z2 + 0.16, Z3 - 0.40)])
    wy(gb, 4.2, 3.4, BY1, Z2, Z3, PAR_T, "M_WallInner")
    CTX.mesh(gb, "F3_Walls")

    obj(L, "F3_Slab", lambda gb: arch.slab(
        gb, BX0 - 0.30, BX1 + 0.30, F3Y0 - 0.30, BY1 + 0.30, Z3, 0.22,
        "M_Concrete", None, holes=[(-1.8, 1.8, 1.4, 5.8)]))
    obj(L, "F3_FloorFinish", lambda gb: (
        gb.boxb(((-8.0, 8.0), (F3Y0, 6.0), (Z2 + 0.20, Z2 + 0.03)), mat="M_WoodPale")))
    obj(L, "F3_Stair", lambda gb: arch.stair(gb, -1.7, 1.7, 1.5, 5.7, Z2, Z3,
                                             steps=20, handrail=True))
    obj(L, "F3_Ceiling", lambda gb: gb.boxb(
        ((BX0, BX1), (F3Y0, BY1), (Z3 - 0.26, Z3 - 0.14)), mat="M_Ceiling"))

    # 三层露台（退台）
    obj(L, "F3_Terrace", lambda gb: (
        gb.boxb(((-8.0, 8.0), (-6.4, F3Y0), (Z2, Z2 + 0.10)), mat="M_StoneLight"),
        gb.boxb(((-8.2, 8.2), (-6.5, F3Y0), (Z2 - 0.02, Z2)), mat="M_Concrete"),
        arch.railing(gb, -8.0, 8.0, -6.36, Z2 + 0.10, "X", 1.05, "M_WoodDark", "wood"),
        arch.railing(gb, -6.4, F3Y0, -8.0, Z2 + 0.10, "Y", 1.05, "M_WoodDark", "wood"),
        arch.railing(gb, -6.4, F3Y0, 8.0, Z2 + 0.10, "Y", 1.05, "M_WoodDark", "wood")))

    # ---------------- 屋顶 ----------------
    L = "ROOF"
    obj(L, "ROOF_Main", lambda gb: arch.pitched_roof(
        gb, BX0, BX1, F3Y0, BY1, Z3, 2.15, overhang=1.05, mat="M_Tile",
        corner_lift=0.48))
    # 各层披檐
    obj(L, "ROOF_EaveF3", lambda gb: (
        arch.eave_canopy(gb, BX0, BX1, F3Y0, BY1, Z2 + 0.30, out=1.05, drop=0.60,
                         sides="NS", corner_lift=0.20),
        arch.eave_canopy(gb, BX0, BX1, F3Y0, BY1, Z2 + 0.30, out=0.77, drop=0.44,
                         sides="EW", corner_lift=0.14)))
    obj(L, "ROOF_EaveF2", lambda gb: (
        arch.eave_canopy(gb, BX0, BX1, BY0, BY1, Z1 + 0.24, out=0.92, drop=0.52,
                         sides="N", corner_lift=0.18),
        arch.eave_canopy(gb, BX0, BX1, BY0, BY1, Z1 + 0.24, out=0.75, drop=0.43,
                         sides="EW", corner_lift=0.12)))
    # 阳台雨棚（南向薄檐）
    obj(L, "ROOF_BalconyCanopy", lambda gb: arch.eave_canopy(
        gb, -6.8, 6.8, BY0, BY0 + 0.15, Z2 + 0.20, out=1.9, drop=0.58,
        sides="S", corner_lift=0.34))

    # 女儿墙/屋脊细节已含在 roof 中


# ================================================================ 室内软装
def build_f1_rooms():
    """一层：门厅 / 客厅 / 餐厅 / 厨房 / 茶室 / 客卫 / 家政。"""
    L = "F1"
    FL = 0.20
    # ---------- 客厅（电视墙在北隔墙，沙发朝北；西窗留给边柜与采光） ----------
    place(L, "F1_Living_Rug", furni.rug, -4.4, -1.5, FL + 0.012, 0.0, w=3.6, d=2.6)
    place(L, "F1_Living_Sofa", furni.sofa, -4.4, -2.30, FL, 0.0, w=2.9, d=1.0, seats=3)
    place(L, "F1_Living_Table", furni.coffee_table, -4.4, -1.00, FL, 0.0,
          w=1.6, d=0.9)
    place(L, "F1_Living_TV", furni.tv_wall, -4.40, 0.02, FL, math.radians(0),
          w=3.6, h=2.2)
    place(L, "F1_Living_Armchair", furni.armchair, -6.85, -1.35, FL, math.radians(-90))
    place(L, "F1_Living_Armchair2", furni.armchair, -1.95, -1.35, FL, math.radians(90))
    place(L, "F1_Living_SideTable", furni.side_table, -2.15, -2.95, FL)
    place(L, "F1_Living_Floor", furni.floor_lamp, -2.15, -0.20, FL)
    place(L, "F1_Living_Sideboard", lambda gb: (
        gb.box((1.8, 0.40, 0.72), (0, 0, 0.36), mat="M_Wood"),
        gb.box((1.86, 0.44, 0.05), (0, 0, 0.745), mat="M_StoneLight"),
        gb.box((1.60, 0.02, 0.02), (0, -0.21, 0.52), mat="M_Brass"),
        gb.lathe([(0.07, 0), (0.11, 0.05), (0.12, 0.22), (0.08, 0.30)],
                 seg=16, center=(-0.55, 0, 0.775), mat="M_Ceramic")),
        -7.74, -2.95, FL, math.radians(-90))
    place_plant(L, "F1_Living_Plant", "pine", -7.30, -4.55, FL, 0.3, pot_r=0.3, pot_h=0.46, h=1.15)
    place(L, "F1_Living_Art", furni.art_frame, 2.30, -2.10, FL + 1.70,
          math.radians(-90), w=1.4, h=0.9)
    place_plant(L, "F1_Living_Plant2", "pine", 1.55, 0.95, FL, 1.1, pot_r=0.24, pot_h=0.36, h=0.85)
    place(L, "F1_Living_Bin", furni.trash_bin, -2.20, -3.55, FL)

    # ---------- 门厅 ----------
    place(L, "F1_Entry_Console", lambda gb: (
        gb.box((1.5, 0.38, 0.79), (0, 0, 0.395), mat="M_WoodDark"),
        gb.box((1.56, 0.44, 0.05), (0, 0, 0.815), mat="M_Wood"),
        gb.box((1.40, 0.02, 0.02), (0, -0.20, 0.55), mat="M_Brass")),
        -1.62, -4.85, FL, math.radians(90))
    place(L, "F1_Entry_Vase", furni.vase_branch, -1.60, -4.30, FL + 0.84, 0.0,
          h=0.34, seed=8)
    place(L, "F1_Entry_Hooks", furni.coat_hooks, 2.10, -5.80, FL, math.radians(180))
    place(L, "F1_Entry_Pendant", furni.pendant, 0.55, -5.05, Z1 - 0.14, 0.0,
          drop=0.72, r=0.26)
    place(L, "F1_Entry_Bench", furni.bench, 1.78, -5.55, FL, math.radians(180),
          w=0.95, d=0.36)
    place(L, "F1_Entry_Slippers", furni.slippers, 1.95, -5.05, FL, math.radians(200))
    place(L, "F1_Entry_Shoe", lambda gb: (
        gb.box((1.2, 0.36, 1.0), (0, 0, 0.5), mat="M_Wood"),
        gb.box((1.22, 0.38, 0.04), (0, 0, 1.02), mat="M_WoodDark"),
        gb.box((1.10, 0.02, 0.02), (0, -0.19, 0.52), mat="M_Brass")),
        2.92, -4.55, FL, math.radians(90))

    # ---------- 茶室 ----------
    place(L, "F1_Tea_Table", furni.kang_table, -5.1, 3.5, FL + 0.01, 0.0, w=1.6, d=0.9)
    for i, (dx, dy) in enumerate(((-1.02, 0.0), (1.02, 0.0), (0.0, 0.80), (0.0, -0.80))):
        place(L, f"F1_Tea_Cushion{i}", furni.cushion, -5.1 + dx, 3.5 + dy, FL + 0.01)
    place(L, "F1_Tea_Tray", furni.tray_tea, -5.1, 3.5, FL + 0.35, 0.0)
    place(L, "F1_Tea_Screen", furni.screen, -7.55, 3.5, FL + 0.01, math.radians(90),
          w=2.0, h=1.9)
    place(L, "F1_Tea_Cabinet", lambda gb: (
        gb.box((1.2, 0.42, 1.02), (0, 0, 0.51), mat="M_WoodDark"),
        gb.box((1.26, 0.46, 0.05), (0, 0, 1.045), mat="M_Wood"),
        gb.box((1.10, 0.02, 0.02), (0, -0.23, 0.68), mat="M_Brass")),
        -2.95, 5.62, FL, math.radians(180))
    place(L, "F1_Tea_Vase", furni.vase_branch, -2.95, 5.60, FL + 1.07, 0.0, h=0.30,
          mat="M_Celadon", leaf="M_LeafPale", seed=11)
    place(L, "F1_Tea_Pendant", furni.pendant, -5.1, 3.5, Z1 - 0.10, 0.0,
          drop=1.02, r=0.22)
    place_plant(L, "F1_Tea_Plant", "pine", -7.35, 1.90, FL, 0.4, pot_r=0.24, pot_h=0.36, h=0.85)

    # ---------- 餐厅 ----------
    place(L, "F1_Dining_Table", furni.dining_table, 5.15, -3.45, FL, 0.0, w=2.0, d=1.0)
    seats = [(-0.62, -0.82, 0), (0.62, -0.82, 0), (-0.62, 0.82, math.pi),
             (0.62, 0.82, math.pi), (-1.28, 0, -math.pi / 2), (1.28, 0, math.pi / 2)]
    for i, (dx, dy, rz) in enumerate(seats):
        place(L, f"F1_Dining_Chair{i}", furni.dining_chair, 5.15 + dx, -3.45 + dy, FL, rz)
    place(L, "F1_Dining_Pendant", furni.pendant, 5.15, -3.45, Z1 - 0.12, 0.0,
          drop=1.05, r=0.30)
    place(L, "F1_Dining_Rug", furni.rug, 5.15, -3.45, FL + 0.012, 0.0, w=3.4, d=2.6,
          mat="M_RugRed", border="M_FabricOat")
    place(L, "F1_Dining_Bowl", furni.fruit_bowl, 5.15, -3.42, FL + 0.78, 0.0)
    place(L, "F1_Dining_Sideboard", lambda gb: (
        gb.box((2.2, 0.42, 0.78), (0, 0, 0.39), mat="M_Wood"),
        gb.box((2.26, 0.46, 0.05), (0, 0, 0.805), mat="M_StoneDark"),
        gb.box((2.0, 0.02, 0.02), (0, -0.22, 0.54), mat="M_Brass")),
        7.55, -3.4, FL, math.radians(90))
    place(L, "F1_Dining_Art", furni.art_frame, 5.15, -5.83, FL + 1.75, math.radians(180),
          w=1.6, h=0.9)

    # ---------- 厨房 ----------
    place(L, "F1_Kitchen_Run", furni.kitchen_run, 7.62, 1.4, FL, math.radians(-90),
          w=3.6, d=0.62)
    place(L, "F1_Kitchen_Ware", furni.kitchenware, 7.55, 0.55, FL, math.radians(-90))
    place(L, "F1_Kitchen_Dish", furni.dish_rack, 7.55, 2.35, FL + 0.90, math.radians(-90))
    place(L, "F1_Kitchen_Island", furni.island, 5.3, 1.5, FL, 0.0, w=2.3, d=0.95)
    place(L, "F1_Kitchen_Bin", furni.trash_bin, 3.05, 3.55, FL)
    place(L, "F1_Kitchen_Fridge", lambda gb: (
        gb.box((0.72, 0.70, 1.98), (0, 0, 0.99), mat="M_MetalGrey"),
        gb.box((0.02, 0.70, 1.98), (0.37, 0, 0.99), mat="M_MetalBlack"),
        gb.box((0.03, 0.06, 0.60), (-0.34, -0.33, 1.30), mat="M_Chrome")),
        2.72, 3.45, FL, 0.0)

    # ---------- 客卫 ----------
    place(L, "F1_WC_Toilet", furni.toilet, 6.2, 5.55, FL, math.radians(180))
    place(L, "F1_WC_Basin", furni.basin, 7.45, 4.55, FL, math.radians(-90),
          w=1.0, d=0.46)
    place(L, "F1_WC_Towel", furni.towel_bar, 6.25, 5.80, FL, 0.0, w=0.55)
    place(L, "F1_WC_Tile", lambda gb: (
        gb.boxb(((5.45, 8.0), (4.05, 6.0), (FL, FL + 0.02)), mat="M_StoneDark"),
        gb.boxb(((5.45, 5.52), (4.05, 6.0), (FL, FL + 2.2)), mat="M_StoneDark")),
        0, 0, 0)

    # ---------- 家政 / 储藏 ----------
    place(L, "F1_Laundry_Washer", furni.washer, 2.55, 5.58, FL, math.radians(180))
    place(L, "F1_Laundry_Dryer", furni.washer, 3.25, 5.58, FL, math.radians(180))
    place(L, "F1_Laundry_Shelf2", lambda gb: furni.bookshelf(gb, 1.4, 0.34, 2.0, 4, 12),
          4.45, 5.62, FL, math.radians(180))
    place(L, "F1_Laundry_Basket", furni.laundry_basket, 3.95, 4.75, FL, 0.0)

    # 灯具
    for name, (px, py) in (("F1_L_Ceiling1", (-5.4, -1.6)), ("F1_L_Ceiling2", (-4.8, 3.6)),
                           ("F1_L_Ceiling3", (5.2, -3.4)), ("F1_L_Ceiling4", (5.0, 1.5)),
                           ("F1_L_Ceiling5", (0.6, -4.8)), ("F1_L_Ceiling6", (6.6, 5.0))):
        place(L, name, furni.ceiling_lamp, px, py, Z1 - 0.12, 0.0, r=0.30)


def bookshelf(gb, w, d, h, shelves, seed):
    furni.bookshelf(gb, w=w, d=d, h=h, shelves=shelves, seed=seed)


def build_f2_rooms():
    """二层：主卧 / 主卫 / 衣帽间 / 次卧 / 书房 / 走廊 / 阳台。"""
    L = "F2"
    FL = Z1 + 0.03
    # ---------- 主卧 ----------
    place(L, "F2_Master_Bed", furni.bed, -5.1, -2.6, FL, math.radians(180),
          w=1.95, l=2.15)
    place(L, "F2_Master_Rug", furni.rug, -5.1, -3.3, FL + 0.012, 0.0, w=3.2, d=2.4)
    place(L, "F2_Master_Bench", furni.bench, -5.1, -4.95, FL, 0.0, w=1.5, d=0.42)
    place(L, "F2_Master_Wardrobe", furni.wardrobe, -2.52, -1.4, FL, math.radians(-90),
          w=2.2, d=0.6, h=2.4)
    place(L, "F2_Master_CurtainL", furni.curtain, -6.6, -5.66, FL, 0.0, w=1.0, h=2.3)
    place(L, "F2_Master_CurtainR", furni.curtain, -3.0, -5.66, FL, 0.0, w=1.0, h=2.3)
    place_plant(L, "F2_Master_Plant", "pine", -7.25, -0.15, FL, 0.5, pot_r=0.3, pot_h=0.46, h=1.15)
    place(L, "F2_Master_Chaise", furni.armchair, -2.65, -4.85, FL, math.radians(135),
          mat="M_FabricOat")
    place(L, "F2_Master_Books", furni.books_row, -5.98, -4.20, FL + 0.50,
          math.radians(90), w=0.26, seed=4)
    place(L, "F2_Master_Art", furni.art_frame, -5.1, 0.66, FL + 1.55, math.radians(180),
          w=1.5, h=0.85)
    place(L, "F2_Master_Slippers", furni.slippers, -3.05, -5.20, FL, math.radians(180))

    # ---------- 衣帽间 ----------
    place(L, "F2_Closet_WardrobeA", furni.wardrobe, -3.35, 0.98, FL, math.radians(180),
          w=2.4, d=0.6, h=2.3)
    place(L, "F2_Closet_WardrobeB", furni.wardrobe, -4.45, 2.35, FL, math.radians(90),
          w=1.8, d=0.58, h=2.3)
    place(L, "F2_Closet_Island", lambda gb: (
        gb.box((1.0, 0.5, 0.84), (0, 0, 0.42), mat="M_Wood"),
        gb.box((1.06, 0.56, 0.04), (0, 0, 0.86), mat="M_Marble"),
        gb.box((0.7, 0.02, 0.02), (0, -0.26, 0.60), mat="M_Brass")),
        -3.1, 2.0, FL, 0.0)

    # ---------- 主卫 ----------
    place(L, "F2_MBath_Tub", furni.bathtub, -6.9, 1.30, FL, math.radians(90))
    place(L, "F2_MBath_Basin", furni.basin, -5.55, 3.22, FL, math.radians(180),
          w=1.3, d=0.5)
    place(L, "F2_MBath_Shower", furni.shower, -7.15, 2.85, FL, 0.0, w=1.3, d=1.0)
    place(L, "F2_MBath_Toilet", furni.toilet, -5.05, 1.35, FL, math.radians(90))
    place(L, "F2_MBath_Towel", furni.towel_bar, -7.55, 0.90, FL, math.radians(90), w=0.6)
    place(L, "F2_MBath_Mat", furni.bath_mat, -6.55, 2.25, FL, 0.0)
    place(L, "F2_MBath_Tile", lambda gb: (
        gb.boxb(((-8.0, -4.85), (0.65, 3.4), (FL, FL + 0.02)), mat="M_StoneDark"),
        gb.boxb(((-8.0, -4.90), (0.65, 3.4), (FL, FL + 2.4)), mat="M_Marble")),
        0, 0, 0)

    # ---------- 次卧 ----------
    place(L, "F2_Kid_Bed", furni.bed, 4.55, -2.45, FL, math.radians(180),
          w=1.5, l=2.05)
    place(L, "F2_Kid_Desk", furni.desk, 7.05, -2.60, FL, math.radians(-90),
          w=1.5, d=0.65)
    place(L, "F2_Kid_Chair", furni.office_chair, 6.36, -2.60, FL, math.radians(-90))
    place(L, "F2_Kid_Wardrobe", furni.wardrobe, 2.48, -3.20, FL, math.radians(90),
          w=2.0, d=0.6, h=2.35)
    place(L, "F2_Kid_Rug", furni.rug, 4.75, -3.65, FL + 0.012, 0.0, w=2.4, d=1.8,
          mat="M_RugRed", border="M_FabricOat")
    place(L, "F2_Kid_Shelf", lambda gb: furni.bookshelf(gb, 1.5, 0.32, 1.9, 4, 21),
          4.75, -5.55, FL, 0.0)
    place(L, "F2_Kid_CurtainL", furni.curtain, 2.95, -5.66, FL, 0.0, w=1.0, h=2.3)
    place(L, "F2_Kid_CurtainR", furni.curtain, 6.55, -5.66, FL, 0.0, w=1.0, h=2.3)
    place(L, "F2_Kid_Art", furni.art_frame, 4.55, 0.72, FL + 1.50, math.radians(180),
          w=1.1, h=0.8)

    # ---------- 书房 ----------
    place(L, "F2_Study_Desk", furni.desk, 7.30, 2.65, FL, math.radians(-90),
          w=2.0, d=0.78)
    place(L, "F2_Study_Chair", furni.office_chair, 6.45, 2.65, FL, math.radians(-90))
    place(L, "F2_Study_Shelf", lambda gb: furni.bookshelf(gb, 2.6, 0.36, 2.35, 5, 5),
          4.30, 4.22, FL, math.radians(180))
    place(L, "F2_Study_Armchair", furni.armchair, 4.45, 1.95, FL, math.radians(160),
          mat="M_Leather")
    place(L, "F2_Study_Rug", furni.round_rug, 5.60, 2.85, FL + 0.012, 0.0, r=1.05)
    place_plant(L, "F2_Study_Plant", "pine", 2.45, 2.10, FL, 0.0, pot_r=0.3, pot_h=0.46, h=1.15)
    place(L, "F2_Study_Lamp", furni.floor_lamp, 4.10, 3.55, FL)
    place(L, "F2_Study_Bin", furni.trash_bin, 7.30, 3.90, FL)

    # ---------- 走廊 ----------
    place(L, "F2_Corridor_Console", lambda gb: (
        gb.box((1.6, 0.34, 0.78), (0, 0, 0.39), mat="M_Wood"),
        gb.box((1.66, 0.38, 0.04), (0, 0, 0.80), mat="M_StoneDark")),
        2.30, 0.92, FL, math.radians(180))
    place(L, "F2_Corridor_Vase", furni.vase_branch, 2.30, 0.92, FL + 0.82, 0.0,
          h=0.32, mat="M_Ceramic", seed=17)
    place(L, "F2_Corridor_Art", furni.art_frame, 2.30, 1.10, FL + 1.60,
          math.radians(180), w=1.2, h=1.5)
    place(L, "F2_Corridor_Clock", furni.wall_clock, -1.55, 0.10, FL + 1.75,
          math.radians(-90))

    # ---------- 阳台（朝花园） ----------
    place(L, "F2_Bal_Lounge", furni.outdoor_lounge, -4.2, -7.30, Z1 + 0.06, 0.0,
          w=1.9, d=0.8)
    place(L, "F2_Bal_Lounge2", furni.outdoor_lounge, 4.2, -7.30, Z1 + 0.06, 0.0,
          w=1.9, d=0.8)
    place(L, "F2_Bal_Table", furni.outdoor_table, 0.0, -7.45, Z1 + 0.06, 0.0, r=0.40)
    place(L, "F2_Bal_Tray", furni.tray_tea, 0.0, -7.45, Z1 + 0.46, 0.0)
    for nm, px in (("F2_Bal_PotA", -6.05), ("F2_Bal_PotB", 6.05)):
        place(L, nm, furni.potted_plant, px, -7.15, Z1 + 0.06, 0.0, r=0.28, h=0.5,
              leaf="M_LeafOlive")
    place_plant(L, "F2_Bal_PotC", "shrub", 2.10, -8.05, Z1 + 0.06, 0.0, pot_r=0.24, pot_h=0.36, h=0.85)

    for name, (px, py) in (("F2_L_1", (-5.0, -2.8)), ("F2_L_2", (4.6, -2.6)),
                           ("F2_L_3", (5.6, 2.9)), ("F2_L_4", (-3.2, 2.0))):
        place(L, name, furni.ceiling_lamp, px, py, Z2 - 0.12, 0.0, r=0.28)


def build_f3_rooms():
    """三层：客房 / 家庭厅 / 静室 / 卫生间 / 储藏 / 露台。"""
    L = "F3"
    FL = Z2 + 0.03
    MED = Z2 + 0.22          # 木榻面标高
    # ---------- 客房 ----------
    place(L, "F3_Guest_Bed", furni.bed, -5.2, -1.6, FL, math.radians(180),
          w=1.6, l=2.0)
    place(L, "F3_Guest_Chair", furni.armchair, -7.18, -1.95, FL, math.radians(70),
          mat="M_FabricOat")
    place(L, "F3_Guest_Rug", furni.rug, -5.2, -2.30, FL + 0.012, 0.0, w=2.5, d=1.7)
    place(L, "F3_Guest_Wardrobe", furni.wardrobe, -7.15, 0.28, FL, math.radians(180),
          w=1.6, d=0.58, h=2.2)
    place(L, "F3_Guest_Art", furni.art_frame, -5.2, 0.76, FL + 1.50, math.radians(180),
          w=1.2, h=0.85)
    place(L, "F3_Guest_CurtainL", furni.curtain, -7.15, -3.30, FL, 0.0, w=0.9, h=2.1)
    place(L, "F3_Guest_CurtainR", furni.curtain, -3.15, -3.30, FL, 0.0, w=0.9, h=2.1)

    # ---------- 家庭厅 ----------
    place(L, "F3_Family_Sofa", furni.sofa, 3.15, -1.3, FL, math.radians(-90),
          w=2.7, d=0.95, seats=3)
    place(L, "F3_Family_Table", furni.coffee_table, 1.35, -1.3, FL, math.radians(90),
          w=1.3, d=0.8)
    place(L, "F3_Family_Rug", furni.rug, 1.75, -1.3, FL + 0.012, 0.0, w=3.2, d=2.4,
          border="M_FabricRust")
    place(L, "F3_Family_TV", furni.tv_wall, 0.38, -1.3, FL, math.radians(-90),
          w=2.6, h=2.0)
    place(L, "F3_Family_Armchair", furni.armchair, 4.95, 0.45, FL, math.radians(215),
          mat="M_Leather")
    place_plant(L, "F3_Family_Plant", "pine", 7.10, 0.30, FL, 0.0, pot_r=0.3, pot_h=0.46, h=1.15)
    place(L, "F3_Family_Books", furni.books_row, 3.15, -2.55, FL + 0.42,
          math.radians(-90), w=0.30, seed=9)
    place(L, "F3_Family_Bin", furni.trash_bin, 6.90, -2.90, FL)

    # ---------- 静室（木榻 + 蒲团） ----------
    place(L, "F3_Med_Platform", lambda gb: (
        gb.box((4.6, 3.0, 0.16), (0, 0, 0.08), mat="M_WoodPale"),
        gb.box((4.66, 3.06, 0.03), (0, 0, 0.175), mat="M_Bamboo"),
        gb.box((4.4, 2.8, 0.02), (0, 0, 0.196), mat="M_Rug")),
        -5.0, 3.4, FL, 0.0)
    place(L, "F3_Med_Table", furni.kang_table, -5.0, 3.4, MED, 0.0,
          w=1.2, d=0.7, h=0.30)
    for i, (dx, dy) in enumerate(((-0.95, 0.0), (0.95, 0.0), (0.0, 0.98), (0.0, -0.98))):
        place(L, f"F3_Med_Cushion{i}", furni.cushion, -5.0 + dx, 3.4 + dy, MED,
              r=0.26, mat="M_FabricInk")
    place(L, "F3_Med_Tray", furni.tray_tea, -5.0, 3.4, MED + 0.31, 0.0)
    place(L, "F3_Med_Screen", furni.screen, -7.50, 3.4, MED, math.radians(90),
          w=2.0, h=1.7)
    place(L, "F3_Med_Incense", lambda gb: (
        gb.lathe([(0.10, 0), (0.13, 0.03), (0.14, 0.10), (0.09, 0.16)],
                 seg=18, center=(0, 0, 0.02), mat="M_Brass"),
        gb.cyl(0.006, 0.30, (0, 0, 0.30), seg=5, mat="M_Bark")),
        -3.05, 3.4, MED, 0.0)
    place(L, "F3_Med_Vase", furni.vase_branch, -6.35, 5.45, FL, 0.0, h=0.5,
          mat="M_Celadon", leaf="M_LeafPale", seed=11)
    place_plant(L, "F3_Med_Bamboo", "pine", -2.35, 5.35, FL, 0.0, pot_r=0.3, pot_h=0.46, h=1.15)
    place(L, "F3_Med_Pendant", furni.pendant, -5.0, 3.4, Z3 - 0.12, 0.0,
          drop=1.28, r=0.18)

    # ---------- 三层卫 ----------
    place(L, "F3_WC_Toilet", furni.toilet, 2.60, 5.55, FL, math.radians(180))
    place(L, "F3_WC_Basin", furni.basin, 3.95, 5.62, FL, math.radians(180),
          w=0.9, d=0.45)
    place(L, "F3_WC_Towel", furni.towel_bar, 2.62, 5.80, FL, 0.0, w=0.5)

    # ---------- 储藏 ----------
    place(L, "F3_Store_Shelf", lambda gb: furni.bookshelf(gb, 1.8, 0.34, 2.1, 4, 33),
          6.10, 5.62, FL, math.radians(180))
    place(L, "F3_Store_Basket", furni.laundry_basket, 4.85, 4.05, FL, 0.0)

    # ---------- 露台 ----------
    place(L, "F3_Ter_Pergola", furni.pergola, 0.0, -4.85, Z2 + 0.10, 0.0,
          w=5.0, d=2.2, h=2.45)
    place(L, "F3_Ter_Table", furni.outdoor_table, 0.0, -4.85, Z2 + 0.10, 0.0, r=0.36)
    place(L, "F3_Ter_Tray", furni.tray_tea, 0.0, -4.85, Z2 + 0.50, 0.0)
    place(L, "F3_Ter_Lounge", furni.outdoor_lounge, -3.95, -5.25, Z2 + 0.10,
          math.radians(180), w=1.8, d=0.8)
    place(L, "F3_Ter_Lounge2", furni.outdoor_lounge, 3.95, -5.25, Z2 + 0.10,
          math.radians(180), w=1.8, d=0.8)
    for i, px in enumerate((-6.6, -5.6, 5.6, 6.6)):
        place_plant(L, f"F3_Ter_Pot{i}", "shrub", px, -5.55, Z2 + 0.10, 0.0,
                    pot_r=0.27, pot_h=0.46, h=0.9)
    place(L, "F3_Ter_Lantern", furni.stone_lantern, 7.20, -4.35, Z2 + 0.10, 0.0, h=1.2)

    for name, (px, py) in (("F3_L_1", (-5.2, -1.6)), ("F3_L_2", (2.0, -1.3))):
        place(L, name, furni.ceiling_lamp, px, py, Z3 - 0.14, 0.0, r=0.26)


# ================================================================ 花园
# 禁止种树的区域（建筑/亭/甲板/车道/水面）
NO_PLANT = [
    ("house", -8.4, 8.4, -6.4, 6.4),
    ("balcony", -6.9, 6.9, -8.9, -5.9),
    ("terrace", -8.3, 8.3, -6.7, -3.1),
    ("pavilion", -19.8, -14.6, -5.4, -0.2),
    ("deck", -6.6, 6.6, -9.7, -6.2),
    ("driveway", 9.3, 19.8, -17.4, -6.6),
    ("pond", -12.3, -2.9, -16.5, -10.3),
]


def plant_ok(x, y, r=0.0, force=False):
    if force:
        return True
    for (nm, x0, x1, y0, y1) in NO_PLANT:
        if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
            print(f"[plant] SKIP {nm}: ({x:.1f},{y:.1f}) r={r}")
            return False
    return True


def build_garden():
    L = "GARDEN"
    CTX.use(L)
    # 木平台（南院，正对客厅）
    gb = GB("GARDEN_Deck")
    gb.boxb(((-6.2, 6.2), (-9.4, -6.5), (0.02, 0.14)), mat="M_WoodPale")
    for i in range(24):
        y = -9.3 + i * 0.12
        gb.boxb(((-6.1, 6.1), (y - 0.045, y + 0.045), (0.14, 0.17)), mat="M_Bamboo")
    gb.boxb(((-6.3, 6.3), (-9.5, -9.4), (0.02, 0.22)), mat="M_StoneDark")
    CTX.mesh(gb, "GARDEN_Deck")

    # 水池
    gb = GB("GARDEN_Pond")
    px0, px1, py0, py1 = -12.0, -3.2, -16.2, -10.6
    # 池壁
    for (b, mat) in ((((px0 - 0.35, px0), (py0, py1)), "M_StoneDark"),
                     (((px1, px1 + 0.35), (py0, py1)), "M_StoneDark"),
                     (((px0, px1), (py0 - 0.35, py0)), "M_StoneDark"),
                     (((px0, px1), (py1, py1 + 0.35)), "M_StoneDark")):
        gb.boxb((b[0], b[1], (-0.55, 0.16)), mat=mat)
    gb.boxb(((px0, px1), (py0, py1), (-0.62, -0.58)), mat="M_StoneDark")
    gb.boxb(((px0 + 0.02, px1 - 0.02), (py0 + 0.02, py1 - 0.02), (-0.60, -0.10)),
            mat="M_WaterDark")
    # 水面：起伏网格（有波光）
    nu, nv = 46, 30
    vs, fs = [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u = i / nu
            v = j / nv
            x = px0 + 0.05 + u * (px1 - px0 - 0.10)
            y = py0 + 0.05 + v * (py1 - py0 - 0.10)
            zz = -0.085 + 0.012 * math.sin(u * 13.0 + v * 3.0) * math.sin(v * 9.0)
            vs.append((x, y, zz))
    for j in range(nv):
        for i in range(nu):
            a0 = j * (nu + 1) + i
            fs.append([a0, a0 + 1, a0 + nu + 2, a0 + nu + 1])
    gb._add_faces(vs, fs, "M_Water")
    CTX.mesh(gb, "GARDEN_Pond")

    # 水岸石 + 汀步

    def stones_fn(gb2):
        rng = _r.Random(31)
        for i in range(9):
            t = i / 8
            x = lerp(px0 + 1.2, px1 - 1.2, t) + rng.uniform(-0.35, 0.35)
            y = py1 + 0.85 + rng.uniform(-0.25, 0.35)
            with gb2.frame(Matrix.Translation((x, y, 0.05)) @
                           Matrix.Rotation(rng.uniform(0, TAU), 4, "Z")):
                nature.rock(gb2, r=rng.uniform(0.55, 0.95), mat="M_Stone", seed=i)
        # 池中石
        for i in range(4):
            with gb2.frame(Matrix.Translation((px0 + 1.6 + i * 2.0, py0 + 1.4, -0.1)) @
                           Matrix.Rotation(rng.uniform(0, TAU), 4, "Z")):
                nature.rock(gb2, r=rng.uniform(0.6, 1.0), mat="M_StoneDark", seed=10 + i)
        # 汀步：门 → 台阶
        for i in range(11):
            y = -16.6 + i * 0.72
            x = 0.0 + (0.35 if i % 2 else -0.35)
            gb2.cyl(0.42, 0.10, (x, y, 0.045), seg=7, mat="M_StoneLight")
        # 平台东侧的园路小径
        for i in range(7):
            gb2.cyl(0.38, 0.10, (8.0 + 0.55 * i, -9.6 - 0.62 * i), seg=7, mat="M_StoneLight")
        # 石桥汀步：跨过水池西段
        for i in range(9):
            gb2.box((0.62, 0.34, 0.12), (-9.4, -15.9 + i * 0.60, 0.06), mat="M_StoneLight")
    obj(L, "GARDEN_Path", stones_fn)

    # 莲花
    def lotus_fn(gb2):
        rng = _r.Random(9)
        for i in range(18):
            x = rng.uniform(px0 + 0.8, px1 - 0.8)
            y = rng.uniform(py0 + 0.8, py1 - 0.8)
            with gb2.frame(Matrix.Translation((x, y, -0.075))):
                nature.lotus(gb2, r=rng.uniform(0.14, 0.26),
                             leaf="M_Lotus")
    obj(L, "GARDEN_Lotus", lotus_fn)

    # 竹林
    def bamboo_fn(gb2):
        for (x, y, n, rad, h) in ((-17.6, -13.6, 20, 2.0, 5.6),
                                  (-15.8, -7.4, 16, 1.7, 5.0),
                                  (17.4, -3.6, 18, 1.9, 5.4),
                                  (-13.2, 9.6, 14, 1.6, 4.8)):
            if not plant_ok(x, y, rad):
                continue
            with gb2.frame(Matrix.Translation((x, y, 0.02))):
                nature.bamboo(gb2, n=n, radius=rad, h=h, seed=int(x * 7 + y))
    obj(L, "GARDEN_Bamboo", bamboo_fn)

    # 造型松
    def pine_fn(gb2):
        for i, (x, y, h) in enumerate(((-15.0, -12.6, 4.6), (11.6, -3.4, 3.6),
                                       (-17.5, -9.2, 4.0), (16.8, 6.4, 3.8))):
            if not plant_ok(x, y, 1.6):
                continue
            assets.instance(CTX, "GARDEN", "pine", f"p{i}", x, y, 0.02,
                            height=h, rot=i * 2.1)
    obj(L, "GARDEN_Pine", pine_fn)

    # 枫树 / 乔木
    def maple_fn(gb2):
        for i, (x, y, h) in enumerate(((7.6, -11.8, 4.4), (-8.0, -9.0, 3.8))):
            if not plant_ok(x, y, 1.4):
                continue
            assets.instance(CTX, "GARDEN", "jacaranda", f"mid{i}", x, y, 0.02,
                            height=h, rot=i * 2.9)
        # 背景乔木：用 PolyHaven CC0 成品模型（jacaranda，减面到 23 万面）
        for i, (x, y, h) in enumerate(((-14.0, 9.0, 8.0), (11.0, 10.5, 7.2),
                                       (17.0, 3.0, 6.6), (-17.8, 6.2, 6.4))):
            assets.instance(CTX, "GARDEN", "jacaranda", f"big{i}", x, y, 0.02,
                            height=h, rot=i * 1.7)
    obj(L, "GARDEN_Trees", maple_fn)

    # 灌木 / 地被 / 草丛
    def shrub_fn(gb2):
        rng = _r.Random(101)
        spots = []
        for i in range(26):
            x = rng.uniform(-18.5, 18.5)
            y = rng.uniform(-16.5, 14.5)
            # 避开建筑与水池与平台
            if -9.5 < x < 9.5 and -9.8 < y < 7.6:
                continue
            if px0 - 1 < x < px1 + 1 and py0 - 1 < y < py1 + 4:
                continue
            if not plant_ok(x, y, 0.5):
                continue
            spots.append((x, y))
        # 灌木：成品模型（shrub_03，5k 面），分布在草坪与建筑周边
        placed = 0
        for i, (x, y) in enumerate(spots):
            if placed >= 16:
                break
            assets.instance(CTX, "GARDEN", "shrub", f"s{placed}", x, y, 0.02,
                            height=rng.uniform(0.85, 1.35), rot=rng.uniform(0, 6.28))
            placed += 1
        for i in range(14):
            x = -8.6 + i * 1.28
            assets.instance(CTX, "GARDEN", "shrub", f"h{i}", x, 7.2, 0.02,
                            height=rng.uniform(0.95, 1.15), rot=rng.uniform(0, 6.28))
        for i in range(8):
            assets.instance(CTX, "GARDEN", "shrub", f"w{i}", -8.9, -6.4 + i * 1.6, 0.02,
                            height=rng.uniform(0.95, 1.15), rot=rng.uniform(0, 6.28))
            assets.instance(CTX, "GARDEN", "shrub", f"e{i}", 8.9, -6.4 + i * 1.6, 0.02,
                            height=rng.uniform(0.95, 1.15), rot=rng.uniform(0, 6.28))
        # 草丛点缀
        rng2 = _r.Random(202)
        for i in range(120):
            x = rng2.uniform(-19, 19)
            y = rng2.uniform(-17, 15)
            if -9.6 < x < 9.6 and -9.9 < y < 7.7:
                continue
            if not plant_ok(x, y):
                continue
            with gb2.frame(Matrix.Translation((x, y, 0.02))):
                nature.grass_tuft(gb2, h=rng2.uniform(0.18, 0.34), seed=i)
    obj(L, "GARDEN_Shrubs", shrub_fn)

    # 池畔四角亭 + 石桥 + 水岸铺装
    obj(L, "GARDEN_Pavilion", lambda gb: arch.pavilion(
        gb, -19.4, -15.0, -5.0, -0.6, 0.02, h=2.9, mat="M_WoodDark"))
    obj(L, "GARDEN_Bridge", lambda gb: (
        gb.boxb(((-10.3, -8.5), (-13.6, -13.2), (0.10, 0.20)), mat="M_StoneLight"),
        gb.boxb(((-10.3, -8.5), (-14.2, -13.6), (-0.10, 0.10)), mat="M_StoneDark"),
        arch.railing(gb, -13.6, -10.4, -10.25, 0.20, "Y", 0.62, "M_StoneLight", "plain"),
        arch.railing(gb, -13.6, -10.4, -8.55, 0.20, "Y", 0.62, "M_StoneLight", "plain")))
    def pond_edge(gb):
        gb.boxb(((-12.9, -2.3), (-17.1, -16.2), (0.02, 0.06)), mat="M_Gravel")
        gb.boxb(((-12.9, -2.3), (-10.6, -9.8), (0.02, 0.06)), mat="M_Gravel")
        gb.boxb(((-13.3, -12.0), (-16.2, -10.6), (0.02, 0.06)), mat="M_Gravel")
        gb.boxb(((-3.2, -1.9), (-16.2, -10.6), (0.02, 0.06)), mat="M_Gravel")
        # 池岸散石
        rng = _r.Random(55)
        for i in range(16):
            x = rng.choice([-12.6, -3.5, -12.0 + i * 0.6, -3.4 + i * 0.1])
            y = rng.choice([-16.6, -10.2, -15.0 + i * 0.4, -11.0 + i * 0.35])
            with gb.frame(Matrix.Translation((x, y, 0.03)) @
                          Matrix.Rotation(rng.uniform(0, TAU), 4, "Z")):
                nature.rock(gb, r=rng.uniform(0.16, 0.34), mat="M_Stone", seed=i)
    obj(L, "GARDEN_PondEdge", pond_edge)

    # 花境 / 地被：成品模型（flower / cover），沿院墙与汀步两侧成片
    rng = _r.Random(2027)
    beds = []
    for i in range(9):          # 南院墙内侧花境
        beds.append(("flower", -17.5 + i * 3.9 + rng.uniform(-0.5, 0.5),
                     -16.4 + rng.uniform(-0.5, 0.4), 0.34))
    for i in range(7):          # 汀步两侧
        beds.append(("flower", -1.5 + (0.6 if i % 2 else -0.6),
                     -15.8 + i * 0.95, 0.30))
    for i in range(8):          # 甲板两侧地被
        beds.append(("cover", -7.4 + (i % 2) * 0.9, -7.0 - i * 0.55, 0.22))
    for i in range(6):          # 东侧车道边
        beds.append(("cover", 9.0 + rng.uniform(-0.4, 0.4), -6.2 + i * 1.2, 0.24))
    for i, (kind, x, y, h) in enumerate(beds):
        if not plant_ok(x, y, 0.3):
            continue
        assets.instance(CTX, "GARDEN", kind, f"f{i}", x, y, 0.02,
                        height=h, rot=rng.uniform(0, 6.28))

    # 石灯笼 + 户外家具 + 长凳
    L2 = "GARDEN"
    place(L2, "GARDEN_Lantern1", furni.stone_lantern, 2.6, -15.4, 0.02, 0.0, h=1.5)
    place(L2, "GARDEN_Lantern2", furni.stone_lantern, -2.6, -15.4, 0.02, 0.0, h=1.5)
    place(L2, "GARDEN_Lantern3", furni.stone_lantern, 7.4, -6.9, 0.02, 0.0, h=1.2)
    place(L2, "GARDEN_Bench", furni.bench, 14.2, -9.4, 0.02, math.radians(-90), w=1.9, d=0.44)
    # 西侧草坪上的休闲铺装平台：遮阳伞 + 圆桌 + 四把对坐扶手椅（摆在一起）
    place(L2, "GARDEN_Patio", furni.patio, -8.90, -8.60, 0.0, 0.0,
          x0=-10.9, x1=-6.9, y0=-10.4, y1=-6.9, top=0.10)
    place(L2, "GARDEN_Parasol", furni.parasol, -8.90, -8.60, 0.11, 0.0,
          r=1.55, h=2.35)
    place(L2, "GARDEN_CafeTable", furni.cafe_table, -8.90, -8.60, 0.11, 0.0, r=0.42)
    for i, (dx, dy, rz) in enumerate(((-0.78, 0.0, -90), (0.78, 0.0, 90),
                                      (0.0, -0.78, 0), (0.0, 0.78, 180))):
        place(L2, f"GARDEN_CafeChair{i}", furni.deck_chair,
              -8.90 + dx, -8.60 + dy, 0.11, math.radians(rz))
    place(L2, "GARDEN_CafeCup", lambda gb: (
        gb.lathe([(0.045, 0), (0.075, 0.03), (0.078, 0.09), (0.05, 0.12)],
                 seg=16, center=(0.10, 0.06, 0.505), mat="M_Porcelain"),
        gb.lathe([(0.045, 0), (0.075, 0.03), (0.078, 0.09), (0.05, 0.12)],
                 seg=16, center=(-0.12, -0.08, 0.505), mat="M_Porcelain")),
        -8.90, -8.60, 0.11, 0.0)

    def reeds_fn(gb2):
        for (x, y) in ((px1 - 0.6, py1 - 0.6), (px0 + 0.6, py1 - 0.4),
                       (px0 + 0.4, py0 + 0.6)):
            with gb2.frame(Matrix.Translation((x, y, -0.10))):
                nature.reeds(gb2, n=12, h=1.2, seed=int(x * 3 + y))
    obj(L, "GARDEN_Reeds", reeds_fn)


# ================================================================ 灯光与相机
def build_lights():
    sc = bpy.context.scene
    # 太阳
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 4.2
    sd.angle = math.radians(1.6)
    sd.color = (1.0, 0.94, 0.84)
    sun = bpy.data.objects.new("Sun", sd)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-38))
    sun.location = (12, -14, 18)
    # 天空补光
    fill = bpy.data.lights.new("SkyFill", "AREA")
    fill.energy = 220
    fill.size = 26
    fill.color = (0.72, 0.84, 1.0)
    fo = bpy.data.objects.new("SkyFill", fill)
    sc.collection.objects.link(fo)
    fo.location = (0, -4, 16)
    fo.rotation_euler = (math.radians(8), 0, 0)
    # 室内暖光（分层）
    interior = [(-5.2, -1.6, 2.6), (-4.8, 3.6, 2.5), (5.2, -3.4, 2.6),
                (5.0, 1.5, 2.5), (-5.0, -2.6, 5.9), (4.9, -2.6, 5.9),
                (5.6, 2.7, 5.9), (-5.2, -1.6, 8.7), (2.0, -1.3, 8.7)]
    for i, (x, y, z) in enumerate(interior):
        ld = bpy.data.lights.new(f"Lamp{i}", "POINT")
        ld.energy = 55
        ld.color = (1.0, 0.76, 0.46)
        ld.shadow_soft_size = 0.35
        try:
            ld.use_shadow = False
        except Exception:
            pass
        lo = bpy.data.objects.new(f"Lamp{i}", ld)
        sc.collection.objects.link(lo)
        lo.location = (x, y, z)


def build_cameras():
    sc = bpy.context.scene
    cams = {
        "CAM_Hero": ((28.0, -35.0, 17.0), (-0.5, -6.0, 3.6), 44),
        "CAM_Night": ((25.0, -32.0, 12.0), (-0.5, -5.0, 4.0), 46),
        "CAM_Court": ((3.0, -24.0, 5.2), (-1.0, -4.0, 3.0), 32),
        "CAM_Living": ((1.35, -3.85, 1.62), (-5.4, 0.30, 1.25), 22),
        "CAM_Axo": ((26.0, -26.0, 26.0), (0.0, -2.0, 3.0), 62),
        "CAM_East": ((31.0, -17.0, 9.5), (-1.0, -1.5, 4.6), 40),
    }
    for name, (loc, tgt, lens) in cams.items():
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        co = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(co)
        co.location = loc
        d = Vector(tgt) - Vector(loc)
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = bpy.data.objects["CAM_Hero"]


# ================================================================ 房间标注
def build_rooms():
    R = CTX.room
    R("garden", "南园 · 前庭", "South Garden", "GARDEN", (0, 0.6, -11.5), 210,
      "月洞门 / 睡莲池 / 竹林 / 汀步")
    R("deck", "木平台", "Timber Deck", "GARDEN", (0, 0.3, -8.0), 33,
      "整木铺装，正对客厅落地窗")
    R("entry", "门厅", "Foyer", "F1", (0.8, 1.6, -4.9), 12.6, "玄关条案 + 吊灯")
    R("living", "客厅", "Living Room", "F1", (-4.4, 1.6, -1.4), 56.0,
      "格栅电视墙 / 布艺沙发 / 落地窗")
    R("dining", "餐厅", "Dining Room", "F1", (5.2, 1.6, -3.4), 23.0,
      "八人长桌 + 长吊灯")
    R("kitchen", "厨房", "Kitchen", "F1", (5.2, 1.6, 1.6), 24.0,
      "中岛 + 高柜 + 灶台")
    R("tea", "茶室", "Tea Room", "F1", (-5.0, 1.7, 3.6), 28.0,
      "罗汉床 / 屏风 / 茶具")
    R("wc1", "客卫", "Guest Bath", "F1", (6.6, 1.4, 5.0), 5.2, "台盆 + 坐便")
    R("stair", "楼梯间", "Stair Core", "F1", (0, 2.0, 3.6), 14.0,
      "双跑木踏步 + 钢索扶手")
    R("master", "主卧", "Master Bedroom", "F2", (-5.0, 5.0, -2.8), 40.0,
      "1.95m 大床 / 羊毛地毯 / 飘窗")
    R("mbath", "主卫", "Master Bath", "F2", (-6.2, 5.0, 2.0), 12.0,
      "独立浴缸 / 干湿分离")
    R("closet", "衣帽间", "Walk-in Closet", "F2", (-3.2, 5.0, 2.0), 9.0,
      "U 型柜体 + 中岛")
    R("kid", "次卧", "Second Bedroom", "F2", (5.0, 5.0, -3.2), 27.0,
      "1.5m 床 + 书桌")
    R("study", "书房", "Study", "F2", (5.6, 5.0, 2.7), 22.0,
      "整墙书架 / 单人皮椅")
    R("balcony", "阳台", "Balcony", "F2", (0, 4.3, -7.4), 26.0,
      "木栏杆 / 户外躺椅 / 花池")
    R("guest", "客房", "Guest Room", "F3", (-5.2, 8.0, -1.6), 27.0,
      "1.6m 床 + 卧榻")
    R("family", "家庭厅", "Family Lounge", "F3", (2.2, 8.0, -1.2), 34.0,
      "沙发 + 影音墙")
    R("med", "静室", "Meditation Room", "F3", (-5.0, 8.0, 3.4), 26.0,
      "木榻 / 蒲团 / 香炉 / 屏风")
    R("terrace", "露台", "Roof Terrace", "F3", (0, 7.4, -4.9), 34.0,
      "木廊架 / 户外家具 / 石灯")
    R("roof", "歇山屋顶", "Hipped Roof", "ROOF", (0, 11.0, 1.2), 0,
      "深灰筒瓦 / 四角起翘")


# ================================================================ 导出
def export_all():
    sc = bpy.context.scene
    # rooms.json
    rooms = dict(rooms=CTX.rooms,
                 meta=dict(title="新中式三层别墅 · 现代中式",
                           units="m", up="Y",
                           floors={"SITE": "场地", "GARDEN": "花园", "F1": "一层 · 会客与茶叙",
                                   "F2": "二层 · 居寝与书房", "F3": "三层 · 家庭厅与露台",
                                   "ROOF": "屋顶"}))
    with open(os.path.join(HERE, "rooms.json"), "w", encoding="utf-8") as f:
        json.dump(rooms, f, ensure_ascii=False, indent=1)

    with open(os.path.join(HERE, "walls.json"), "w", encoding="utf-8") as f:
        json.dump(WALLS, f)

    # GLB
    props = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    kw = dict(filepath=os.path.join(HERE, "villa.glb"), export_format="GLB",
              export_apply=True, export_yup=True, use_selection=False,
              export_cameras=False, export_lights=False, export_extras=True,
              export_materials="EXPORT", export_image_format="AUTO")
    kw = {k: v for k, v in kw.items() if k in props}
    bpy.ops.export_scene.gltf(**kw)
    # blend
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "villa.blend"))


def main():
    global CTX
    print("[villa] clean")
    clean()
    setup_world()
    mats.build_all()
    CTX = kit.Ctx()
    for lay in ("SITE", "GARDEN", "F1", "F2", "F3", "ROOF"):
        CTX.coll(lay)
    print("[villa] site")
    build_site()
    print("[villa] shell")
    build_shell()
    print("[villa] doors")
    details.add_doors(CTX, obj, Z1, Z2, Z3, F3Y0, BX0, BX1, BY0, BY1, WALL_T, PAR_T)
    details.eave_corners(obj, Z1, Z2, F3Y0, BY0, BY1, BX0, BX1)
    print("[villa] f1")
    build_f1_rooms()
    print("[villa] f2")
    build_f2_rooms()
    print("[villa] f3")
    build_f3_rooms()
    print("[villa] garden")
    build_garden()
    print("[villa] lights")
    build_lights()
    print("[villa] cameras")
    build_cameras()
    build_rooms()
    print("[villa] objects =", len(CTX.objects))
    print("[villa] export")
    export_all()
    print("[villa] DONE")


if __name__ == "__main__":
    main()
