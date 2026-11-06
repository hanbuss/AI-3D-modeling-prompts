# 云嵴山居 · 三层新中式别墅

程序化生成的 3D 别墅 + 可交互网页模型。设计说明见 **[设计说明.md](设计说明.md)**。

## 怎么打开

**① 交互 3D（推荐）**

```bash
cd <repo>/villa/viewer
python -m http.server 8899
```

浏览器打开 <http://127.0.0.1:8899/index.html>

能做的事：拖动旋转 / 滚轮缩放、按层查看（花园·一层·二层·三层·屋顶）、0–24 小时昼夜滑杆、水平剖切看内部、点击房间标签飞过去、鸟瞰/正立面/庭院/室内四个预设视角。

**② Blender 工程**

用 Blender 5.1 打开 `villa.blend`：`SITE / GARDEN / F1 / F2 / F3 / ROOF` 六个集合对应六个图层，右上角贴图按 N 键可开侧栏；机位 `CAM_Hero / CAM_Court / CAM_East / CAM_Living / CAM_Night / CAM_Axo`。

**③ 出图**

`previews/` 里已有：日景 4 张、夜景 3 张、分层平面 4 张（1600×900 / 1300×975）。

## 文件

| 文件 | 说明 |
|---|---|
| `villa.glb` | 网页模型（glTF2 binary，Y-up，米制，228 mesh / 57 材质 / 12 套程序化贴图 + 成品植被 / 约 55 MB） |
| `rooms.json` | 20 个房间的标注数据（中英名、楼层、坐标、面积） |
| `viewer/index.html` | 离线 Three.js 查看器（本地 vendor，无 CDN） |
| `villa.blend` | Blender 工程 |
| `build_villa.py` | 总装脚本（约 3 秒重建全场景） |
| `lib/kit.py` `mats.py` `arch.py` `furni.py` `nature.py` `details.py` | 几何内核 / 材质 / 建筑构件 / 家具 / 植物 / 门窗细节 |
| `lib/texgen.py` + `textures/` | 12 套可平铺 PBR 贴图（albedo + normal） |
| `prep_assets.py` + `lib/assets.py` + `assets/` | PolyHaven CC0 成品植被（树/松/花/地被）的下载、减面、实例化 |
| `audit.py` + `walls.json` | 布局审查（浮空/穿墙/越界/穿插） |
| `render_shots.py` `plan_shots.py` | 透视出图 / 分层平面出图 |

## 重建

```bash
cd <repo>/villa
blender -b --python build_villa.py
"blender" -b villa.blend --python render_shots.py -- cams=CAM_Hero mode=day
"blender" -b villa.blend --python plan_shots.py
"blender" -b villa.blend --python audit.py        # 布局体检
python lib/texgen.py --res 512                                                    # 重生成贴图（1 秒）
```

层高、开间、退台位置都在 `build_villa.py` 顶部常量里：`Z1/Z2/Z3`（三层标高）、`BX0/BX1`、`BY0/BY1`（主体边界）、`F3Y0/F3Y1`（三层退台）、`BAL_Y`（阳台外沿）、`WALL_T/PAR_T`（墙厚）。
