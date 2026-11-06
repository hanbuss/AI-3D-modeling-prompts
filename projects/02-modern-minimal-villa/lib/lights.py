"""灯光：室内灯 + 园林灯 + 水景灯。

只做真实光源（Point / Spot / Area）。渲染模式（日 / 黄昏 / 夜）由
render_shots.py 统一改 energy，所以这里只定位置、色温、朝向与量级。

命名前缀约定（render_shots 按前缀调光）：
    Lamp_*   室内灯
    Garden_* 园林灯
    Water_*  水景灯
"""
import math
import bpy
from mathutils import Vector

WARM = (1.0, 0.845, 0.660)
WARM_SOFT = (1.0, 0.885, 0.740)
COOL = (1.0, 0.945, 0.885)

# (名字, (x,y,z), 类型, 能量, 色, 尺寸/角度, 朝向点或 None)
INTERIOR = [
    # ---- 1F（层高 3.15，吊顶 3.30）----
    ("Lamp_Foyer",       (0.0, 1.30, 2.95), "POINT", 55, WARM, 0.9, None),
    ("Lamp_Living_A",    (-5.40, 0.20, 3.00), "POINT", 90, WARM_SOFT, 1.4, None),
    ("Lamp_Living_B",    (-3.30, 4.60, 3.00), "POINT", 80, WARM_SOFT, 1.4, None),
    ("Lamp_Dining",      (4.35, 1.10, 2.75), "AREA", 130, WARM, 1.1, None),
    ("Lamp_Kitchen",     (4.40, 5.70, 3.00), "POINT", 85, WARM, 1.2, None),
    ("Lamp_KitchenIsland", (4.40, 3.05, 2.60), "POINT", 45, WARM, 0.8, None),
    ("Lamp_Service",     (-4.30, 7.70, 3.00), "POINT", 45, WARM, 1.0, None),
    ("Lamp_WC_1F",       (5.80, 8.20, 3.00), "POINT", 25, WARM, 0.6, None),
    # ---- 2F（层高 3.00，吊顶 6.60）----
    ("Lamp_Master_A",    (-5.10, 1.10, 6.30), "POINT", 80, WARM_SOFT, 1.3, None),
    ("Lamp_Master_B",    (-3.10, 4.20, 6.30), "POINT", 55, WARM_SOFT, 1.1, None),
    ("Lamp_MBath",       (-5.90, 7.20, 6.28), "POINT", 60, COOL, 1.0, None),
    ("Lamp_WalkIn",      (-3.10, 7.20, 6.28), "POINT", 45, WARM, 0.9, None),
    ("Lamp_Landing_2F",  (0.0, 1.30, 6.30), "POINT", 60, WARM_SOFT, 1.2, None),
    ("Lamp_Bed2",        (4.30, 1.20, 6.30), "POINT", 70, WARM_SOFT, 1.2, None),
    ("Lamp_Bath2",       (2.95, 5.30, 6.28), "POINT", 40, COOL, 0.8, None),
    ("Lamp_Laundry",     (5.80, 5.30, 6.28), "POINT", 40, WARM, 0.8, None),
    ("Lamp_Nook",        (4.30, 7.90, 6.30), "POINT", 45, WARM, 0.9, None),
    # ---- 3F（层高 3.00，吊顶 9.90）----
    ("Lamp_Study_A",     (-5.10, 1.20, 9.60), "POINT", 75, WARM_SOFT, 1.3, None),
    ("Lamp_Study_B",     (-3.00, 3.60, 9.60), "POINT", 55, WARM_SOFT, 1.1, None),
    ("Lamp_Guest",       (-4.30, 6.70, 9.60), "POINT", 60, WARM_SOFT, 1.2, None),
    ("Lamp_Landing_3F",  (0.0, 1.30, 9.60), "POINT", 55, WARM_SOFT, 1.1, None),
    ("Lamp_Tea",         (2.60, 1.70, 9.55), "POINT", 40, WARM, 0.9, None),
    ("Lamp_Bath3",       (2.60, 7.00, 9.58), "POINT", 35, COOL, 0.8, None),
    ("Lamp_Terrace",     (5.40, 3.40, 8.60), "POINT", 50, WARM, 1.0, None),
]

# 园林灯：位置在院子上方 0.6~1.0 m，模拟地埋灯/矮柱灯的散射
GARDEN = [
    ("Garden_Deck_A",    (-7.20, -4.00, 0.55), 55, WARM),
    ("Garden_Deck_B",    (-3.20, -7.60, 0.55), 50, WARM),
    ("Garden_Deck_C",    (-6.80, -8.20, 0.55), 45, WARM),
    ("Garden_Pergola_A", (4.30, -5.20, 2.35), 60, WARM),
    ("Garden_Pergola_B", (6.90, -7.20, 2.35), 55, WARM),
    ("Garden_Zen_A",     (2.10, -10.60, 0.45), 40, WARM_SOFT),
    ("Garden_Zen_B",     (5.60, -11.80, 0.45), 35, WARM_SOFT),
    ("Garden_Lawn_A",    (-5.40, -11.40, 0.50), 45, WARM_SOFT),
    ("Garden_Lawn_B",    (-7.80, -12.60, 0.50), 40, WARM_SOFT),
    ("Garden_Gate_A",    (-2.10, -13.30, 1.90), 40, WARM),
    ("Garden_Gate_B",    (2.10, -13.30, 1.90), 40, WARM),
    ("Garden_EastBed",   (7.60, -1.80, 0.55), 35, WARM_SOFT),
    ("Garden_EntryPath", (0.00, -9.00, 0.45), 30, WARM_SOFT),
]

# 水景灯：水幕墙
WATER = [
    ("Water_Wall_A", (8.05, -3.90, 0.60), 30, (0.52, 0.80, 1.0)),
    ("Water_Wall_B", (8.05, -2.90, 0.60), 30, (0.52, 0.80, 1.0)),
    ("Water_Wall_C", (8.05, -1.95, 0.60), 26, (0.52, 0.80, 1.0)),
]

# 树下射灯（聚光，向上打树冠）
UPLIGHTS = [
    ("Garden_Up_Maple1", (-6.60, -10.10, 0.06), (-6.60, -10.10, 4.6), 70),
    ("Garden_Up_Maple2", (-8.20, -12.30, 0.06), (-8.20, -12.30, 4.2), 60),
    ("Garden_Up_Pine",   (3.10, -11.10, 0.06), (3.10, -11.10, 3.6), 65),
    ("Garden_Up_Pergola", (7.90, -8.20, 0.06), (7.90, -8.20, 3.0), 45),
]


def _make(sc, name, loc, kind, energy, color, size=1.0, target=None, spot=None):
    ld = bpy.data.lights.new(name, type=kind)
    ld.color = color
    ld.energy = energy
    if kind == "AREA":
        ld.shape = "RECTANGLE"
        ld.size = size
        ld.size_y = size * 0.45
    elif kind == "SPOT":
        ld.spot_size = math.radians(spot or 42.0)
        ld.spot_blend = 0.55
        ld.shadow_soft_size = 0.06
    elif kind == "POINT":
        ld.shadow_soft_size = max(0.10, size * 0.35)
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = loc
    if target:
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def build(sc, ctx=None):
    """在场景里放灯。ctx 仅用于拿 collection 归属（可空）。"""
    n = 0
    for name, loc, kind, energy, color, size, _t in INTERIOR:
        _make(sc, name, loc, kind, energy, color, size)
        n += 1
    for name, loc, energy, color in GARDEN:
        _make(sc, name, loc, "POINT", energy, color, 0.7)
        n += 1
    for name, loc, energy, color in WATER:
        _make(sc, name, loc, "POINT", energy, color, 0.35)
        n += 1
    for name, loc, tgt, energy in UPLIGHTS:
        _make(sc, name, loc, "SPOT", energy, (1.0, 0.90, 0.72), target=tgt, spot=34)
        n += 1
    print(f"[lights] {n} lights")
    return n
