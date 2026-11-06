# PROMPT · 复刻提示词

> 把下面**整段**喂给任意具备「文件读写 + 命令行 + Blender」能力的 AI Agent，即可从零复刻本项目。
> 提示词里每一条硬约束都是实际踩坑后写进去的，照做能少走 80% 的弯路。

---

## 0. 角色与目标

你是一名建筑可视化工程师。用 **Blender 5.x + Python 脚本**程序化生成一栋**三层现代新中式别墅**（含庭院），并交付一个**可旋转、可分层查看的网页查看器**。

交付物必须是**可一键重建的工程**，而不是一个手工 .blend 文件：

```
<project>/
├── build_villa.py        # 总装：一次跑完生成整栋建筑
├── lib/
│   ├── kit.py            # 累积式几何内核（GB 类）+ 三向 box UV
│   ├── mats.py           # 材质表（PBR 参数 + 贴图接线）
│   ├── arch.py           # 建筑构件：开洞墙/门窗/栏杆/楼梯/庑殿顶/披檐/月洞门/亭
│   ├── furni.py          # 家具与生活小物（50+ 件）
│   ├── nature.py         # 程序化植物（松/竹/灌木/景石/睡莲）
│   ├── details.py        # 门扇、檐角等次要构件
│   ├── texgen.py         # 程序化贴图（纯 numpy 自写 PNG）
│   └── assets.py         # 成品模型（PolyHaven）实例化
├── prep_assets.py        # 成品模型预处理（导入→减面→压贴图→归一化→存 blend）
├── audit.py              # 布局审查：浮空/沉地/穿墙/越界/穿插
├── render_shots.py       # 日/夜出图
├── plan_shots.py         # 逐层正交平面图（带中文标注）
├── textures/             # 12 套可平铺 albedo + normal
├── viewer/index.html     # 离线 Three.js 查看器（单文件）
├── previews/             # 日景/夜景/平面图
└── villa.glb             # 网页模型
```

---

## 1. 硬性设计参数（不要自由发挥）

| 项 | 值 |
|---|---|
| 主体平面 | 16 × 12 m（x −8…8，y −6…6） |
| 层高 | F1 3.40 / F2 3.20 / F3 2.80，楼板面 z = 0.20 / 3.43 / 6.63 |
| 屋脊 | 11.55 m，三层南向退台 2.6 m |
| 墙厚 | 外墙 0.24 m，内隔墙 0.14 m |
| 屋顶 | 庑殿顶（四坡 + 起翘檐口 + 瓦垄 + 正脊/垂脊） |
| 庭院 | 南院 210 m²：月洞门 + 8.8×5.6 水池 + 石桥 + 木平台 + 四角亭 + 竹林 + 汀步 |
| 房间 | **20 个**（见 §2） |

---

## 2. 房间清单（必须一一对应，rooms.json 要能对上）

| 层 | 房间 |
|---|---|
| F1 | 门厅、客厅、餐厅、厨房、茶室、楼梯间、客卫、家政间 |
| F2 | 主卧、主卫、衣帽间、次卧、书房/儿童房、次卫、家政间2、**阳台（南向，深 2.6 m）** |
| F3 | 客房、家庭厅、静室（榻榻米）、储藏、**露台（含廊架）** |
| 室外 | 南院·前庭、木平台 |

层分组必须导出为顶层空物体：`SITE / GARDEN / F1 / F2 / F3 / ROOF`，供查看器分层开关。

---

## 3. 运行环境（写死，别猜）

| 项 | 值 |
|---|---|
| Blender | `blender`（5.1.2） |
| 无头渲染 | `blender -b xxx.blend --python script.py -- args` |
| **引擎字符串** | **`BLENDER_EEVEE`**（5.1 没有 `BLENDER_EEVEE_NEXT`，写错直接 `enum not found`） |
| Blender 是中文界面 | `nodes.get("Principled BSDF")` 返回 **None** —— 一律按 `n.type == "BSDF_PRINCIPLED"` 取节点 |
| 出图分辨率 | 日景 1600×900 / 平面图 1300×975 |
| 网页 | Three.js 0.160，**离线 vendor 副本**，禁用一切 CDN |

---

## 4. 十二条工程约束（照抄，别重新发明）

1. **累积式几何**：写一个 `GB` 类，每件东西往同一份 `(verts, faces, face_mats)` 里追加，一个空间/构件最后只生成**一个多材质 mesh**。否则 3000 个小物体会让 GLB 爆炸、查看器卡死。
2. **变换栈**：`gb.frame(Matrix)` 上压栈，让"局部坐标系里摆家具"成为默认写法（`place(obj, x, y, z, rot)`）。
3. **UV 用三向 box 投影**：按面法线取主轴，UV = 世界坐标 / 2 m。这样任意物体贴图密度一致、不拉伸、不用手动展 UV。
4. **材质按名字回退**：`Ctx.mesh()` 里材质缺失自动创建，避免 `KeyError: 'M_Screen'` 让整栋楼重建失败。
5. **glTF 轴向**：Blender `(x,y,z)` → glTF `(x, z, −y)`。所以**南面（花园）落在 glTF 的 +Z**，查看器默认机位要在 +Z 侧。`rooms.json` 写坐标时记得 `y → −y`。
6. **每段墙都要留痕**：`wx()` / `wy()` 建墙时把真实墙段写进 `walls.json`。**这是审查脚本唯一可靠的数据源**——整层墙是一个 mesh，用它的包围盒判穿墙会把所有家具都报成穿墙（第一版就是这么错的）。
7. **门洞参数必须落在墙段范围内**：`wy(x, y0, y1, …)` 的洞口参数是 **y 区间**，写成墙外的值会被静默裁掉 → 房间"没有门"。构建时校验。
8. **植物禁植区**：建筑 / 阳台 / 露台 / 亭 / 甲板 / 车道 / 水面 七块矩形，种树前逐株校验，越界直接 SKIP 并打印。
9. **成品模型走 HTTP 直连**：`api.polyhaven.com/assets?t=models&c=trees` 选资产 → `api.polyhaven.com/files/<id>` 取 gltf 下载清单 → 连同 `.bin` 与贴图拉到本地 → `decimate` + 贴图压 512 → 存成 `assets/<name>.blend`。构建时 `bpy.data.libraries.load` **append 一次**，其余副本 `ob.copy()` 共享同一 mesh（glTF 只写一份几何）。**不要**走 Blender 插件通道（addon 常超时）。
10. **实例必须按"缩放后包围盒 zmin"落地**：不同成品模型原点不同，直接 `location.z = 0` 会让整片花境陷进地里 0.2 m。
11. **平摊扫描不是立栽**：PolyHaven 的 `anthurium`/`calathea` 是**标本扫描**（2.8×1.8×0.5 m），按高度缩放后宽达 8 m。室内盆栽要用真三维模型（如 `pine` 缩小成"松盆景"），并给实例化加 `max_w` 宽度钳制。
12. **每次 build 必须确认日志里有 `[villa] DONE`**：脚本抛异常后 Blender 仍会继续跑旧流程，后面的"审计通过"其实是对着旧 .blend 测的（踩过）。

---

## 5. 工作流（四阶段，每阶段有明确验收）

### 阶段 A · 骨架
搭场地/外墙/楼板/楼梯/屋顶/披檐。
**验收**：`villa.blend` 能在无头模式下 3 秒内重建；正立面出图能看到屋顶 + 三层 + 阳台 + 露台。

### 阶段 B · 布置
按 §2 清单逐房间摆家具，每个房间至少 6 件（床/柜/桌椅/灯具/软装）。
**验收**：逐层平面图能看清每个房间的功能。

### 阶段 C · 审查（关键，别跳）
写 `audit.py`，用 `walls.json` 的真实墙段 + 物体世界包围盒，输出五类问题：

- **浮空**：离地 > 6 cm
- **沉地**：低于楼板 > 6 cm
- **穿墙**：与墙段重叠 > 5 cm
- **越界**：超出建筑外轮廓
- **互相穿插**：两个家具包围盒重叠 > 5 cm

必须配白名单，否则报告全是噪声：`CEIL_MOUNT`（吊灯）、`WALL_MOUNT`（挂画/挂钟）、`ON_SURFACE`（台面上的花瓶/茶盘/书/杯）、`ASSET_`（成品植物，树冠越墙正常）、`Parasol`（椅子在伞下正常）、`D_`（门套与墙重叠是正常构造）。

**验收**：`TOTAL 0 处问题`。

### 阶段 D · 精修
贴图 / 门窗 / 檐口瓦当 / 水面 / 树形 / 生活小物 / 成品植被。
**验收**：`[mats] textured materials: 26/26`；出图 10 张（日景 4 + 夜景 2 + 平面 4）。

---

## 6. 材质与贴图

`lib/texgen.py`：纯 numpy + 自写 PNG 编码器（zlib + crc32），生成 **12 套严格可平铺** albedo + 切线空间法线：

`plaster / stone / stone_light / marble / wood_oak / wood_walnut / wood_charred / tile / fabric / rug / grass / gravel`

- 噪声基元自己实现：周期性 value noise（**取模索引**才能平铺）+ fbm + ridged + warp
- 法线从高度场逐像素求导（OpenGL Y+ 约定）
- **法线贴图降到 256²**（512² 每张 700 KB，会让 GLB 白涨 8 MB）
- 材质侧用 Mapping 节点按各自 tile 尺寸二次缩放 → 导出为 glTF `KHR_texture_transform`（three.js 原生支持）
- 石/砖纹理别把法线强度调太高：Plaster 的 NormalMap strength **0.26** 就够，再高就像灰泥样板

---

## 7. 成品植被（PolyHaven CC0）

```bash
# 1. 选资产（看 polycount / tags）
curl -s "https://api.polyhaven.com/assets?t=models&c=trees"      # 还有 plants / flowers / ground cover / shrubs
# 2. 取下载清单（gltf 1k）
curl -s "https://api.polyhaven.com/files/jacaranda_tree"
# 3. 下 .gltf + .bin + textures 到 assets/<id>/
# 4. 预处理（一次性）
blender -b --python prep_assets.py -- pine jacaranda shrub flower cover
#    → 导入 → 合并 → Decimate（jacaranda 3.86M→19 万面）→ 贴图压 512 → 落地归一化 → 存 assets/*.blend
# 5. 构建时实例化（共享 mesh）
assets.instance(CTX, "GARDEN", "jacaranda", "big0", x, y, 0.02, height=8.0)
```

| 用途 | 资产 | 减面后 |
|---|---|---|
| 背景乔木 | `jacaranda_tree` | 19.3 万面 |
| 造型松 / 松盆景 | `pine_sapling_small` | 4.8 万面 |
| 灌木绿篱 | `shrub_03` | 4972 面 |
| 花境 / 地被 | `flower_gazania`、`periwinkle_plant` | ~8k / ~12k 面 |

---

## 8. 网页查看器（单文件 index.html）

必须实现：

| 功能 | 要点 |
|---|---|
| 旋转 | OrbitControls，禁钻地（maxPolarAngle）、阻尼、按需渲染 |
| 分层 | 六层 toggle（全景/花园/一层/二层/三层/屋顶/场地），按 GLB 顶层空物体分组 |
| 昼夜 | 0–24h 滑杆：太阳方位/高度 → 平行光 + 半球光 + 渐变天空 ShaderMaterial；PMREM 生成 `scene.environment` |
| 房间标注 | 读 `rooms.json` 自投影 HTML 标签，按楼层过滤、屏幕空间去重、点击飞行 |
| 剖切 | 水平剖切平面，滑杆 0–10 m |
| 预设 | 鸟瞰 / 正立面 / 庭院 / 室内，`R` 键复位（**同时恢复层级与关剖切**） |
| 降级 | GLB/JSON 缺失时用占位建筑；纯离线 |

**点房间飞行的正确写法**（第一版就是错的，这里直接给对的）：

```js
// ❌ 错：相机放在 target + (0.62,0.46,-0.78)*d —— 朝建筑背面、只抬 0.46 m
//    室内房间必然钻进墙体，画面只剩一片空白 + 悬空标签
// ✅ 对：只留该层 + 按房间标签高度自动剖切 + 斜上方看进去（掀顶剖面视角）
const indoor = ['F1','F2','F3'].includes(room.floor);
if (indoor) {
  for (const n of LAYER_NAMES) state.layers[n] = (n === room.floor || n === 'SITE');
  applyLayers();
  clipRange.value = String(Math.max(0.4, room.pos[1] - 0.1));
  clipState.enabled = true; applyClip(); togClip.classList.add('on');
  const k = viewScale();
  tween.start(new THREE.Vector3(room.pos[0] + 2.0*k, room.pos[1] + 3.4*k, room.pos[2] + 4.4*k),
              new THREE.Vector3(...room.pos), 1.15);
}
```

**GLTFLoader 的隐藏坑**：`import { GLTFLoader } from './vendor/GLTFLoader.js'` 会再 import `../utils/BufferGeometryUtils.js` —— 少这一个文件，整条 module graph 静默不执行，表现为加载条卡 0%、DOM 上没有任何 dataset。必须把 `utils/` 一起拷进 vendor。

---

## 9. 迭代协议（用户会逐图挑问题）

用户会截图圈问题，典型是这样的：*"图一柜子挡门 / 图二椅子放反还太远 / 图三树穿模 / 图四点房间变空白"*。处理方式固定：

1. **先复现再改**：每条都先定位到具体对象名或代码行（`grep -n "F1_Entry_Console" build_villa.py`）。
2. **能加护栏的就加护栏**：椅子错位 → 改坐标；植物穿模 → 加 `plant_ok()` 禁植区，以后不会再犯。
3. **改完必须重跑 build + audit + 出图**，三样都过才算完。
4. **报告里写清根因**，不要只说"已修复"。

---

## 10. 验收清单

```bash
blender -b --python build_villa.py                 # 必须有 [villa] DONE
blender -b villa.blend --python audit.py           # 必须 TOTAL 0 处问题
blender -b villa.blend --python render_shots.py -- cams=CAM_Hero,CAM_Court res=1600x900 mode=day
blender -b villa.blend --python render_shots.py -- cams=CAM_Night res=1600x900 mode=night
blender -b villa.blend --python plan_shots.py      # 四张平面图
python lib/texgen.py --res 512                     # 12 套贴图，1 秒
python -m http.server 8901                         # 在工程根目录起服务，开 /viewer/index.html
```

- [ ] `[villa] DONE` + `[mats] textured materials: 26/26`
- [ ] `audit.py` 五类全 0
- [ ] 日景 4 + 夜景 2 + 平面 4 全部出图，中文标注清晰
- [ ] 查看器：六层可切、昼夜可拖、标注可点、剖切可用、`console.error` 为 0
- [ ] 离线：断网状态下页面仍能加载（本地 vendor）

---

## 11. 附录 · 错误速查

| 现象 | 原因 | 修法 |
|---|---|---|
| `enum "BLENDER_EEVEE_NEXT" not found` | 5.x 引擎名变了 | 用 `BLENDER_EEVEE` |
| `nodes.get("Principled BSDF")` 返回 None | 中文界面节点名被本地化 | 按 `n.type == "BSDF_PRINCIPLED"` 遍历 |
| `KeyError: 'M_Screen'` | 材质未定义 | `Ctx.mesh()` 加材质自动创建兜底 |
| `TypeError: place() got multiple values for argument 'z'` | 自定义函数内部也有 `z` 关键字参数 | 内部参数改名（如 `top`） |
| `NameError: src_radius is not defined` | 解包变量名写错（`sr`） | 修变量名；并确认 build 日志有 DONE |
| 相机对着天空 | 用位置差算朝向 | `d.to_track_quat("-Z","Y").to_euler()` |
| 披檐内高外低 | 原点与倾角符号反了 | 原点 z = `z - drop`，方向向量 z = `+drop` |
| 庑殿顶四角重叠 | 用矩形参数化 | 改梯形/三角网格 + `track_quat` 逐根摆放 |
| 平面图被自家楼板挡住 | 全楼都在正交相机的视锥里 | 渲染前隐藏名字含 `_Slab`/`_Ceiling` 的物体 |
| 查看器白屏 | 缺 `BufferGeometryUtils.js` | 整个 `utils/` 拷进 vendor |
| 画面发灰 | 没有环境光 | 用程序化渐变天空生成 PMREM 当 `scene.environment` |
| GLB 体积暴涨 | 贴图/几何没压 | 法线 256²、树木 Decimate、实例共享 mesh |

---

## 12. 一句话版本

> 用 Blender Python 脚本程序化建一栋 16×12 m、三层、庑殿顶的新中式别墅（20 个房间 + 210 m² 南院），12 套 numpy 生成的 PBR 贴图 + PolyHaven CC0 成品植被，用 `audit.py` 把"浮空/穿墙/越界/穿插"审到 0，导出 GLB + rooms.json，配一个离线 Three.js 查看器（分层/昼夜/标注/剖切/点房间掀顶飞行），最后出 10 张带中文标注的日景、夜景与平面图。
