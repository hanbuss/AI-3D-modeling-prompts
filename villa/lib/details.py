# -*- coding: utf-8 -*-
"""室内门扇 + 檐角补件 + 竖向木饰带细节（在主壳之后调用）。"""
import math
from mathutils import Matrix
from . import arch
from .kit import GB, D


def interior_doors(L, Z1, Z2, Z3, F3Y0, BX0, BX1, BY0, BY1, WALL_T, PAR_T,
                   obj, layer="F1"):
    """在已有洞口里装门扇（半开），按层各调一次。"""
    pass


def add_doors(ctx, objfunc, Z1, Z2, Z3, F3Y0, BX0, BX1, BY0, BY1, WALL_T, PAR_T,
              mat="M_WoodDark"):
    """objfunc(layer, name, fn) 是本工程里的 obj()。"""
    doors = [
        # (layer, name, axis, 洞口 a0,a1, 墙厚 t, 墙位置 b, c0, c1, 开度)
        ("F1", "D_Tea", "X", -7.2, -6.4, PAR_T, 1.4, 0.16, 2.40, 0.9),
        ("F1", "D_Laundry", "X", 2.2, 3.4, PAR_T, 4.0, 0.16, 2.30, 0.35),
        ("F1", "D_WC1", "Y", 4.6, 5.6, PAR_T, 5.4, 0.16, 2.30, -0.30),
        ("F2", "D_Master", "Y", -3.6, -2.4, PAR_T, -1.8, Z1 + 0.03, Z2 - 0.40, 0.8),
        ("F2", "D_MBath", "Y", 1.50, 2.55, PAR_T, -4.8, Z1 + 0.03, Z2 - 0.40, -0.30),
        ("F2", "D_Kid", "X", 3.4, 4.6, PAR_T, -1.0, Z1 + 0.03, Z2 - 0.40, 0.28),
        ("F2", "D_WC2", "X", 2.4, 3.6, PAR_T, 4.4, Z1 + 0.03, Z2 - 0.40, -0.28),
        ("F2", "D_Laundry2", "X", 5.4, 6.6, PAR_T, 4.4, Z1 + 0.03, Z2 - 0.40, 0.25),
        ("F3", "D_Guest", "Y", -2.6, -1.4, PAR_T, -2.2, Z2 + 0.03, Z3 - 0.40, 0.85),
        ("F3", "D_Med", "X", -6.4, -5.2, PAR_T, 0.8, Z2 + 0.03, Z3 - 0.40, -0.30),
        ("F3", "D_Store", "X", 5.2, 6.6, PAR_T, 3.4, Z2 + 0.03, Z3 - 0.40, 0.55),
    ]

    def one(d):
        layer, name, axis, a0, a1, t, b, c0, c1, op = d

        def fn(gb):
            arch.door(gb, a0, a1, c0, c1, b - t / 2, b + t / 2, axis, mat, op)
        objfunc(layer, name, fn)

    for d in doors:
        one(d)
    print(f"[doors] {len(doors)} 樘室内门")


def eave_corners(objfunc, Z1, Z2, F3Y0, BY0, BY1, BX0, BX1, out=1.0, drop=0.55,
                 mat="M_Tile"):
    """给 F2 / F3 披檐补四个转角戗檐块（两带交接处的缺口）。"""
    for layer, z, y0, y1, o, dp in (
            ("ROOF", Z1 + 0.24, BY0, BY1, 0.92, 0.52),
            ("ROOF", Z2 + 0.30, F3Y0, BY1, 1.05, 0.60)):
        def fn(gb, z=z, y0=y0, y1=y1, o=o, dp=dp):
            for sx in (BX0, BX1):
                for sy in (y0, y1):
                    cx = sx + (o * 0.55 if sx > 0 else -o * 0.55)
                    cy = sy + (o * 0.55 if sy > 0 else -o * 0.55)
                    gb.box((o * 1.12, o * 1.12, 0.16), (cx, cy, z - dp * 0.55),
                           mat=mat)
                    gb.box((o * 1.16, o * 1.16, 0.07), (cx, cy, z - dp * 0.55 - 0.11),
                           mat="M_TileEdge")
        objfunc(layer, f"ROOF_Corner_{int(z * 10)}", fn)
