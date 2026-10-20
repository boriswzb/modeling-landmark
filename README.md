# 埃及吉萨金字塔群 · 3D 复原模型

本项目用 Blender 4.5 / Python 程序化重建了吉萨高原三大金字塔及其核心环境：胡夫（Khufu）、哈夫拉（Khafre）、门卡乌拉（Menkaure）金字塔，以及王后金字塔、马斯塔巴墓群、河谷/葬祭庙、堤道和狮身人面像。模型采用**米制真实尺度**，表现的是**今日遗迹状态**，而非公元前 26 世纪的完整原貌。

## 交付文件

| 文件 | 说明 |
|---|---|
| `Giza_Pyramids.blend` | 完整 Blender 场景，所有贴图已打包，可直接打开 |
| `Giza_Pyramids.glb` | 通用 glTF 二进制模型，内嵌贴图，可用于网页/Unity/Unreal 等 |
| `renders/hero_golden.png` | 黄昏斜光下的三金字塔主视觉（1600×800，全景裁切） |
| `renders/hero_golden_full.png` | 同一机位的未裁切版本（1600×1000） |
| `renders/aerial.png` | 高原鸟瞰，展示整体布局与堤道（1600×1000） |
| `renders/khafre_casing.png` | 哈夫拉金字塔顶部保留的白色大理岩外壳细节（1200×1500） |
| `renders/site_plan.png` | 正射总平面图，含名称、尺寸标注、比例尺与指北针（1600×1600） |
| `renders/sphinx.png` | 新版低模 Sphinx 与围坑、哈夫拉背景（1200×1000） |
| `renders/contact_sheet.jpg` | 四图汇总版面（2400×2000） |
| `renders/viewer_preview.jpg` | 在线查看器主界面截图 |
| `renders/viewer_exploded.jpg` | 在线查看器模型分解截图 |
| `renders/viewer_sphinx.jpg` | 查看器“狮身”预设截图 |
| `viewer/` | 在线交互 3D 查看器（Three.js，本地渲染） |
| `start_viewer.bat` | 一键启动本地查看器并打开浏览器 |
| `textures/` | 程序生成的石灰岩、花岗岩、砂岩、岩层、圣蛇与头巾纹理 |
| `assets/` | Sphinx 低多边形模型及来源/许可说明 |
| `build_giza.py` | 场景生成脚本（可重新生成 .blend / .glb / 渲染） |
| `make_textures.py` | 无缝程序纹理生成脚本 |
| `make_sky.py` | 黄昏天空环境贴图生成脚本 |

## 主要尺寸与坐标

坐标系：**+X 向东，+Y 向北，+Z 向上**；原点位于胡夫金字塔底面中心；胡夫底面标高为 0 m。

| 建筑 | 纬度 / 经度 | 底边 | 原高 | 现高 | 坡角 |
|---|---|---|---|---|---|
| 胡夫金字塔 | 29.97917°N, 31.13417°E | 230.33 × 230.33 m | 146.6 m | 138.5 m | 51°50′40″ |
| 哈夫拉金字塔 | 29.97611°N, 31.13083°E | 215.25 × 215.25 m | 143.5 m | 136.4 m | 53°10′ |
| 门卡乌拉金字塔 | 29.97250°N, 31.12833°E | 102.2 × 104.6 m | 65.0 m | 61.0 m | 51°20′25″ |
| 大狮身人面像 | 29.97526°N, 31.13758°E | 长 73 m / 宽 19 m / 高 20 m | — | — | — |

主要参考：Lehner《The Complete Pyramids》(1997)、Verner《The Pyramids》(2001)、Petrie (1883)；坐标取自 Wikipedia / Wikidata 条目。

## 模型内容

- **三大金字塔**：按原坡角生成逐层收分的石砌体；胡夫顶部为今貌的平顶，哈夫拉顶部保留约 10 m 高的白色图拉石灰岩外壳，门卡乌拉底部保留红色阿斯旺花岗岩饰面。
- **附属金字塔**：胡夫东侧 3 座、门卡乌拉南侧 3 座王后金字塔。
- **狮身人面像**：采用 3D Warehouse 的低多边形 Sphinx 模型（3dHH，2009），按 73 m 长、约 19 m 高重新缩放、UV 展开并贴图，放入凿岩围坑。相比上一版程序化体块，卧姿、前肢、脚爪和头颈比例明显更接近真实 Sphinx；但仍是低模，面部细节有限。
  > 来源与许可见 [assets/README.md](assets/README.md)。该素材基于埃及旅游局（Egyptian Tourist Authority）的原始 Giza 模型改编；在对外再分发或商用前，请核对 3D Warehouse 当前条款。
- **墓葬群**：西场、东场、中央场与南场约 300 座马斯塔巴，按真实场域走向布置（个体位置为示意）。
- **祭祀建筑**：胡夫、哈夫拉、门卡乌拉的葬祭庙，哈夫拉河谷神庙，以及三条堤道。
- **地形**：10 km × 10 km 吉萨高原，含台地、东侧向尼罗河方向的坡降、西侧低山脊、狮身人面像围坑和采石场碎石堆。

## 在线交互查看器

本项目附带一个无需构建的浏览器查看器，支持自由旋转、缩放、模型分解、标签聚焦、日间/黄昏光照和线框模式。

```powershell
cd D:\建模
python -m http.server 8765 --bind 127.0.0.1
```

打开 **http://127.0.0.1:8765/viewer/**，或双击 `start_viewer.bat`。详细操作与部署方式见 [viewer/README.md](viewer/README.md)。

> 必须通过 HTTP 服务打开，不能直接双击 `viewer/index.html`（`file://` 会阻止 GLB 与 ES Module 加载）。

## 打开方式

### Blender
用 **Blender 4.5 LTS** 或更新版本打开 `Giza_Pyramids.blend`。场景已包含：
- `Hero camera`：主视觉相机
- `Aerial camera`：鸟瞰相机
- `Khafre detail camera`：外壳细节相机
- `Site plan camera`：正射平面相机（标注集合默认隐藏）

### glTF / GLB
`Giza_Pyramids.glb` 为 Y-up、米制，可直接导入 Three.js、Unity、Unreal、Blender 等。由于 glTF 不支持 Blender 的全部程序节点，GLB 中的材质略简化，但基础色/法线/粗糙度贴图已内嵌。

### 重新生成
```powershell
# 生成纹理与天空
python make_textures.py
python make_sky.py

# 生成模型并导出
.\.venv\Scripts\python.exe build_giza.py --export

# 渲染最终图
.\.venv\Scripts\python.exe build_giza.py --full --plan
```

## 渲染设置

- 引擎：Cycles（CPU）
- 色彩管理：AgX，Medium High Contrast
- 主光：低角度暖色太阳（方位约 80°，高度约 10°），冷色天空补光
- 主视觉：1600×800（由 1600×1000 全景裁切），44 samples，OpenImageDenoise
- 平面图：正射相机，正交尺度 1650 m，顶光 65°

## 说明与限制

- 模型表现**现存遗迹**：胡夫无外壳、哈夫拉仅顶部有外壳、门卡乌拉仅底部有花岗岩饰面。
- 马斯塔巴、神庙柱网、堤道的个体位置和残损状态为**示意性复原**，用于提供场域尺度，不应作为考古测绘数据使用。
- 狮身人面像为**低多边形模型**（约 2,100 面），不是高精度摄影测量扫描；面部、头巾和风化细节有限，适合中远距离观看。交互查看器提供 Sphinx 聚焦，但不宜作为雕刻级特写。
- 地形高程为艺术化重建，不代表实测 DEM。

## 参考来源

- [Great Pyramid of Giza — Wikipedia](https://en.wikipedia.org/wiki/Great_Pyramid_of_Giza)
- [Pyramid of Khafre — Wikipedia](https://en.wikipedia.org/wiki/Pyramid_of_Khafre)
- [Pyramid of Menkaure — Wikipedia](https://en.wikipedia.org/wiki/Pyramid_of_Menkaure)
- [Great Sphinx of Giza — Wikipedia](https://en.wikipedia.org/wiki/Great_Sphinx_of_Giza)
- [Giza pyramid complex — Wikipedia](https://en.wikipedia.org/wiki/Giza_pyramid_complex)
- [3D Warehouse: Great Sphinx of Giza by 3dHH](https://3dwarehouse.sketchup.com/model/7ee790a94d0c7d57ae504fdbdb5a7e96) — low-poly Sphinx asset; attribution/terms in [assets/README.md](assets/README.md)
- Mark Lehner, *The Complete Pyramids* (1997); Miroslav Verner, *The Pyramids* (2001); W. M. Flinders Petrie (1883).
