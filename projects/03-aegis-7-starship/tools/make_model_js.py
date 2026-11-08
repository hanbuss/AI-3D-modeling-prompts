"""starship/tools/make_model_js.py — 把 GLB + 元数据打包成网页可直接 <script> 加载的 JS（file:// 也能用）

用法:
    python tools/make_model_js.py out/starship.glb viewer/model.b64.js
    python tools/make_model_js.py out/starship.glb viewer/model.b64.js \
        --manifest out/manifest.json --meta out/ship_meta.json --data viewer/data.js

为什么不 fetch：页面必须能双击打开（file://），file:// 下 fetch/XHR 被浏览器拦，
所以模型只能以 <script> 内联进来（base64 比 JSON 数字数组小 ~40%）；
零件表与引擎元数据同理，一起内联成 data.js，避免运行时再去读 JSON。

产物:
    <out_js>    window.STARSHIP_GLB_B64 = "..."
    <data_js>   window.STARSHIP_DATA = { meta, parts, source }
"""

import base64
import json
import os
import sys

# Windows 控制台默认 GBK，打印船名（含 «») 会 UnicodeEncodeError 直接中断打包
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def argval(argv, flag, default=None):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def read_json(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def glb_node_extras(path):
    """从 GLB 里直接把 node.extras 读出来（不依赖 Blender / three.js）。"""
    if not os.path.isfile(path):
        return []
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) < 20 or raw[:4] != b"glTF":
        return []
    total = int.from_bytes(raw[8:12], "little")
    off, js = 12, None
    while off < total:
        clen = int.from_bytes(raw[off:off + 4], "little")
        ctype = raw[off + 4:off + 8]
        if ctype == b"JSON":
            js = json.loads(raw[off + 8:off + 8 + clen].decode("utf-8"))
        off += 8 + clen
    if not js:
        return []
    out = []
    for n in js.get("nodes", []):
        ex = n.get("extras") or {}
        if "part_id" in ex:
            out.append(ex)
    return out


def main():
    argv = sys.argv[1:]
    src = argv[0] if argv and not argv[0].startswith("--") else "out/starship.glb"
    dst = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else "viewer/model.b64.js"
    man_path = argval(argv, "--manifest", "out/manifest.json")
    meta_path = argval(argv, "--meta", "out/ship_meta.json")
    data_path = argval(argv, "--data", os.path.join(os.path.dirname(os.path.abspath(dst)), "data.js"))

    if not os.path.isfile(src):
        cand = []
        for d in ("out", "."):
            if os.path.isdir(d):
                cand += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".glb")]
        sys.stderr.write("找不到模型: %s\n可用 glb:\n  %s\n" % (src, "\n  ".join(cand) or "(无)"))
        return 1

    with open(src, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode()
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("/* auto-generated from %s (%d bytes) — do not edit */\n"
                % (os.path.basename(src), len(raw)))
        f.write('window.STARSHIP_GLB_B64 = "')
        f.write(b64)
        f.write('";\n')

    # ---- 元数据（manifest 优先，缺就用 GLB 里的 node.extras 兜底）----
    man = read_json(man_path)
    meta = read_json(meta_path) or {}
    if man and isinstance(man, dict) and "parts" in man:
        parts = man["parts"]
    else:
        parts = glb_node_extras(src)
        for p in parts:
            p.setdefault("zh", p.get("label_zh", ""))
            p.setdefault("en", p.get("label_en", ""))
            p.setdefault("tris", 0)
    payload = {
        "source": os.path.basename(src),
        "bytes": len(raw),
        "meta": meta,
        "parts": parts,
    }
    os.makedirs(os.path.dirname(os.path.abspath(data_path)), exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        f.write("/* auto-generated from %s / %s — do not edit */\n"
                % (os.path.basename(man_path), os.path.basename(meta_path)))
        f.write("window.STARSHIP_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    groups = {}
    for p in parts:
        groups[p.get("group", "?")] = groups.get(p.get("group", "?"), 0) + 1
    tris = sum(int(p.get("tris") or 0) for p in parts)
    print("wrote %s  glb=%.2f MB  js=%.2f MB"
          % (dst, len(raw) / 1048576.0, os.path.getsize(dst) / 1048576.0))
    print("wrote %s  parts=%d  tris=%d  groups=%s"
          % (data_path, len(parts), tris,
             ", ".join("%s:%d" % (k, v) for k, v in sorted(groups.items()))))
    eng = meta.get("engines") or []
    tur = meta.get("turret") or {}
    print("meta: ship=%s engines=%d turret=%s"
          % (meta.get("ship", "?"), len(eng), "yes" if tur else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
