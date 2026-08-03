# 方案设计：书法高清大图系统（DESIGN-calligraphy-hd-image-system）

> 依据：REQ-calligraphy-hd-image-system V1.2（已确认）  
> 版本：D0.1（待确认）  
> 日期：2026-08-03  
> 状态：方案待人工确认，确认后方可进入开发（AGENTS.md B1）

---

## 1. 目标与非目标

目标：实现需求定义的离线处理管线——输入清单 → 下载归档 → 拼接原图 → 瓦片/缩略图 → 黑白候选 → 人工选择 → 双钩候选 → 人工选择 → 装配 Manifest，全部产物遵守统一坐标与对象键契约。

非目标：不实现移动端接口/页面；不实现 OSS 上传（仅产出可迁移的对象键布局）；不在本阶段确定 JPEG 质量数值、双钩质量指标与性能 SLO（REQ §15.2，随方案确认后细化）。

## 2. 总体架构

### 2.1 组件与边界（对应 REQ §3.1）

| 模块 | 职责 | 依赖 | 交付物 |
|---|---|---|---|
| `downloader` | 解析清单、下载、校验、归档来源文件 | httpx、Pillow/pyvips | 归档文件 + 来源记录 |
| `stitcher` | 高度统一等比缩放、从右向左拼接、位置映射 | pyvips / Pillow、numpy | original.jpg + 映射数据 |
| `tiling` | 金字塔瓦片生成（三版本统一契约） | pyvips / Pillow | tiles/{version}/{z}/{x}_{y}.jpg |
| `thumbnails` | 9:16 缩略图 + jump2x | Pillow | thumbs/{index}.jpg |
| `binarize` | 2–10 个黑白候选 + 质量边界校验 | OpenCV、DoxaPy | bw/candidates/*.png |
| `hook` | 基于已选黑白图生成 2–10 个双钩候选 | OpenCV | hook/candidates/*.png |
| `review` | 独立评审工具：并排比较、坐标对照、确认选择 | FastAPI、OpenSeadragon | Web 工具 + 选择记录 |
| `manifest` | 装配并校验统一 Manifest | pydantic | manifest.json |
| `records` | processing.json 状态机与处理记录 | pydantic | records/processing.json |

### 2.2 端到端数据流

```text
清单 JSON ─▶ downloader ─▶ stitcher ─▶ original.jpg + 映射
                                   ├─▶ tiling ─▶ 原图瓦片
                                   └─▶ thumbnails ─▶ thumbs + jump2x
binarize(original.jpg) ─▶ 黑白候选 ─▶ review 选择 ─▶ bw/selected.png ─▶ tiling(黑白瓦片)
hook(bw/selected.png) ─▶ 双钩候选 ─▶ review 选择 ─▶ hook/selected.png ─▶ tiling(双钩瓦片)
manifest 装配（全部校验通过后发布）
records/processing.json 贯穿全程（状态机）
```

### 2.3 目录结构（建议）

```text
hd_image_system/
  __init__.py
  config.py          # 任务配置：version_id、根前缀、JPEG 质量等
  models.py          # pydantic 模型：SourceItem、DownloadRecord、Manifest 等
  downloader.py
  stitcher.py
  tiling.py
  thumbnails.py
  binarize.py
  hook.py
  manifest.py
  records.py         # processing.json 状态机
  review/            # FastAPI 评审工具（api.py + static/）
  cli.py             # 阶段命令入口：download/stitch/tile/bw/hook/review/manifest
tests/               # pytest：单测 + 样例端到端
```

## 3. 关键技术选型（开源优先，REQ §12 / AGENTS.md C）

### 3.1 瓦片金字塔生成

| 方案 | 说明 | 优劣 | 结论 |
|---|---|---|---|
| **libvips `dzsave`（pyvips）** | 官方成熟操作，超大图内存友好，直接产出 256×256 JPEG 金字塔 | 快、省内存、久经考验；层命名需按我方 z0=最小层 契约重排 | ★ 推荐 |
| GDAL `gdal2tiles` | GIS 生态成熟 | 面向地理坐标、产物结构冗余，与移动端契约不匹配 | 备选 |
| 自研 Pillow 金字塔 | 逐层 resize + 切片 | 简单可控；80000×5000 全分辨率内存压力大、慢 | 回退方案 |

### 3.2 拼接与高度统一

| 方案 | 说明 | 优劣 | 结论 |
|---|---|---|---|
| **pyvips `arrayjoin`/`join`** | 支持超大图流式拼接，内存占用小 | 快、省内存；依赖 libvips 运行时 | ★ 推荐 |
| Pillow `paste` | 一次性画布粘贴 | 实现简单；全分辨率画布内存占用高（80000×5000×3 ≈ 1.2GB） | 回退/单图模式 |
| OpenCV `hconcat` | 已知有序位置，无需特征配准 | 数组入内存，超大图受限 | 不推荐 |

### 3.3 黑白图二值化

| 方案 | 说明 | 优劣 | 结论 |
|---|---|---|---|
| **OpenCV + DoxaPy** | Otsu/自适应/Sauvola/Niblack/Wolf 多种算法出候选 | 轻量、可解释、参数化出 2–10 候选；DoxaPy 为文档二值化专门库 | ★ 推荐 |
| 纯 OpenCV 阈值 | Otsu + 自适应 + 直方图极性修正 | 依赖最少；候选多样性有限 | 备选 |
| SauvolaNet 等深度学习 | 端到端二值化网络 | 质量上限可能更高；引入模型依赖与推理成本，可解释性差 | 暂缓 |

印章处理：红色通道/HSV 掩码提取印章区域，归入黑色前景（REQ §6.1）。

### 3.4 书法双钩图

无成熟一键开源方案（调研到 OpenCV 轮廓、骨架化与书法笔画研究项目）。采用：

| 方案 | 说明 | 优劣 | 结论 |
|---|---|---|---|
| **OpenCV 轮廓策略族** | findContours 层级/简化参数/Canny/骨架膨胀 组合出 2–10 候选 | 可控、可参数化、依赖少 | ★ 推荐 |
| 骨架中轴恢复（thinning + 重建） | ximgproc.thinning 得到中轴再重建轮廓 | 更适合"双钩"书法语义，但参数敏感 | 作为候选策略之一 |

双钩质量量化指标由 REQ §15.2 待定项在本方案确认后补充，不作为本版硬指标。

### 3.5 评审工具

| 方案 | 说明 | 优劣 | 结论 |
|---|---|---|---|
| **FastAPI + OpenSeadragon** | 后端服务瓦片/清单，前端用 OpenSeadragon 自定义 TileSource 并排比较 | 移动端同族查看器、放大细节体验好；独立 standalone | ★ 推荐 |
| 纯静态页面 + 原生 Canvas | 无后端依赖 | 实现成本高、细节查看体验弱 | 备选 |

### 3.6 依赖清单（conda 环境 `zgy_hd_py311`）

`pyvips`（libvips）、`pillow`、`numpy`、`opencv-python`、`doxapy`、`httpx`、`fastapi`、`uvicorn`、`pydantic`、`pytest`、`ruff`、`mypy`、`black`、`isort`。

## 4. 关键设计决策（★ 需确认）

### ★D1 金字塔层命名与层级公式

REQ §7.1 定义 `Z=0` 为全局最小层、`Z=Zmax` 为原始分辨率层。统一公式：

```text
Zmax = ceil(log2(max(W, H) / tile_size))        # 80000×5000 → Zmax=9
scale_z = 2^(z - Zmax)                          # z ∈ [0, Zmax]
tile_count_x(z) = ceil(W * scale_z / 256)
tile_count_y(z) = ceil(H * scale_z / 256)
```

每层瓦片数为 1×1 起步（80000×5000 时 z0=1×1，z9=313×20）。REQ §10.2 示例为示意值，以本公式为准。

### ★D2 瓦片生成方式

优先 libvips `dzsave`（DeepZoom 布局，256×256、overlap=0、JPEG），生成后做**层级重排**（DeepZoom 的 0=全分辨率 → 我方 Zmax=全分辨率，即 `z_new = Zmax - z_old`）或自研 pyvips 逐层生成以完全贴合我方命名。推荐前者（复用成熟实现 + 一次重命名）。

### ★D3 黑白候选算法集

候选策略族（2–10 个，每候选记录策略标识+参数）：

1. Otsu 全局阈值（block 参数变体）
2. 自适应均值 / 自适应高斯（block size、C 变体）
3. Sauvola / Wolf（DoxaPy，k、window 变体）
4. 印章红色通道掩码合并（所有策略统一执行）
5. 极性修正：检测前景占比（黑底白字 → 反转），统一白底黑字输出

### ★D4 双钩候选策略集

1. `RETR_EXTERNAL` 外轮廓 + 简化系数变体
2. `RETR_LIST` 全层级轮廓（含内部结构）变体
3. Canny 边缘 + 形态学闭合变体
4. 骨架化（thinning）→ 按宽度膨胀重建双钩线

输出统一为白底黑线 PNG，画布与原图一致（REQ §6.2）。

### ★D5 缩略图与 jump2x

- 单图模式：`n = ceil(W / 1080)` 段，从右向左；末段强制 `[0, 1080]` 允许重叠；高度 ≥1920 居中裁 1080×1920，高度 <1920 按实际高度输出（不做特殊处理）。
- 多图模式：每个分屏图对应一张，非 9:16 以物理中心裁取；高度不足同单图策略。
- `jump2x`：每缩略图区域中心 X → 按 D1 公式换算 z=0…Zmax 的 tile-x。

### ★D6 评审工具

FastAPI 提供作品清单、候选列表、瓦片代理与确认接口；前端 OpenSeadragon 双视图并排 + 同步坐标 + 缩放对比；选择确认写回 `processing.json` 并记录操作者/时间。

### ★D7 记录文件结构（`records/processing.json`）

```json
{
  "version_id": "...",
  "status": {"original": "published", "bw": "selected", "hook": "pending_selection"},
  "sources": [{"source_index": 1, "img_id": "...", "source_url": "...",
               "download": {"status": "ok", "time": "...", "local_path": "...", "format": "jpg", "size": [w, h]},
               "scaled": false, "x_range": [0, 28000]}],
  "original": {"width": 80000, "height": 5000, "status": "published"},
  "bw": {"candidates": [{"candidate_id": "...", "strategy": "...", "params": {}, "path": "..."}],
         "selected": {"candidate_id": "...", "operator": "...", "time": "..."}},
  "hook": {"candidates": [...], "selected": null},
  "manifest": {"path": "...", "published_at": "..."}
}
```

字段名可随实现微调，状态机与 REQ §6.3 一致。

## 5. 错误处理与重处理

- 下载失败/不可读/格式不支持/尺寸越界：记录阶段原因，停止并保留现场，不发布 Manifest（REQ §4.3；AC-04b）。
- 每阶段产物写入独立对象键，失败阶段可单独重跑（幂等覆盖）。
- 候选保留：选择完成前全分辨率保留；整套作品处理完毕后未选候选可清理（REQ §9.1）。

## 6. 分步验证方式（AGENTS.md B3）

| 步骤 | 验证方式 | 验收依据 |
|---|---|---|
| 清单解析 | 单测：27 项样例排序、单图/多图判定 | AC-01 |
| 下载归档 | 单测（mock 下载）+ 样例真实下载一次 | AC-01、AC-04b |
| 高度统一+拼接 | 样例数据生成 original.jpg，断言尺寸/X 区间/顺序 | AC-02、AC-04 |
| 位置映射 | 断言各层 tile-x 范围与中心点 | AC-03 |
| 瓦片生成 | 三版本同层同网格一致性断言 + 视觉抽查 | AC-08 |
| 黑白候选 | 断言 2–10 个、二值 0/255、同尺寸、印章入前景 | AC-05、AC-06 |
| 双钩候选 | 断言 2–10 个、同尺寸同坐标 | AC-07 |
| 评审工具 | 手动：并排比较/缩放/坐标对照/确认回写 | AC-15 |
| Manifest | 单测：状态→模板空串规则、thumbnails 倒序、jump2x 合法 | AC-09、AC-10、AC-13、AC-14 |
| 存储布局 | 单测：对象键可预测、version_id 分区 | AC-16 |
| 全量 | `pytest` + `ruff` + `mypy` + `black` + `isort` | AGENTS.md G4 |

## 7. 影响范围（AGENTS.md B2）

全部为新增文件：`hd_image_system/`（约 10 个模块 + review 子包）、`tests/`、`pyproject.toml`、`requirements.yml`（conda 环境导出）、README（运行说明）；本方案文档与既有 REQ/TASKLIST 无冲突。

## 8. 里程碑（对应 TASKLIST）

| 里程碑 | 任务 | 出口条件 |
|---|---|---|
| M1 基建 | T0.1–T0.4 | 方案确认、环境可用、待定项确定 |
| M2 获取归档 | T1.1–T1.4 | 样例清单下载归档完成、记录完整 |
| M3 拼接导航 | T2.1–T2.4 | original.jpg + 映射校验通过 |
| M4 黑白 | T3.1–T3.3 | 候选可评审、选择回写 |
| M5 双钩 | T4.1–T4.2 | 候选可评审 |
| M6 评审工具 | T5.1–T5.4 | 端到端选择流程可用 |
| M7 瓦片/缩略图/Manifest | T6.1–T6.5 | 三版本瓦片 + manifest 校验通过 |
| M8 存储与迁移 | T7.1–T7.3 | 对象键布局符合契约 |
| M9 全量验证 | T8.1–T8.3 | pytest/ruff/mypy 全绿、文档同步 |

## 9. 待确认项（随本方案一并确认）

1. ★D1 层命名与公式（推荐公式如上）。
2. ★D2 瓦片生成：dzsave + 层级重排（推荐）还是自研逐层生成。
3. ★D3 黑白候选算法集（推荐 OpenCV + DoxaPy）。
4. ★D4 双钩候选策略集（推荐 OpenCV 轮廓族）。
5. ★D5 缩略图/jump2x 实现口径。
6. ★D6 评审工具技术栈（FastAPI + OpenSeadragon）。
7. ★D7 processing.json 记录结构。
8. JPEG 编码质量数值、双钩质量指标、性能 SLO（REQ §15.2，建议在本方案确认时给出初步值或验收口径）。
