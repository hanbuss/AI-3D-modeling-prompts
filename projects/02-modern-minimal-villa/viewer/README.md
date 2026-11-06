# mvilla / viewer

现代简约别墅的离线 three.js 交互查看器。**单文件** `index.html` + 本地 vendor，无任何 CDN / 网络字体。

## 起服务

资产路径按「服务根」自动解析，两种都可以：

```bash
# A. 服务根 = mvilla/   → 访问 /viewer/
cd mvilla && python -m http.server 8899
#   http://127.0.0.1:8899/viewer/

# B. 服务根 = 工作区根  → 访问 /mvilla/viewer/
cd .. && python -m http.server 8899
#   http://127.0.0.1:8899/mvilla/viewer/
```

GLB 候选链：`../mvilla.glb` → `mvilla.glb` → `../../mvilla.glb`。
`?glb=` 可强制指定，例如 `?glb=../mvilla.glb`。

## 交互

| 操作 | 说明 |
|---|---|
| 拖动 / 滚轮 / 右键拖动 | 旋转 / 缩放 / 平移（带阻尼，极角钳制在地面以上） |
| 楼层 全部·1F·2F·3F | 单层隔离 = 隐藏该层以上与 ROOF，从上方看进室内 |
| 掀顶 | 隐藏 ROOF 层 |
| 水平剖切 | 拖滑杆切掉上部结构；与楼层联用时会自动对齐到该层顶板 |
| 日间 / 夜间 / 自动循环 | 太阳位置·色温·天空·室内灯与 `WinGlow/LampShade/Glow/Flame/Uplight` 自发光一起变 |
| 太阳滑杆 06–20 | 驱动平行光方位/高度/颜色，并改变阴影贴图分辨率（低太阳角=更柔的阴影） |
| 材质 真实/素模 | 素模把全部材质换成单色哑光，看体块关系 |
| 质量 高/中/低 | 像素比（上限 1.6 / 低 1.2）+ 阴影贴图 2048·1024·512 |
| 房间列表 | 读 `rooms.json` 按层分组；点击=只留该层 + 剖切 + 3/4 俯视机位（永不空画面） |
| 房间标注 | 投影到屏幕，被遮挡/越界即隐藏；窄屏默认关闭、上限 8 条 |
| 兴趣点 | 8 个（院门/门庭/平台/格栅亭/水幕/枯山水/客厅/露台），点击飞过去并给一行说明 |
| 截图 | canvas → PNG 下载 |

键位：`1/2/3` 单层、`0` 全部、`C` 剖切、`T` 掀顶、`N` 昼夜、`L` 标注、`R` 复位、`H` 面板、`S` 截图、`?` 说明、`F` 全屏、`Esc` 关闭。

窄屏（≤860px 或 pointer:coarse）右侧面板变成底部抽屉，默认收起为 52 px 把手（仍显示标题与状态），按钮 ≥40 px，触屏提示单独一套 DOM。

## 验收钩子

`body.dataset`：`ready / model / groups / meshes / rooms / floor / clip / mat / hour / phase / labels-shown / errors`。
`#insp` 里是当前图层、可见网格数、机位与包围盒的 JSON 快照（`display:none`），无头截图核对用。

URL 预设：`?t=19&clip=6.6&floor=2F&view=aerial&labels=1&night=1&mat=clay&poi=living&room=study&glb=...`

## vendor

`vendor/three.module.js` + `vendor/OrbitControls.js` + `vendor/GLTFLoader.js` + `utils/BufferGeometryUtils.js`（r160；GLTFLoader 内部 `import '../utils/BufferGeometryUtils.js'`，缺它整个 module graph 静默失败）。
