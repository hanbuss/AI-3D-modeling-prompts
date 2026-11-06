# -*- coding: utf-8 -*-
"""院墙与大门（新中式 · 高档）。

设计逻辑
--------
- 院墙三段式：深灰石勒脚 0.45 + 米白墙身 + 深灰石压顶 + 筒瓦小披檐（出挑 0.20）
- 每 ~4 m 一道石壁柱（0.46 见方、高出墙 0.17、柱帽 + 瓦顶），把长墙切成节奏
- 隔段一块深木格栅饰板（石框 + 竖条），近看不空、远看不腻
- 主入口：门楼式——0.6 方石柱 + 深木横梁 + 瓦檐 + 双开"板门 + 竖格栅" + 抱鼓石 + 门匾 + 三级踏步
- 门内一道影壁（照壁），挡住直视客厅的视线
- 东侧车行门：石柱 + 深灰金属推拉门（半开）
"""
import math

from mathutils import Matrix

TAU = math.pi * 2
WALL_H = 2.55
WALL_T = 0.36


def _slab(gb, size, center, mat, axis="X", deg=0.0):
    """绕 X 或 Y 轴倾斜的板（用 Matrix 旋转，kit.box 支持 rot）。"""
    rot = Matrix.Rotation(math.radians(deg), 4, axis)
    gb.box(size, center, rot=rot, mat=mat)


def _seg_boxes(axis, c, a0, a1):
    """把 (a0,a1) 段换算成 boxb 需要的包围盒。"""
    if axis == "X":
        return ((a0, a1), (c - WALL_T / 2, c + WALL_T / 2))
    return ((c - WALL_T / 2, c + WALL_T / 2), (a0, a1))


def wall_run(gb, axis, c, a0, a1, h=WALL_H, pilaster=4.2, panels=True,
             outer_sign=0):
    """一段院墙：勒脚 + 墙身 + 压顶 + 瓦檐 + 壁柱 + 木饰板。"""
    if a1 - a0 < 0.4:
        return
    plinth = 0.45
    # ---- 勒脚 / 墙身 / 压顶 ----
    (xr, yr) = _seg_boxes(axis, c, a0, a1)
    gb.boxb((xr, yr, (0.0, plinth)), mat="M_StoneDark")
    gb.boxb(((xr[0] - 0.015, xr[1] + 0.015), (yr[0] - 0.015, yr[1] + 0.015),
             (plinth, h)), mat="M_WallWhite")
    gb.boxb(((xr[0] - 0.05, xr[1] + 0.05), (yr[0] - 0.05, yr[1] + 0.05),
             (h, h + 0.14)), mat="M_StoneDark")
    # 腰线：把墙身分成上下两段（中式院墙常见做法，也压住"一片白"）
    if axis == "X":
        gb.box((xr[1] - xr[0], WALL_T + 0.045, 0.035), ((xr[0] + xr[1]) / 2, c, 1.06),
               mat="M_Stone")
    else:
        gb.box((WALL_T + 0.045, yr[1] - yr[0], 0.035), (c, (yr[0] + yr[1]) / 2, 1.06),
               mat="M_Stone")
    # ---- 瓦檐（双坡）----
    if axis == "X":
        L, m, cy = a1 - a0, (a0 + a1) / 2, c
        half = WALL_T / 2 + 0.20
        for sgn in (-1, 1):
            _slab(gb, (L, half * 1.08, 0.05),
                  (m, cy + sgn * half * 0.52, h + 0.14 + 0.075), "M_Tile",
                  axis="X", deg=sgn * 17.0)
            gb.box((L, 0.05, 0.07), (m, cy + sgn * (half + 0.01), h + 0.13),
                   mat="M_TileEdge")
        gb.box((L, 0.10, 0.05), (m, cy, h + 0.29), mat="M_TileEdge")
    else:
        L, m, cx = a1 - a0, (a0 + a1) / 2, c
        half = WALL_T / 2 + 0.20
        for sgn in (-1, 1):
            _slab(gb, (half * 1.08, L, 0.05),
                  (cx + sgn * half * 0.52, m, h + 0.14 + 0.075), "M_Tile",
                  axis="Y", deg=-sgn * 17.0)
            gb.box((0.05, L, 0.07), (cx + sgn * (half + 0.01), m, h + 0.13),
                   mat="M_TileEdge")
        gb.box((0.10, L, 0.05), (cx, m, h + 0.29), mat="M_TileEdge")
    # ---- 壁柱 ----
    n = max(1, int(round((a1 - a0) / pilaster)))
    for i in range(n + 1):
        u = a0 + (a1 - a0) * i / n
        u = min(max(u, a0 + 0.25), a1 - 0.25)
        px, py = (u, c) if axis == "X" else (c, u)
        gb.box((0.46, 0.46, h + 0.17), (px, py, (h + 0.17) / 2), mat="M_Stone")
        gb.box((0.56, 0.56, 0.08), (px, py, h + 0.21), mat="M_StoneDark")
        gb.box((0.44, 0.44, 0.10), (px, py, h + 0.30), mat="M_Tile")
    # ---- 木格栅饰板（只做朝外/朝院一面）----
    if panels and outer_sign != 0 and (a1 - a0) > 3.0:
        s = c + outer_sign * (WALL_T / 2 + 0.02)
        for i in range(n):
            u0 = a0 + (a1 - a0) * i / n + 0.62
            u1 = a0 + (a1 - a0) * (i + 1) / n - 0.62
            if u1 - u0 < 1.0:
                continue
            if i % 2:
                continue
            _panel(gb, axis, s, min(u0, u1 - 2.0), u1, 1.30, 2.02)


def _panel(gb, axis, s, u0, u1, z0, z1):
    """石框 + 深木竖条。"""
    cu, cz = (u0 + u1) / 2, (z0 + z1) / 2
    du, dz = u1 - u0, z1 - z0
    frames = ((u0, u1, z0 - 0.08, z0), (u0, u1, z1, z1 + 0.08),
              (u0 - 0.08, u0, z0, z1), (u1, u1 + 0.08, z0, z1))
    for (a, b, c0, c1) in frames:
        if axis == "X":
            gb.box((b - a, 0.05, c1 - c0), ((a + b) / 2, s, (c0 + c1) / 2), mat="M_Stone")
        else:
            gb.box((0.05, b - a, c1 - c0), (s, (a + b) / 2, (c0 + c1) / 2), mat="M_Stone")
    k = max(3, int(du / 0.26))
    for i in range(k):
        u = u0 + du * (i + 0.5) / k
        if axis == "X":
            gb.box((0.055, 0.045, dz), (u, s, cz), mat="M_WoodDark")
        else:
            gb.box((0.045, 0.055, dz), (s, u, cz), mat="M_WoodDark")


def main_gate(gb, cx, y, w=2.60, side=-1):
    """门楼式主入口。side=-1 表示院内朝 -y（南门），踏步朝 +y 外侧。"""
    pw, ph = 0.60, 3.10
    for sgn in (-1, 1):
        x = cx + sgn * (w / 2 + pw / 2)
        gb.box((pw, pw, ph), (x, y, ph / 2), mat="M_Stone")
        gb.box((pw + 0.14, pw + 0.14, 0.09), (x, y, ph + 0.045), mat="M_StoneDark")
        gb.box((pw + 0.52, pw + 0.52, 0.06), (x, y, ph + 0.12), mat="M_TileEdge")
        gb.box((pw + 0.34, pw + 0.34, 0.11), (x, y, ph + 0.20), mat="M_Tile")
        gb.box((pw + 0.16, pw + 0.16, 0.07), (x, y, ph + 0.29), mat="M_TileEdge")
        # 抱鼓石（院内一侧）
        gb.box((0.50, 0.86, 0.28), (x, y - side * 0.66, 0.14), mat="M_StoneDark")
        gb.cyl(0.20, 0.22, (x, y - side * 0.66, 0.40), axis="X", seg=20,
               mat="M_StoneLight")
    # 横梁 + 梁上瓦檐
    gb.box((w + 0.16, 0.32, 0.34), (cx, y, ph - 0.19), mat="M_WoodDark")
    for i in range(9):
        u = cx - w / 2 + w * (i + 0.5) / 9
        gb.box((0.045, 0.34, 0.30), (u, y, ph - 0.19), mat="M_WoodPale")
    gb.box((w + 0.30, 0.30, 0.20), (cx, y, ph - 0.02), mat="M_StoneDark")
    for sgn in (1, -1):
        _slab(gb, (w + 0.74, 0.52, 0.05), (cx, y + sgn * 0.26, ph + 0.19), "M_Tile",
              axis="X", deg=sgn * 18.0)
    gb.box((w + 0.80, 0.07, 0.07), (cx, y, ph + 0.32), mat="M_TileEdge")
    # 门匾
    gb.box((1.30, 0.05, 0.40), (cx, y - side * 0.18, ph - 0.24), mat="M_StoneLight")
    gb.box((1.18, 0.02, 0.28), (cx, y - side * 0.205, ph - 0.24), mat="M_WoodDark")
    # 双开门扇
    lw, lh = (w - 0.10) / 2, 2.26
    yy = y + side * 0.06
    for sgn in (-1, 1):
        hinge = cx + sgn * (w / 2 - 0.05)
        # 框
        gb.box((0.06, 0.07, lh), (hinge, yy, lh / 2), mat="M_WoodDark")
        gb.box((lw, 0.07, 0.07), (hinge - sgn * lw / 2, yy, lh), mat="M_WoodDark")
        # 下段实心板（0.02~1.38）
        gb.box((lw - 0.04, 0.055, 1.36), (hinge - sgn * lw / 2, yy, 0.70),
               mat="M_WoodDark")
        # 中横档
        gb.box((lw, 0.075, 0.10), (hinge - sgn * lw / 2, yy, 1.42), mat="M_WoodDark")
        # 上段竖格栅（1.47~lh，约 0.8 m 高）
        bars = 6
        gh = lh - 1.47
        for i in range(bars):
            u = hinge - sgn * lw * (i + 0.5) / bars
            gb.box((0.045, 0.05, gh), (u, yy, 1.47 + gh / 2), mat="M_WoodDark")
        gb.box((0.030, 0.05, gh), (hinge - sgn * lw * 0.5, yy, 1.47 + gh / 2),
               mat="M_Brass")
    # 门槛 + 三级踏步（院内朝外）
    gb.box((w + 0.24, 0.40, 0.12), (cx, y, 0.06), mat="M_StoneLight")
    for i in range(3):
        gb.box((w + 1.00, 0.34, 0.09),
               (cx, y - side * (0.42 + i * 0.34), 0.045), mat="M_StoneLight")
    for sgn in (-1, 1):
        gb.box((0.22, 1.30, 0.30),
               (cx + sgn * (w / 2 + 0.62), y - side * 0.75, 0.15), mat="M_StoneDark")


def screen_wall(gb, cx, y, w=2.70, h=2.35, t=0.36):
    """影壁（照壁）：两级石台 + 白墙 + 圆形砖雕 + 八字翼墙 + 起翘瓦顶。

    形制要点：独立照壁必须有"台基—墙身—瓦顶"三段，两侧翼墙收边，
    否则在草坪上就是一块白板（这正是上一版的毛病）。
    """
    base_w, base_h = w + 0.70, 0.13
    # 台基（两级）
    gb.box((base_w, t + 0.66, base_h), (cx, y, base_h / 2), mat="M_StoneDark")
    gb.box((base_w - 0.24, t + 0.42, 0.10), (cx, y, base_h + 0.05), mat="M_Stone")
    z0 = base_h + 0.10
    # 墙身
    gb.box((w, t, h - z0), (cx, y, z0 + (h - z0) / 2), mat="M_WallWhite")
    # 正反两面的石框 + 圆形砖雕
    for sgn in (-1, 1):
        yy = y + sgn * (t / 2 + 0.012)
        # 外框
        for (dz0, dz1) in ((z0 + 0.30, z0 + 0.40), (h - 0.36, h - 0.26)):
            gb.box((w - 0.34, 0.028, dz1 - dz0), (cx, yy, (dz0 + dz1) / 2), mat="M_Stone")
        for (dx) in (-(w / 2 - 0.20), (w / 2 - 0.20)):
            gb.box((0.028, 0.028, h - z0 - 0.66), (cx + dx, yy, (z0 + h) / 2), mat="M_Stone")
        # 圆形砖雕：环形石圈 + 内凹浅板
        cz = (z0 + h) / 2 + 0.02
        R, seg = 0.62, 48
        ring_out, ring_in = [], []
        for i in range(seg):
            a_ = TAU * i / seg
            ring_out.append((cx + math.cos(a_) * R, yy, cz + math.sin(a_) * R))
            ring_in.append((cx + math.cos(a_) * (R - 0.075), yy, cz + math.sin(a_) * (R - 0.075)))
        vs = ring_out + ring_in
        fs = [[i, (i + 1) % seg, seg + (i + 1) % seg, seg + i] for i in range(seg)]
        gb._add_faces(vs, fs, "M_Stone")
        disc = [(cx + math.cos(TAU * i / seg) * (R - 0.08), yy - sgn * 0.012,
                 cz + math.sin(TAU * i / seg) * (R - 0.08)) for i in range(seg)]
        gb._add_faces([(cx, yy - sgn * 0.012, cz)] + disc,
                      [[0, 1 + i, 1 + (i + 1) % seg] for i in range(seg)], "M_WallWarm")
    # 八字翼墙（两侧各 1.0，高 1.40，与大墙成 90°）
    wing_w, wing_h = 1.05, 1.42
    for sgn in (-1, 1):
        xw = cx + sgn * (w / 2 + 0.02)
        gb.box((t, wing_w, wing_h), (xw, y + wing_w / 2 + 0.02, wing_h / 2), mat="M_WallWhite")
        gb.box((t + 0.14, wing_w + 0.14, 0.11), (xw, y + wing_w / 2 + 0.02, wing_h + 0.055),
               mat="M_StoneDark")
        _slab(gb, (t + 0.34, wing_w + 0.34, 0.045),
              (xw, y + wing_w / 2 + 0.02, wing_h + 0.14), "M_Tile", axis="Y", deg=15.0)
        gb.box((t + 0.30, 0.05, 0.07), (xw, y + wing_w + 0.14, wing_h + 0.12),
               mat="M_TileEdge")
    # 瓦顶：双坡 + 两端起翘
    gb.box((w + 0.34, t + 0.30, 0.11), (cx, y, h + 0.055), mat="M_StoneDark")
    for sgn in (-1, 1):
        _slab(gb, (w + 0.56, t * 0.64, 0.05), (cx, y + sgn * t * 0.34, h + 0.24),
              "M_Tile", axis="X", deg=sgn * 18.0)
    gb.box((w + 0.62, 0.07, 0.09), (cx, y, h + 0.35), mat="M_TileEdge")
    for sgn in (-1, 1):
        gb.box((0.26, t + 0.34, 0.10), (cx + sgn * (w / 2 + 0.16), y, h + 0.30),
               mat="M_Tile")
        gb.box((0.20, t + 0.30, 0.07), (cx + sgn * (w / 2 + 0.20), y, h + 0.40),
               mat="M_TileEdge")


def forecourt(gb, cx, y0, y1, w=3.10):
    """门内前庭铺装：石铺地 + 两道分格 + 两侧白砂带。"""
    L = y1 - y0
    gb.box((w, L, 0.06), (cx, (y0 + y1) / 2, 0.05), mat="M_StoneLight")
    n = max(2, int(L / 0.60))
    for i in range(n + 1):
        yy = y0 + L * i / n
        gb.box((w, 0.05, 0.012), (cx, yy, 0.085), mat="M_StoneDark")
    for sgn in (-1, 1):
        gb.box((0.26, L, 0.05), (cx + sgn * (w / 2 + 0.15), (y0 + y1) / 2, 0.045),
               mat="M_Gravel")
        gb.box((0.05, L, 0.10), (cx + sgn * (w / 2 + 0.01), (y0 + y1) / 2, 0.09),
               mat="M_StoneDark")


def car_gate(gb, cx, y, w=5.20, open_=0.55):
    """车行门：两根石柱 + 深灰金属竖条推拉门（按 open_ 半开）。"""
    pw = 0.58
    for sgn in (-1, 1):
        x = cx + sgn * (w / 2 + pw / 2)
        gb.box((pw, pw, 2.86), (x, y, 1.43), mat="M_Stone")
        gb.box((pw + 0.14, pw + 0.14, 0.09), (x, y, 2.90), mat="M_StoneDark")
        gb.box((pw + 0.34, pw + 0.34, 0.08), (x, y, 2.99), mat="M_Tile")
    panel_w = w * (1 - open_)
    x0 = cx - w / 2
    gb.box((panel_w, 0.07, 0.10), (x0 + panel_w / 2, y, 1.98), mat="M_MetalBlack")
    gb.box((panel_w, 0.07, 0.10), (x0 + panel_w / 2, y, 0.10), mat="M_MetalBlack")
    n = max(8, int(panel_w / 0.20))
    for i in range(n):
        u = x0 + panel_w * (i + 0.5) / n
        gb.box((0.030, 0.075, 1.86), (u, y, 1.04), mat="M_MetalGrey")
