# 第三方素材署名 / Credits

本项目自建的部分（几何、材质、贴图生成器、汽车与邻栋、查看器）为 MIT。

## 植被与户外家具

来自 [PolyHaven](https://polyhaven.com/)，**CC0 1.0（公共领域）**，
可商用、可修改、无需署名——此处署名仅为记录来源。

| 资产 | 用途 | 面数 |
|---|---|---|
| `fir_tree_01` | 冷杉（针叶） | 25,000 |
| `pine_tree_01` | 松（针叶） | 24,999 |
| `island_tree_01` | 阔叶乔木 5.0 m | 24,999 |
| `island_tree_02` | 阔叶乔木 3.4 m | 25,000 |
| `tree_small_02` | 密叶小乔木 4.6 m | 24,976 |
| `shrub_01` / `shrub_02` / `shrub_03` / `shrub_04` | 灌木与地被 | 5.3k / 5.2k / 2.4k / 3.7k |
| `grass_medium_02` | 观赏草 | 2,489 |
| `periwinkle_plant` | 花 | 4,999 |
| `celandine_01` | 花 | 4,301 |
| `fern_02` | 蕨 | 2,384 |
| `ArmChair_01` / `sofa_02` / `Ottoman_01` | 户外家具 | 5.6k / 2.7k / 4.2k |

这些文件经 `prep_assets.py` 处理：应用对象变换 → 归一化到底部原点 → 贴图降到 1k 并打包 → 减面。
原始文件可从 polyhaven.com 按同名检索下载。

## 运行库

- [three.js](https://threejs.org/) — MIT，`viewer/vendor/` 内为本地副本（离线可用）。
  `three.module.js` / `GLTFLoader.js` / `OrbitControls.js`。
- [Blender](https://www.blender.org/) — GPL，仅作为建模与渲染工具使用，其代码不在本仓库内。

## 参考图

设计参考自**现代简约小院（三百平）**的 5 张实景照片。

> **这些照片是第三方网图，未随本仓库分发。**
> 仓库与文档中不包含任何参考图原文件，也不含其水印或可识别信息。
> 若需复现设计过程，请自备同类参考图。

## 字体

查看器使用系统字体栈，不加载任何网络字体，无字体许可问题。
