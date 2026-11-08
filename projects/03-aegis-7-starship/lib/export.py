"""mk18/lib/export.py — GLB 导出 + 零件清单（part manifest）
每个零件对象带自定义属性：part_id / label_zh / label_en / group / order / explode / note
Blender glTF 导出器把它们写进 extras，Three.js 里可从 userData 读到。
"""
import bpy, json, os, struct


def objects_manifest():
    parts = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or 'part_id' not in o:
            continue
        parts.append({
            "id": o["part_id"],
            "name": o.name,
            "zh": o.get("label_zh", ""),
            "en": o.get("label_en", ""),
            "group": o.get("group", ""),
            "order": int(o.get("order", 0)),
            "explode": [round(float(v), 4) for v in o.get("explode", (0, 0, 0))],
            "note": o.get("note", ""),
            "center": [round(v, 5) for v in o.location],
            "tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
        })
    parts.sort(key=lambda p: p["order"])
    return parts


def export_glb(path, merge=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    kw = dict(
        filepath=path,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_extras=True,
        export_yup=True,
        export_texture_dir='',
        export_image_format='AUTO',
        export_cameras=False,
        export_lights=False,
    )
    try:
        kw["export_materials"] = 'EXPORT'
        bpy.ops.export_scene.gltf(**kw)
    except TypeError as e:
        print("export kwargs fallback:", e)
        for k in ("export_texture_dir", "export_image_format", "export_materials"):
            kw.pop(k, None)
        bpy.ops.export_scene.gltf(**kw)
    return path


def glb_stats(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, ver, total = struct.unpack('<III', data[:12])
    off = 12
    js = None
    while off < len(data):
        clen, ctype = struct.unpack('<II', data[off:off + 8])
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
        off += 8 + clen
    meshes = len(js.get('meshes', []))
    mats = len(js.get('materials', []))
    imgs = len(js.get('images', []))
    nodes = len(js.get('nodes', []))
    tris = 0
    for m in js.get('meshes', []):
        for p in m.get('primitives', []):
            if 'indices' in p:
                tris += js['accessors'][p['indices']]['count'] // 3
    return dict(bytes=len(data), meshes=meshes, nodes=nodes, materials=mats,
                images=imgs, tris=tris, extras=sum(1 for n in js.get('nodes', []) if 'extras' in n))


def write_manifest(path, parts):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"unit": "m", "axis": "X=barrel", "parts": parts}, f, ensure_ascii=False, indent=1)
    return path
