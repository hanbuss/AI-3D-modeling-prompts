"""家具与软装构件库。每个函数局部坐标：原点在落地中心，Z 向上。"""
import math
import random
from mathutils import Vector, Matrix, Euler
from .kit import GB, D, TAU, lerp

RNG = random.Random(20261106)


def L(gb, x, y, z=0.0, rot=0.0, sx=1.0, sy=1.0):
    return gb.frame(Matrix.Translation((x, y, z)) @
                    Matrix.Rotation(rot, 4, "Z") @
                    Matrix.Diagonal((sx, sy, 1.0, 1.0)))


def rbox(gb, size, center, mat, r=0.02, nx=3, ny=3):
    """带圆角的盒子（用堆叠网格近似）：用于坐垫、被褥。"""
    sx, sy, sz = size
    cx, cy, cz = center
    gb.box((sx - 2 * r, sy, sz), (cx, cy, cz), mat=mat)
    gb.box((sx, sy - 2 * r, sz), (cx, cy, cz), mat=mat)
    # 倒角顶
    gb.box((sx - 2 * r, sy - 2 * r, sz + 0.004), (cx, cy, cz), mat=mat)


# --------------------------------------------------------------- 客厅
def sofa(gb, w=2.9, d=0.95, seats=3, mat="M_FabricCream", leg="M_WoodDark",
         pillows=True):
    h_seat = 0.40
    h_back = 0.80
    arm = 0.16
    # 底座
    gb.box((w, d, 0.16), (0, 0, 0.22), mat=mat)
    # 靠背
    gb.box((w, 0.20, h_back), (0, -d / 2 + 0.10, h_back / 2 + 0.05), mat=mat)
    gb.box((w - 2 * arm, 0.13, 0.42), (0, -d / 2 + 0.18, h_back - 0.06), mat=mat)
    # 扶手
    for s in (-1, 1):
        gb.box((arm, d, 0.52), (s * (w / 2 - arm / 2), 0, 0.30), mat=mat)
        gb.box((arm + 0.03, d + 0.02, 0.05), (s * (w / 2 - arm / 2), 0, 0.56), mat=mat)
    # 坐垫
    inner = w - 2 * arm
    cw = inner / seats
    for i in range(seats):
        cx = -inner / 2 + cw * (i + 0.5)
        rbox(gb, (cw - 0.03, d - 0.34, 0.16), (cx, 0.10, h_seat), "M_FabricOat", r=0.04)
        rbox(gb, (cw - 0.06, d - 0.42, 0.09), (cx, 0.10, h_seat + 0.13), mat, r=0.03)
    # 抱枕
    if pillows:
        for i, (cx, rz) in enumerate(((-inner / 2 + 0.34, 0.14), (inner / 2 - 0.34, -0.1))):
            with gb.frame(Matrix.Translation((cx, -d / 2 + 0.30, 0.60)) @
                          Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(D(8), 4, "X")):
                gb.box((0.42, 0.12, 0.42), (0, 0, 0), mat="M_FabricRust" if i == 0 else "M_FabricGrey")
    # 腿
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.cyl(0.028, 0.22, (sx * (w / 2 - 0.14), sy * (d / 2 - 0.14), 0.11),
                   seg=8, mat=leg)


def armchair(gb, w=0.86, d=0.86, mat="M_Leather"):
    gb.box((w, d, 0.34), (0, 0, 0.26), mat=mat)
    gb.box((w, 0.16, 0.62), (0, -d / 2 + 0.08, 0.62), mat=mat)
    for s in (-1, 1):
        gb.box((0.12, d, 0.34), (s * (w / 2 - 0.06), 0, 0.46), mat=mat)
    rbox(gb, (w - 0.26, d - 0.24, 0.12), (0, 0.04, 0.48), "M_FabricCream", r=0.03)
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.cyl(0.024, 0.16, (sx * (w / 2 - 0.10), sy * (d / 2 - 0.10), 0.08),
                   seg=8, mat="M_WoodDark")


def coffee_table(gb, w=1.5, d=0.85, h=0.38):
    gb.box((w, d, 0.055), (0, 0, h), mat="M_Wood")
    gb.box((w - 0.1, d - 0.1, 0.02), (0, 0, h + 0.035), mat="M_StoneLight")
    gb.box((w - 0.4, d - 0.3, 0.10), (0, 0, h - 0.11), mat="M_Wood")
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.box((0.06, 0.06, h - 0.03), (sx * (w / 2 - 0.09), sy * (d / 2 - 0.09), (h - 0.03) / 2),
                   mat="M_WoodDark")
    # 桌面摆件
    gb.cyl(0.075, 0.03, (-w / 2 + 0.30, 0.06, h + 0.06), seg=20, mat="M_Celadon",
           r_top=0.06)
    gb.sphere(0.05, (-w / 2 + 0.30, 0.06, h + 0.13), seg=10, rings=7, mat="M_Celadon")
    for i, (bx, by) in enumerate(((0.05, 0.10), (0.16, 0.02), (0.02, -0.02))):
        gb.box((0.30, 0.22, 0.035), (bx, by, h + 0.055 + i * 0.036), mat="M_BookPage")
        gb.box((0.31, 0.16, 0.030), (bx, by, h + 0.055 + i * 0.036), mat="M_BookSpine")
    gb.box((0.16, 0.16, 0.02), (w / 2 - 0.28, -0.10, h + 0.05), mat="M_Brass")


def side_table(gb, r=0.25, h=0.52):
    gb.cyl(r, 0.035, (0, 0, h), seg=24, mat="M_StoneLight")
    gb.cyl(0.03, h, (0, 0, h / 2), seg=10, mat="M_MetalBlack")
    gb.cyl(r * 0.7, 0.02, (0, 0, 0.012), seg=20, mat="M_MetalBlack")


def rug(gb, w=3.6, d=2.4, mat="M_Rug", border="M_FabricGrey", z=0.012):
    gb.box((w, d, 0.018), (0, 0, z), mat=mat)
    gb.box((w - 0.12, 0.06, 0.020), (0, d / 2 - 0.10, z + 0.002), mat=border)
    gb.box((w - 0.12, 0.06, 0.020), (0, -d / 2 + 0.10, z + 0.002), mat=border)
    gb.box((0.06, d - 0.12, 0.020), (w / 2 - 0.10, 0, z + 0.002), mat=border)
    gb.box((0.06, d - 0.12, 0.020), (-w / 2 + 0.10, 0, z + 0.002), mat=border)


def tv_wall(gb, w=3.4, h=2.3, mat="M_WoodDark"):
    """整面木格栅电视墙 + 悬浮柜 + 电视"""
    for i in range(int(w / 0.30)):
        x = -w / 2 + 0.15 + i * 0.30
        gb.box((0.055, 0.06, h), (x, 0, h / 2), mat=mat)
    gb.box((w, 0.10, 0.10), (0, 0, h), mat=mat)
    gb.box((w, 0.10, 0.10), (0, 0, 0.0), mat=mat)
    # 悬浮柜
    gb.box((2.6, 0.42, 0.34), (0, 0.26, 0.36), mat="M_Wood")
    gb.box((2.62, 0.03, 0.02), (0, 0.475, 0.36), mat="M_Brass")
    # 电视
    gb.box((1.62, 0.05, 0.94), (0, 0.08, 1.32), mat="M_MetalBlack")
    gb.box((1.55, 0.012, 0.88), (0, 0.108, 1.32), mat="M_Screen")
    gb.box((0.36, 0.05, 0.06), (0, 0.30, 0.60), mat="M_MetalBlack")
    # 摆件
    gb.lathe([(0.06, 0), (0.10, 0.05), (0.12, 0.16), (0.08, 0.30), (0.09, 0.34)],
             seg=18, center=(-1.0, 0.26, 0.53), mat="M_Ceramic")
    gb.box((0.26, 0.20, 0.16), (0.95, 0.26, 0.62), mat="M_BookSpineB")
    gb.box((0.22, 0.18, 0.20), (1.15, 0.26, 0.65), mat="M_BookSpine")


def floor_lamp(gb, h=1.62):
    gb.cyl(0.16, 0.02, (0, 0, 0.01), seg=20, mat="M_MetalBlack")
    gb.cyl(0.025, h, (0, 0, h / 2), seg=10, mat="M_MetalBlack")
    gb.lathe([(0.10, 0), (0.17, 0.10), (0.18, 0.22), (0.10, 0.30)],
             seg=22, center=(0, 0, h - 0.02), mat="M_LampShade")


def pendant(gb, z=0.0, drop=0.9, r=0.22, mat="M_LampShade"):
    gb.cyl(0.012, drop, (0, 0, z - drop / 2), seg=6, mat="M_MetalBlack")
    gb.lathe([(r * 0.35, 0), (r * 0.9, 0.08), (r, 0.16), (r * 0.55, 0.26)],
             seg=24, center=(0, 0, z - drop - 0.26), mat=mat)
    gb.cyl(r * 0.6, 0.01, (0, 0, z - drop - 0.005), seg=20, mat="M_Brass")


def ceiling_lamp(gb, z=0.0, r=0.34):
    gb.cyl(r * 0.55, 0.02, (0, 0, z - 0.01), seg=24, mat="M_LampDark")
    gb.sphere(r, (0, 0, z - r * 0.55), seg=20, rings=14, mat="M_LampShade",
              scale=(1, 1, 0.72))


def wall_sconce(gb, z=1.8, x=0.0, y=0.0):
    gb.box((0.10, 0.05, 0.14), (x, y, z), mat="M_Brass")
    gb.lathe([(0.03, 0), (0.09, 0.03), (0.10, 0.14), (0.05, 0.20)],
             seg=14, center=(x, y - 0.10, z - 0.02), mat="M_LampShade")


# --------------------------------------------------------------- 餐厅
def dining_table(gb, w=1.9, d=0.95, h=0.75):
    gb.box((w, d, 0.06), (0, 0, h), mat="M_Wood")
    gb.box((w - 0.24, d - 0.24, 0.03), (0, 0, h - 0.045), mat="M_WoodDark")
    for sx in (-1, 1):
        gb.box((0.09, d - 0.24, h - 0.06), (sx * (w / 2 - 0.16), 0, (h - 0.06) / 2),
               mat="M_WoodDark")
        gb.box((0.06, 0.06, 0.06), (sx * (w / 2 - 0.16), 0, 0.03), mat="M_Brass")
    # 桌面：茶壶与碗
    gb.lathe([(0.06, 0), (0.10, 0.04), (0.11, 0.12), (0.06, 0.16), (0.05, 0.18)],
             seg=18, center=(0, 0, h + 0.03), mat="M_Porcelain")
    for i in range(4):
        gb.cyl(0.075, 0.012, (-0.5 + 0.33 * i, 0.18, h + 0.036), seg=16, mat="M_Porcelain")


def dining_chair(gb, mat="M_Wood", seat="M_FabricOat"):
    h = 0.46
    gb.box((0.44, 0.42, 0.055), (0, 0, h), mat=seat)
    gb.box((0.42, 0.05, 0.42), (0, -0.19, h + 0.24), mat=mat)
    for i in range(3):
        gb.box((0.33, 0.02, 0.03), (0, -0.185, h + 0.12 + i * 0.10), mat=mat)
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.box((0.035, 0.035, h), (sx * 0.19, sy * 0.17, h / 2), mat=mat)
    gb.box((0.30, 0.03, 0.03), (0, 0.16, 0.16), mat=mat)


# --------------------------------------------------------------- 厨房
def kitchen_run(gb, w=4.2, d=0.62, mat="M_WoodLight", tall=True):
    gb.box((w, d, 0.86), (0, 0, 0.44), mat=mat)
    gb.box((w + 0.04, d + 0.04, 0.045), (0, 0, 0.885), mat="M_StoneLight")
    gb.box((w, 0.03, 0.10), (0, -d / 2 + 0.03, 0.08), mat="M_MetalBlack")
    # 柜门分缝
    n = max(3, int(w / 0.62))
    for i in range(1, n):
        x = -w / 2 + w * i / n
        gb.box((0.008, 0.012, 0.80), (x, -d / 2 - 0.002, 0.44), mat="M_MetalGrey")
    for i in range(n):
        x = -w / 2 + w * (i + 0.5) / n
        gb.box((0.16, 0.015, 0.015), (x, -d / 2 - 0.02, 0.80), mat="M_Brass")
    # 水槽
    gb.box((0.62, 0.42, 0.02), (-w / 4, 0, 0.905), mat="M_MetalGrey")
    gb.cyl(0.02, 0.26, (-w / 4, -d / 2 + 0.16, 1.02), seg=10, mat="M_Chrome")
    gb.box((0.20, 0.03, 0.03), (-w / 4, -d / 2 + 0.22, 1.14), mat="M_Chrome")
    # 灶台
    gb.box((0.60, 0.42, 0.02), (w / 4, 0, 0.912), mat="M_MetalBlack")
    for (dx, dy) in ((-0.14, -0.10), (0.14, -0.10), (-0.14, 0.10), (0.14, 0.10)):
        gb.cyl(0.055, 0.012, (w / 4 + dx, dy, 0.922), seg=14, mat="M_MetalGrey")
    # 吊柜
    if tall:
        gb.box((w * 0.86, 0.36, 0.72), (0, 0.14, 1.72), mat=mat)
        gb.box((w * 0.86, 0.02, 0.008), (0, -0.05, 1.40), mat="M_MetalGrey")
        # 油烟机
        gb.box((0.68, 0.44, 0.16), (w / 4, 0.06, 1.92), mat="M_MetalGrey")
        gb.box((0.30, 0.30, 0.60), (w / 4, 0.16, 2.28), mat="M_MetalGrey")


def island(gb, w=2.2, d=0.92, mat="M_WoodLight"):
    gb.box((w, d, 0.84), (0, 0, 0.43), mat=mat)
    gb.box((w + 0.10, d + 0.16, 0.055), (0, 0.02, 0.885), mat="M_Marble")
    gb.box((w - 0.1, 0.02, 0.02), (0, -d / 2 - 0.01, 0.60), mat="M_Brass")
    for i in range(3):
        gb.box((0.008, 0.012, 0.62), (-w / 2 + w * (i + 1) / 4, -d / 2 - 0.002, 0.45),
               mat="M_MetalGrey")
    # 高脚凳
    for x in (-w / 2 + 0.34, w / 2 - 0.34):
        gb.cyl(0.035, 0.62, (x, -d / 2 - 0.30, 0.31), seg=10, mat="M_MetalBlack")
        gb.cyl(0.17, 0.055, (x, -d / 2 - 0.30, 0.64), seg=20, mat="M_Leather")
        gb.cyl(0.15, 0.02, (x, -d / 2 - 0.30, 0.20), seg=16, mat="M_MetalBlack")


# --------------------------------------------------------------- 卧室
def bed(gb, w=1.9, l=2.1, mat="M_Linen", head="M_FabricGrey"):
    gb.box((w + 0.10, l + 0.10, 0.28), (0, 0, 0.14), mat="M_WoodDark")
    rbox(gb, (w, l, 0.26), (0, 0.02, 0.40), mat, r=0.05)
    # 被子
    rbox(gb, (w + 0.04, l * 0.72, 0.10), (0, 0.58, 0.55), "M_FabricOat", r=0.04)
    gb.box((w + 0.04, 0.20, 0.06), (0, 0.30, 0.60), mat="M_FabricRust")
    # 枕头
    for dx in (-w / 4, w / 4):
        with gb.frame(Matrix.Translation((dx, -l / 2 + 0.24, 0.60)) @
                      Matrix.Rotation(D(-12), 4, "X")):
            gb.box((0.62, 0.36, 0.15), (0, 0, 0), mat="M_Linen")
    gb.box((w * 0.9, 0.05, 0.10), (0, 0.16, 0.60), mat="M_FabricGrey")
    # 床头板
    gb.box((w + 0.34, 0.10, 1.10), (0, -l / 2 - 0.10, 0.60), mat=head)
    for i in range(6):
        gb.box((0.02, 0.02, 0.90), (-1.1 + i * 0.44, -l / 2 - 0.16, 0.62), mat="M_Brass")
    # 床头柜
    for s in (-1, 1):
        gb.box((0.46, 0.40, 0.46), (s * (w / 2 + 0.34), -l / 2 + 0.16, 0.24), mat="M_Wood")
        gb.box((0.44, 0.02, 0.02), (s * (w / 2 + 0.34), -l / 2 - 0.04, 0.36), mat="M_Brass")
        # 台灯
        gb.cyl(0.07, 0.14, (s * (w / 2 + 0.34), -l / 2 + 0.16, 0.54), seg=14,
               mat="M_Ceramic")
        gb.lathe([(0.09, 0), (0.14, 0.06), (0.15, 0.17), (0.09, 0.24)],
                 seg=18, center=(s * (w / 2 + 0.34), -l / 2 + 0.16, 0.61),
                 mat="M_LampShade")


def wardrobe(gb, w=3.0, d=0.62, h=2.45, mat="M_Wood"):
    gb.box((w, d, h), (0, 0, h / 2), mat=mat)
    n = max(3, int(w / 0.7))
    for i in range(1, n):
        gb.box((0.014, 0.02, h - 0.2), (-w / 2 + w * i / n, -d / 2 - 0.002, h / 2), mat="M_WoodDark")
    for i in range(n):
        x = -w / 2 + w * (i + 0.5) / n
        gb.box((0.02, 0.03, 0.34), (x, -d / 2 - 0.03, h * 0.55), mat="M_Brass")
    gb.box((w + 0.04, d + 0.04, 0.04), (0, 0, h + 0.02), mat="M_WoodDark")


def desk(gb, w=1.7, d=0.72, h=0.75):
    gb.box((w, d, 0.05), (0, 0, h), mat="M_Wood")
    for s in (-1, 1):
        gb.box((0.06, d - 0.10, h - 0.05), (s * (w / 2 - 0.12), 0, (h - 0.05) / 2),
               mat="M_WoodDark")
    gb.box((w - 0.30, d - 0.16, 0.10), (0, 0, h - 0.10), mat="M_Wood")
    # 台面：笔筒 + 书 + 笔电
    gb.cyl(0.05, 0.13, (-w / 2 + 0.22, 0.10, h + 0.09), seg=14, mat="M_Ceramic")
    for i in range(3):
        gb.box((0.30, 0.22, 0.03), (w / 2 - 0.34, 0.16, h + 0.05 + i * 0.032), mat="M_BookPage")
    gb.box((0.34, 0.24, 0.018), (0.05, 0.02, h + 0.034), mat="M_MetalGrey")
    gb.box((0.34, 0.01, 0.22), (0.05, -0.11, h + 0.14), mat="M_MetalGrey")
    # 桌灯
    gb.cyl(0.09, 0.02, (-w / 2 + 0.24, -0.20, h + 0.035), seg=16, mat="M_MetalBlack")
    gb.cyl(0.012, 0.42, (-w / 2 + 0.24, -0.20, h + 0.24), seg=8, mat="M_MetalBlack")
    gb.lathe([(0.05, 0), (0.10, 0.03), (0.11, 0.12), (0.05, 0.17)], seg=16,
             center=(-w / 2 + 0.24, -0.20, h + 0.42), mat="M_LampShade")


def office_chair(gb, mat="M_Leather"):
    gb.cyl(0.30, 0.05, (0, 0, 0.05), seg=20, mat="M_MetalBlack")
    gb.cyl(0.045, 0.34, (0, 0, 0.24), seg=10, mat="M_MetalBlack")
    gb.box((0.50, 0.48, 0.09), (0, 0, 0.46), mat=mat)
    gb.box((0.48, 0.10, 0.52), (0, -0.20, 0.78), mat=mat)
    gb.box((0.44, 0.08, 0.06), (0, -0.18, 1.02), mat=mat)
    for s in (-1, 1):
        gb.box((0.06, 0.42, 0.05), (s * 0.27, 0.02, 0.56), mat="M_MetalBlack")


def bookshelf(gb, w=2.6, d=0.36, h=2.4, shelves=5, seed=1):
    rng = random.Random(seed)
    gb.box((0.05, d, h), (-w / 2, 0, h / 2), mat="M_Wood")
    gb.box((0.05, d, h), (w / 2, 0, h / 2), mat="M_Wood")
    gb.box((w, d, 0.05), (0, 0, h), mat="M_Wood")
    gb.box((w, d, 0.05), (0, 0, 0.02), mat="M_Wood")
    gb.box((w, 0.03, h), (0, d / 2 - 0.015, h / 2), mat="M_WoodDark")
    for s in range(shelves):
        z = 0.05 + (h - 0.10) * s / (shelves - 1)
        gb.box((w - 0.10, d, 0.035), (0, 0, z), mat="M_Wood")
        if s == shelves - 1:
            continue
        x = -w / 2 + 0.12
        while x < w / 2 - 0.16:
            bw = rng.uniform(0.035, 0.075)
            bh = rng.uniform(0.22, 0.34)
            mat = rng.choice(["M_BookSpine", "M_BookSpineB", "M_BookPage",
                              "M_FabricRust", "M_Lacquer"])
            gb.box((bw, d * 0.78, bh), (x + bw / 2, -0.01, z + 0.018 + bh / 2), mat=mat)
            x += bw + 0.004
            if rng.random() < 0.04:
                x += 0.10


def book_stack(gb, n=4, size=(0.26, 0.19), z0=0.0):
    for i in range(n):
        gb.box((size[0] - i * 0.01, size[1] - i * 0.005, 0.032),
               (0, 0, z0 + 0.016 + i * 0.034),
               mat=RNG.choice(["M_BookPage", "M_BookSpine", "M_BookSpineB"]))


# --------------------------------------------------------------- 卫生间
def bathtub(gb, l=1.72, w=0.82, h=0.56):
    gb.box((l, w, h), (0, 0, h / 2), mat="M_Marble")
    # 内胆（凹槽用 4 面内壁 + 底）
    zt = h - 0.06
    gb.box((l - 0.22, w - 0.22, 0.06), (0, 0, zt - 0.10), mat="M_Water")
    gb.box((l - 0.16, w - 0.16, 0.02), (0, 0, zt), mat="M_Marble")
    gb.cyl(0.02, 0.22, (l / 2 - 0.16, 0, h + 0.10), seg=10, mat="M_Chrome")
    gb.box((0.16, 0.03, 0.03), (l / 2 - 0.24, 0, h + 0.20), mat="M_Chrome")


def shower(gb, w=1.2, d=1.2, h=2.2):
    gb.box((w, d, 0.04), (0, 0, 0.02), mat="M_StoneDark")
    gb.box((w, 0.012, h), (0, -d / 2, h / 2), mat="M_Glass")
    gb.box((0.012, d, h), (-w / 2, 0, h / 2), mat="M_Glass")
    gb.box((w, 0.03, 0.03), (0, -d / 2, h), mat="M_Chrome")
    gb.box((0.03, d, 0.03), (-w / 2, 0, h), mat="M_Chrome")
    gb.cyl(0.012, 1.0, (0, -d / 2 + 0.06, 1.6), seg=8, mat="M_Chrome")
    gb.cyl(0.11, 0.02, (0, -d / 2 + 0.10, 2.10), seg=20, mat="M_Chrome")
    gb.cyl(0.02, 0.10, (0.18, -d / 2 + 0.06, 1.05), seg=8, mat="M_Chrome")


def toilet(gb):
    gb.box((0.36, 0.20, 0.36), (0, -0.20, 0.52), mat="M_Porcelain")
    gb.cyl(0.19, 0.36, (0, -0.02, 0.18), seg=20, mat="M_Porcelain", r_top=0.16)
    gb.cyl(0.20, 0.04, (0, -0.02, 0.38), seg=22, mat="M_Porcelain")
    gb.box((0.36, 0.42, 0.03), (0, -0.02, 0.40), mat="M_Porcelain")
    gb.box((0.10, 0.02, 0.02), (0, -0.30, 0.72), mat="M_Chrome")


def basin(gb, w=1.1, d=0.50, h=0.82):
    """台盆柜：柜体落地，台面 0.82，上置盆 + 龙头 + 镜子。"""
    gb.box((w, d, 0.09), (0, 0, h - 0.045), mat="M_Marble")
    gb.box((w - 0.06, d - 0.06, h - 0.13), (0, 0, (h - 0.09) / 2), mat="M_Wood")
    gb.box((w - 0.02, 0.02, h - 0.20), (0, -d / 2 + 0.01, (h - 0.09) / 2),
           mat="M_WoodDark")
    gb.box((0.42, 0.30, 0.14), (0, 0, h + 0.07), mat="M_Porcelain")
    gb.cyl(0.018, 0.22, (0, -0.16, h + 0.13), seg=10, mat="M_Chrome")
    gb.box((0.04, 0.14, 0.03), (0, -0.10, h + 0.24), mat="M_Chrome")
    # 镜子
    gb.box((w - 0.12, 0.04, 0.86), (0, -d / 2 + 0.03, h + 0.66), mat="M_Mirror")
    gb.box((w - 0.04, 0.03, 0.02), (0, -d / 2 + 0.03, h + 1.10), mat="M_Brass")


def washer(gb):
    gb.box((0.60, 0.62, 0.85), (0, 0, 0.425), mat="M_MetalGrey")
    gb.cyl(0.20, 0.02, (0, -0.32, 0.48), axis="Y", seg=22, mat="M_MetalBlack")
    gb.cyl(0.17, 0.03, (0, -0.33, 0.48), axis="Y", seg=22, mat="M_Chrome")


# --------------------------------------------------------------- 茶室 / 中式
def kang_table(gb, w=1.5, d=0.85, h=0.34):
    gb.box((w, d, 0.06), (0, 0, h), mat="M_WoodDark")
    gb.box((w - 0.12, d - 0.12, 0.03), (0, 0, h + 0.035), mat="M_Wood")
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.box((0.07, 0.07, h), (sx * (w / 2 - 0.10), sy * (d / 2 - 0.10), h / 2),
                   mat="M_WoodDark")
    # 茶具
    gb.lathe([(0.05, 0), (0.09, 0.03), (0.10, 0.09), (0.06, 0.12), (0.055, 0.14)],
             seg=16, center=(0.10, 0.02, h + 0.05), mat="M_Celadon")
    for i in range(3):
        gb.cyl(0.035, 0.05, (-0.36 + 0.14 * i, 0.16, h + 0.07), seg=14, mat="M_Celadon")
    gb.cyl(0.13, 0.02, (0.10, 0.02, h + 0.05), seg=20, mat="M_WoodDark")


def cushion(gb, r=0.24, h=0.14, mat="M_FabricRust"):
    gb.cyl(r, h, (0, 0, h / 2), seg=20, mat=mat, r_top=r * 0.94)


def screen(gb, w=1.9, h=1.9, panels=3, mat="M_WoodDark"):
    """屏风：3 折，带绢面"""
    pw = w / panels
    for i in range(panels):
        ang = D(-14 + i * 14)
        with gb.frame(Matrix.Translation((pw * (i - (panels - 1) / 2), 0, 0)) @
                      Matrix.Rotation(ang, 4, "Z")):
            gb.box((pw - 0.04, 0.035, h), (0, 0, h / 2), mat=mat)
            gb.box((pw - 0.12, 0.01, h - 0.16), (0, 0.025, h / 2), mat="M_Silk")
            for k in range(1, 4):
                gb.box((pw - 0.12, 0.02, 0.012), (0, 0.03, h * k / 4), mat=mat)


def vase_branch(gb, h=0.42, mat="M_Ceramic", leaf="M_LeafPale", seed=3):
    rng = random.Random(seed)
    gb.lathe([(0.07, 0), (0.11, 0.06), (0.13, h * 0.55), (0.09, h * 0.85), (0.10, h)],
             seg=20, center=(0, 0, 0), mat=mat)
    for k in range(4):
        a = rng.uniform(0, TAU)
        ln = rng.uniform(0.35, 0.62)
        base = Vector((0, 0, h))
        tip = base + Vector((math.cos(a) * ln * 0.5, math.sin(a) * ln * 0.5, ln))
        mid = (base + tip) / 2
        d = tip - base
        yaw = math.atan2(d.y, d.x)
        pitch = math.atan2(math.hypot(d.x, d.y), d.z)
        M = Matrix.Translation(mid) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "Y")
        with gb.frame(M):
            gb.cyl(0.008, d.length, (0, 0, 0), seg=6, mat="M_Bark")
        for m in range(4):
            t = 0.4 + 0.18 * m
            p = base + d * t
            gb.sphere(rng.uniform(0.05, 0.09), tuple(p), seg=8, rings=5, mat=leaf,
                      scale=(1.4, 1.4, 0.5))


def art_frame(gb, w=1.2, h=0.8, mat="M_WoodDark", art="M_Canvas"):
    # 四边框条，中间让出画心
    fw = 0.055
    gb.box((w, 0.05, fw), (0, 0, h / 2 - fw / 2), mat=mat)
    gb.box((w, 0.05, fw), (0, 0, -h / 2 + fw / 2), mat=mat)
    gb.box((fw, 0.05, h), (-w / 2 + fw / 2, 0, 0), mat=mat)
    gb.box((fw, 0.05, h), (w / 2 - fw / 2, 0, 0), mat=mat)
    gb.box((w - 2 * fw, 0.012, h - 2 * fw), (0, 0.018, 0), mat=art)
    gb.box((w - 0.30, 0.012, h * 0.10), (0, 0.045, -h * 0.22), mat="M_FabricInk")
    gb.box((w - 0.42, 0.012, h * 0.06), (0, 0.045, -h * 0.10), mat="M_FabricInk")


def curtain(gb, w=1.6, h=2.6, mat="M_Linen"):
    n = max(5, int(w / 0.16))
    for i in range(n):
        x = -w / 2 + w * (i + 0.5) / n
        gb.cyl(0.055, h, (x, 0, h / 2 + 0.05), seg=8, mat=mat, r_top=0.045)
        gb.box((0.01, 0.10, h * 0.9), (x, 0.0, h / 2), mat=mat)


def potted_plant(gb, r=0.24, h=0.42, leaf="M_LeafGreen", big=False):
    gb.lathe([(r * 0.8, 0), (r, 0.04), (r, h * 0.9), (r * 1.06, h)],
             seg=18, center=(0, 0, 0), mat="M_Ceramic")
    gb.cyl(r * 0.9, 0.03, (0, 0, h - 0.02), seg=18, mat="M_Soil")
    if big:
        gb.cyl(0.05, 0.75, (0, 0, h + 0.36), seg=8, mat="M_Bark")
        for k in range(9):
            a = TAU * k / 9
            rr = 0.28 + 0.12 * (k % 3)
            gb.sphere(0.22, (math.cos(a) * rr * 0.6, math.sin(a) * rr * 0.6, h + 0.55 + 0.14 * (k % 4)),
                      seg=10, rings=7, mat=leaf, scale=(1.5, 1.3, 0.6))
    else:
        for k in range(7):
            a = TAU * k / 7
            gb.cyl(0.008, 0.34, (0, 0, h + 0.17), seg=5, mat="M_Bark")
            gb.sphere(0.13, (math.cos(a) * 0.12, math.sin(a) * 0.12, h + 0.36),
                      seg=9, rings=6, mat=leaf, scale=(1.2, 1.2, 0.85))


# --------------------------------------------------------------- 户外
def outdoor_lounge(gb, w=1.9, d=0.82):
    gb.box((w, d, 0.09), (0, 0, 0.36), mat="M_Bamboo")
    gb.box((w, 0.10, 0.52), (0, -d / 2 + 0.05, 0.68), mat="M_Bamboo")
    rbox(gb, (w - 0.12, d - 0.14, 0.13), (0, 0.06, 0.47), "M_FabricOat", r=0.04)
    gb.box((w - 0.10, 0.16, 0.22), (0, -d / 2 + 0.14, 0.66), mat="M_FabricOat")
    for s in (-1, 1):
        gb.box((0.10, d, 0.24), (s * (w / 2 - 0.05), 0, 0.55), mat="M_Bamboo")
        for sy in (-1, 1):
            gb.box((0.06, 0.06, 0.34), (s * (w / 2 - 0.10), sy * (d / 2 - 0.08), 0.17),
                   mat="M_Bamboo")


def outdoor_table(gb, r=0.42, h=0.40):
    gb.cyl(r, 0.05, (0, 0, h), seg=24, mat="M_Bamboo")
    gb.cyl(0.05, h, (0, 0, h / 2), seg=10, mat="M_MetalBlack")
    gb.cyl(r * 0.6, 0.03, (0, 0, 0.015), seg=20, mat="M_MetalBlack")


def bench(gb, w=1.6, d=0.42, mat="M_Bamboo"):
    gb.box((w, d, 0.06), (0, 0, 0.42), mat=mat)
    for s in (-1, 1):
        gb.box((0.08, d - 0.06, 0.42), (s * (w / 2 - 0.12), 0, 0.21), mat=mat)
    gb.box((w - 0.1, 0.04, 0.04), (0, 0, 0.20), mat=mat)


def stone_lantern(gb, h=1.55):
    gb.cyl(0.28, 0.14, (0, 0, 0.07), seg=6, mat="M_StoneDark")
    gb.cyl(0.10, h * 0.45, (0, 0, 0.14 + h * 0.225), seg=6, mat="M_StoneDark")
    gb.cyl(0.24, 0.07, (0, 0, h * 0.52), seg=6, mat="M_StoneDark")
    gb.box((0.34, 0.34, 0.30), (0, 0, h * 0.52 + 0.19), mat="M_StoneLight")
    gb.box((0.26, 0.26, 0.20), (0, 0, h * 0.52 + 0.19), mat="M_LampShade")
    gb.cyl(0.02, 0.22, (0, 0, h * 0.52 + 0.44), seg=6, mat="M_StoneDark")
    for i in range(6):
        a = TAU * i / 6
        gb.box((0.36, 0.03, 0.30), (0, 0, h * 0.52 + 0.19), mat="M_StoneLight")


def pergola(gb, w=5.0, d=3.2, h=2.6, post_mat="M_WoodDark"):
    for sx in (-1, 1):
        for sy in (-1, 1):
            gb.box((0.14, 0.14, h), (sx * (w / 2 - 0.10), sy * (d / 2 - 0.10), h / 2),
                   mat=post_mat)
    for sy in (-1, 1):
        gb.box((w, 0.12, 0.16), (0, sy * (d / 2 - 0.10), h + 0.08), mat=post_mat)
    n = int(w / 0.34)
    for i in range(n):
        x = -w / 2 + w * (i + 0.5) / n
        gb.box((0.06, d, 0.10), (x, 0, h + 0.20), mat=post_mat)


# --------------------------------------------------------------- 生活细节
def kitchenware(gb):
    """台面小物：砧板、锅、油盐瓶、挂具。"""
    gb.box((0.46, 0.30, 0.025), (0.0, 0.02, 0.90), mat="M_WoodLight")
    gb.box((0.40, 0.26, 0.028), (0.10, 0.06, 0.925), mat="M_WoodPale")
    gb.cyl(0.115, 0.10, (-0.34, 0.02, 0.945), seg=20, mat="M_MetalGrey", r_top=0.10)
    gb.cyl(0.10, 0.012, (-0.34, 0.02, 0.90), seg=18, mat="M_MetalBlack")
    gb.cyl(0.03, 0.02, (-0.34, 0.02, 1.00), seg=10, mat="M_MetalBlack")
    for i, (x, y, r, h) in enumerate(((-0.05, 0.20, 0.035, 0.20),
                                      (0.03, 0.22, 0.032, 0.24),
                                      (0.11, 0.20, 0.030, 0.17))):
        gb.cyl(r, h, (x, y, 0.90 + h / 2), seg=14,
               mat="M_Celadon" if i % 2 else "M_Porcelain")
        gb.cyl(r * 0.5, 0.02, (x, y, 0.90 + h + 0.01), seg=10, mat="M_MetalBlack")
    # 挂在墙上的铲勺
    for i in range(4):
        gb.cyl(0.012, 0.26, (0.28 + i * 0.07, 0.28, 1.42), seg=7, mat="M_MetalGrey")
        gb.box((0.05, 0.02, 0.06), (0.28 + i * 0.07, 0.28, 1.30), mat="M_MetalGrey")


def dish_rack(gb):
    gb.box((0.34, 0.24, 0.10), (0, 0, 0.05), mat="M_MetalGrey")
    for i in range(5):
        gb.cyl(0.075, 0.012, (-0.12 + i * 0.06, 0, 0.10), axis="Y", seg=16,
               mat="M_Porcelain")
    for i in range(3):
        gb.cyl(0.04, 0.06, (-0.08 + i * 0.08, 0.06, 0.13), seg=14, mat="M_Porcelain")


def towel_bar(gb, w=0.62, z=1.05, cloth="M_Linen"):
    gb.cyl(0.012, w, (0, 0, z), axis="X", seg=8, mat="M_Chrome")
    for s in (-1, 1):
        gb.cyl(0.012, 0.10, (s * w / 2, -0.05, z), axis="Y", seg=8, mat="M_Chrome")
    n = 5
    for i in range(n):
        x = -w / 2 + 0.06 + i * (w - 0.12) / (n - 1)
        gb.cyl(0.032, 0.44, (x, 0.02, z - 0.23), seg=7, mat=cloth, r_top=0.026)


def bath_mat(gb, w=0.7, d=0.45):
    gb.box((w, d, 0.014), (0, 0, 0.008), mat="M_FabricOat")
    for i in range(9):
        gb.box((w - 0.06, 0.012, 0.016), (0, -d / 2 + 0.05 + i * (d - 0.1) / 8, 0.009),
               mat="M_FabricGrey")


def trash_bin(gb, r=0.14, h=0.34):
    gb.cyl(r, h, (0, 0, h / 2), seg=18, mat="M_MetalGrey", r_top=r)
    gb.cyl(r * 0.92, 0.02, (0, 0, h - 0.01), seg=18, mat="M_MetalBlack")
    gb.cyl(r * 0.55, 0.02, (0, 0, h + 0.012), seg=14, mat="M_MetalBlack")


def laundry_basket(gb, r=0.22, h=0.42):
    gb.lathe([(r * 0.82, 0), (r, 0.05), (r, h * 0.92), (r * 0.96, h)],
             seg=20, center=(0, 0, 0), mat="M_Bamboo")
    for i in range(3):
        gb.cyl(r * 0.99, 0.014, (0, 0, h * (0.3 + 0.25 * i)), seg=20, mat="M_WoodDark")
    # 露出来的衣物
    gb.sphere(r * 0.62, (0, 0, h - 0.02), seg=10, rings=6, mat="M_Linen",
              scale=(1.1, 1.0, 0.5))


def wall_clock(gb, r=0.16):
    gb.cyl(r, 0.045, (0, 0, 0), axis="Y", seg=24, mat="M_WoodDark")
    gb.cyl(r * 0.92, 0.02, (0, 0.03, 0), axis="Y", seg=24, mat="M_Canvas")
    gb.box((0.012, 0.012, r * 0.62), (0, 0.05, r * 0.22), mat="M_MetalBlack")
    gb.box((r * 0.42, 0.012, 0.010), (r * 0.14, 0.05, 0), mat="M_MetalBlack")


def round_rug(gb, r=1.0, mat="M_Rug"):
    gb.cyl(r, 0.016, (0, 0, 0.008), seg=36, mat=mat)
    gb.cyl(r * 0.86, 0.004, (0, 0, 0.017), seg=36, mat="M_RugRed")


def books_row(gb, n=7, w=0.34, seed=1):
    rng = random.Random(seed)
    x = -w / 2
    while x < w / 2 - 0.04:
        bw = rng.uniform(0.03, 0.065)
        bh = rng.uniform(0.18, 0.26)
        gb.box((bw, 0.16, bh), (x + bw / 2, 0, bh / 2),
               mat=rng.choice(["M_BookSpine", "M_BookSpineB", "M_FabricInk",
                               "M_Lacquer"]))
        x += bw + 0.004


def fruit_bowl(gb, r=0.16):
    gb.lathe([(r * 0.5, 0), (r * 0.9, 0.03), (r, 0.09), (r * 0.96, 0.12)],
             seg=22, center=(0, 0, 0), mat="M_Celadon")
    rng = random.Random(3)
    for i in range(4):
        a = 2.399 * i
        gb.sphere(r * 0.32, (math.cos(a) * r * 0.34, math.sin(a) * r * 0.34, r * 0.20),
                  seg=10, rings=7, mat="M_LeafMaple" if i % 2 else "M_LeafOlive")


def tray_tea(gb):
    gb.box((0.46, 0.30, 0.02), (0, 0, 0.01), mat="M_WoodDark")
    for i in range(4):
        gb.cyl(0.032, 0.045, (-0.14 + i * 0.09, 0.04, 0.043), seg=14, mat="M_Celadon")
    gb.lathe([(0.05, 0), (0.085, 0.03), (0.09, 0.09), (0.055, 0.12)],
             seg=16, center=(0.10, -0.06, 0.02), mat="M_Celadon")


def coat_hooks(gb, n=4):
    gb.box((0.9, 0.04, 0.10), (0, 0, 1.62), mat="M_WoodDark")
    for i in range(n):
        gb.cyl(0.014, 0.09, (-0.36 + i * 0.24, -0.06, 1.58), axis="Y", seg=8,
               mat="M_Brass")


def slippers(gb):
    for s in (-1, 1):
        gb.box((0.10, 0.26, 0.03), (s * 0.06, 0, 0.015), mat="M_FabricCream")
        gb.box((0.095, 0.10, 0.02), (s * 0.06, -0.06, 0.045), mat="M_FabricOat")


def hanging_plant(gb, r=0.18, drop=0.55):
    gb.cyl(0.008, drop, (0, 0, -drop / 2), seg=5, mat="M_Bark")
    gb.lathe([(r * 0.6, 0), (r, 0.03), (r, 0.10), (r * 0.9, 0.14)],
             seg=16, center=(0, 0, -drop - 0.14), mat="M_Ceramic")
    for k in range(6):
        a = TAU * k / 6
        gb.sphere(0.07, (math.cos(a) * r * 0.7, math.sin(a) * r * 0.7, -drop + 0.02),
                  seg=8, rings=5, mat="M_LeafGreen", scale=(1.4, 1.4, 0.5))


def parasol(gb, r=1.55, h=2.35, panels=8, canopy="M_FabricCream"):
    """户外遮阳伞：石座 + 铝柱 + **连续伞面**（旋转体，不留缝）+ 伞骨在伞面下 + 顶饰。"""
    # 底座 / 立杆
    gb.box((0.62, 0.62, 0.10), (0, 0, 0.05), mat="M_StoneDark")
    gb.cyl(0.035, h, (0, 0, h / 2), seg=14, mat="M_MetalBlack")
    # 伞面：按半径分环的旋转体，面是平滑锥穹顶（24 扇 × 4 环，顶点共享）
    seg = 32
    rings = [(0.00, 0.30), (0.34, 0.215), (0.68, 0.085), (1.00, -0.045)]  # (r比例, z偏移)
    vs, fs = [], []
    for (rr, dz) in rings:
        if rr == 0.0:
            vs.append((0.0, 0.0, h + dz))
            continue
        for i in range(seg):
            a_ = TAU * i / seg
            vs.append((math.cos(a_) * r * rr, math.sin(a_) * r * rr, h + dz))
    # 顶环扇形
    for i in range(seg):
        fs.append([0, 1 + i, 1 + (i + 1) % seg])
    # 其余环带
    for k in range(1, len(rings) - 1):
        b0 = 1 + (k - 1) * seg
        b1 = 1 + k * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append([b0 + i, b1 + i, b1 + i2, b0 + i2])
    gb._add_faces(vs, fs, canopy)
    # 底面（背面材质），稍微内收，避免单面
    vs2 = [(x, y, z - 0.012) for (x, y, z) in vs]
    gb._add_faces(vs2, fs, "M_FabricOat")
    # 伞裙：最后一圈往下垂一小段，均匀（不做锯齿）
    skirt = []
    for i in range(seg):
        a_ = TAU * i / seg
        skirt.append((math.cos(a_) * r * 0.995, math.sin(a_) * r * 0.995, h - 0.045))
    vs3 = vs[-seg:] + skirt
    fs3 = []
    for i in range(seg):
        i2 = (i + 1) % seg
        fs3.append([i, seg + i, seg + i2, i2])
    gb._add_faces([(x, y, z + 0.001) for (x, y, z) in vs3], fs3, "M_FabricOat")
    # 伞骨：从中心下方放射到每片中间（在伞面之下，不外露）
    for i in range(panels):
        a_ = TAU * (i + 0.5) / panels
        p_in = Vector((math.cos(a_) * 0.09, math.sin(a_) * 0.09, h + 0.18))
        p_out = Vector((math.cos(a_) * r * 0.86, math.sin(a_) * r * 0.86, h - 0.105))
        d = p_out - p_in
        mid = (p_in + p_out) / 2
        M = (Matrix.Translation(mid) @
             Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z") @
             Matrix.Rotation(math.atan2(math.hypot(d.x, d.y), d.z), 4, "Y"))
        with gb.frame(M):
            gb.box((0.020, 0.020, d.length), (0, 0, 0), mat="M_MetalGrey")
    # 顶端连接座 + 顶饰
    gb.cyl(0.055, 0.05, (0, 0, h + 0.30), seg=14, mat="M_MetalBlack")
    gb.cyl(0.030, 0.16, (0, 0, h + 0.38), seg=10, mat="M_Brass")
    gb.sphere(0.045, (0, 0, h + 0.48), seg=12, rings=7, mat="M_Brass")


def deck_chair(gb, w=0.56, d=0.58, mat="M_Bamboo", seat="M_FabricOat"):
    """户外扶手椅（不是躺椅）：可对坐的那种。"""
    h = 0.42
    gb.box((w, d, 0.06), (0, 0, h), mat=mat)
    gb.box((w - 0.06, d - 0.10, 0.07), (0, 0.02, h + 0.06), mat=seat)
    # 靠背略后倾
    with gb.frame(Matrix.Translation((0, -d / 2 + 0.04, h + 0.34)) @
                  Matrix.Rotation(D(9), 4, "X")):
        gb.box((w - 0.04, 0.05, 0.52), (0, 0, 0), mat=mat)
        gb.box((w - 0.12, 0.05, 0.40), (0, 0.03, -0.02), mat=seat)
    for sx in (-1, 1):
        gb.box((0.06, d, 0.06), (sx * (w / 2 - 0.03), 0, h + 0.20), mat=mat)
        for sy in (-1, 1):
            gb.box((0.045, 0.045, h), (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), h / 2),
                   mat=mat)


def cafe_table(gb, r=0.42, h=0.44, mat="M_WoodDark", hole=0.045):
    """伞下圆桌：薄台面 + 裙边 + 中心开孔（伞杆穿过），单柱 + 底盘。"""
    # 台面：环形（中空让伞杆穿过）
    seg = 32
    inner = max(hole, 0.03)
    top_out, top_in = [], []
    bot_out, bot_in = [], []
    for i in range(seg):
        a_ = TAU * i / seg
        cx, cy = math.cos(a_), math.sin(a_)
        top_out.append((cx * r, cy * r, h))
        top_in.append((cx * inner, cy * inner, h))
        bot_out.append((cx * r, cy * r, h - 0.035))
        bot_in.append((cx * inner, cy * inner, h - 0.035))
    fs = []
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append([i, seg + i, seg + i2, i2])                      # 台面
        fs.append([2*seg + i2, 2*seg + i, 3*seg + i, 3*seg + i2])   # 底面
        fs.append([i, i2, 3*seg + i2, 3*seg + i])                   # 外圈
        fs.append([seg + i2, seg + i, 2*seg + i, 2*seg + i2])       # 内圈（孔壁）
    gb._add_faces(top_out + top_in + bot_out + bot_in, fs, mat)
    # 台面下裙边（浅一圈）
    gb.cyl(r * 0.90, 0.03, (0, 0, h - 0.05), seg=seg, mat=mat)
    # 立柱 + 底盘
    gb.cyl(0.042, h - 0.09, (0, 0, (h - 0.09) / 2), seg=14, mat="M_MetalBlack")
    gb.cyl(0.26, 0.03, (0, 0, 0.015), seg=24, mat="M_MetalBlack")

def pot(gb, r=0.26, h=0.42, mat="M_Ceramic"):
    """空花盆（陶盆 + 土），上面摆成品植物模型用。"""
    gb.lathe([(r * 0.78, 0), (r, 0.035), (r * 1.02, h * 0.82), (r * 1.06, h)],
             seg=22, center=(0, 0, 0), mat=mat)
    gb.lathe([(r * 0.98, h - 0.02), (r * 0.9, h + 0.005)], seg=22, center=(0, 0, 0),
             mat="M_Soil")
    gb.cyl(r * 0.94, 0.02, (0, 0, h + 0.012), seg=20, mat="M_Soil")


def patio(gb, x0, x1, y0, y1, top=0.03, mat="M_StoneLight", border="M_StoneDark"):
    """方形铺装小平台（草坪上放休闲家具用）。"""
    gb.boxb(((x0, x1), (y0, y1), (top - 0.05, top)), mat=border)
    gb.boxb(((x0 + 0.12, x1 - 0.12), (y0 + 0.12, y1 - 0.12), (top, top + 0.012)),
            mat=mat)
