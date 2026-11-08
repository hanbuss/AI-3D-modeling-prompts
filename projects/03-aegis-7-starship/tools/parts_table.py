"""tools/parts_table.py — 把 out/manifest.json 转成可读的零件表（交付文档用）

用法：python tools/parts_table.py [manifest.json] [输出.md]
"""
import json, os, sys
from collections import OrderedDict

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P, "out", "manifest.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P, "out", "parts_table.md")

GROUP_ZH = {
    "weapons": "武器系统", "gear": "起落装置", "canopy": "座舱", "engines": "动力系统",
    "wings": "机翼", "hull_fore": "前段船体", "hull_mid": "中段船体",
    "hull_aft": "尾段船体", "detail": "细节件",
}


def main():
    raw = json.load(open(SRC, encoding="utf-8"))
    parts = raw["parts"] if isinstance(raw, dict) else raw
    groups = OrderedDict()
    for p in parts:
        groups.setdefault(p.get("group", "?"), []).append(p)

    lines = ["# 零件清单 · AEGIS-7 «Kestrel»", ""]
    lines.append("共 **%d** 件可拆零件 / **%d** 个分组 / **%d** 三角面。"
                 % (len(parts), len(groups), sum(p["tris"] for p in parts)))
    lines.append("")
    lines.append("| 组 | 件数 | 三角面 | 拆解序号 |")
    lines.append("|---|---:|---:|---|")
    for g, ps in groups.items():
        orders = [p["order"] for p in ps]
        lines.append("| %s `%s` | %d | %d | %d–%d |"
                     % (GROUP_ZH.get(g, g), g, len(ps), sum(p["tris"] for p in ps),
                        min(orders), max(orders)))
    lines.append("")
    for g, ps in groups.items():
        lines.append("## %s（%s）" % (GROUP_ZH.get(g, g), g))
        lines.append("")
        lines.append("| # | 零件 ID | 中文名 | English | 三角面 | 爆炸位移 (m) | 说明 |")
        lines.append("|---:|---|---|---|---:|---|---|")
        for p in sorted(ps, key=lambda x: x["order"]):
            e = p["explode"]
            lines.append("| %d | `%s` | %s | %s | %d | (%.2f, %.2f, %.2f) | %s |"
                         % (p["order"], p["id"], p.get("zh", ""), p.get("en", ""),
                            p["tris"], e[0], e[1], e[2], p.get("note", "")))
        lines.append("")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print("wrote %s  parts=%d groups=%d" % (OUT, len(parts), len(groups)))


if __name__ == "__main__":
    main()
