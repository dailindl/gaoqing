# 瓦片/缩略图/Manifest 装配模块（M7）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现三版本统一金字塔瓦片（§7）、9:16 缩略图与 jump2x（§8）、Manifest 装配与校验（§10）（T6.1–T6.5；AC-08…AC-14）。

**Architecture:** 新增 `tiling.py`（pyvips 逐层生成 z/x_y.jpg，层级公式复用 `mapping.py`）、`thumbnails.py`（单图/多图两种模式 + jump2x）、`manifest.py`（装配 + 校验）；`cli.py` 增加 `tile`/`manifest` 子命令。

**Tech Stack:** Python 3.11（conda env `zgy_hd_py311`）、pyvips/libvips、Pillow、numpy、pydantic v2、pytest、ruff、mypy、black、isort。

## Global Constraints

- Python 3.11+；所有函数必须有 type hints，docstring 使用 Google 风格（AGENTS.md）。
- 路径操作必须使用 `pathlib.Path`，禁止 `os.path`（AGENTS.md）。
- 金字塔：256×256、`Zmax = ceil(log2(max(W,H)/256))`、Zmax 层保留原始分辨率；层级尺寸公式与三版本网格必须完全一致（§7.1/§7.2；AC-08）。
- 瓦片对象键：`{storage}/{version_id}/tiles/{kind}/{z}/{x}_{y}.jpg`（§9.2）。
- 缩略图：单图模式 1080px 右→左分段、末段 `[0,1080]` 允许重叠；多图模式每分屏图一张、按物理中心裁取；高度不足 1920 不做特殊处理（§8；AC-11/12）。
- `jump2x` 覆盖 Z0…Zmax 全部层级且索引合法（§8.4；AC-13）。
- Manifest：`manifest_version`/`version_id`/`layers` 单次/`thumbnails` 倒序/URL 模板按版本状态（§10；AC-09/10/14）。
- 运行测试：`conda run --no-capture-output -n zgy_hd_py311 python -m pytest`；质量门禁同前。
- 提交信息关联需求编号（AGENTS.md D3）。

---

### Task 1: 金字塔瓦片生成（tiling.py）

**Files:**
- Modify: `hd_image_system/mapping.py`（新增 `level_size`、`tile_counts`）
- Create: `hd_image_system/tiling.py`
- Test: `tests/test_tiling.py`

**Interfaces:**
- Consumes: `zmax_for_size`、`level_size`。
- Produces: `generate_tiles(image_path: Path, out_dir: Path, quality: int = 90) -> dict[str, int]`（返回 width/height/zmax）。

- [ ] **Step 1: 写失败测试**（512×256 → Zmax=1：z1=2×1 瓦片、z0=1×1；文件名与尺寸断言）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（逐层 resize(lanczos3) → 强制精确层级尺寸 → crop 256×256 瓦片 → jpegsave）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/mapping.py hd_image_system/tiling.py tests/test_tiling.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 金字塔瓦片生成"
```

---

### Task 2: 缩略图与 jump2x（thumbnails.py）

**Files:**
- Modify: `hd_image_system/models.py`（新增 `Jump2xItem`、`ThumbnailInfo`）
- Create: `hd_image_system/thumbnails.py`
- Test: `tests/test_thumbnails.py`

**Interfaces:**
- Consumes: `zmax_for_size`、`tile_x_for_center`。
- Produces: `generate_thumbnails(original_path, dest_dir, version_id, mode, source_maps, width=1080, root_prefix="/storage", quality=90) -> list[ThumbnailInfo]`。

- [ ] **Step 1: 写失败测试**（单图 3000×2000 → 3 张 1080×1920、index 倒序语义；多图按分屏图 X 区间；高度不足 1920 按实际高度；jump2x 覆盖全部层级）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/models.py hd_image_system/thumbnails.py tests/test_thumbnails.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 缩略图与 jump2x"
```

---

### Task 3: Manifest 装配与校验（manifest.py）

**Files:**
- Modify: `hd_image_system/models.py`（新增 `ManifestValidation`）
- Create: `hd_image_system/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: 记录、缩略图、`zmax_for_size`/`tile_counts`。
- Produces: `build_manifest(version_id, record, thumbnails, root_prefix="/storage") -> dict[str, Any]`、`validate_manifest(manifest) -> ManifestValidation`。

- [ ] **Step 1: 写失败测试**（字段规则、URL 模板状态、thumbnails 倒序、jump2x 合法性；人为破坏后校验失败）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/models.py hd_image_system/manifest.py tests/test_manifest.py
git commit -m "feat(REQ-calligraphy-hd-image-system): Manifest 装配与校验"
```

---

### Task 4: tile/manifest CLI 与端到端

**Files:**
- Modify: `hd_image_system/cli.py`
- Test: `tests/test_cli_pipeline.py`

**Interfaces:**
- Produces: `main(["tile", "--kind", "original|bw|hook", ...])`、`main(["manifest", ...])`。

- [ ] **Step 1: 写失败测试**（manifest 端到端：自动生成原图瓦片与缩略图、写出 manifest.json、原图状态 published；bw/hook tile 后对应 URL 模板非空）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（`tile`：按 kind 生成瓦片并更新状态；`manifest`：原图瓦片/缩略图缺失时自动生成，装配+校验+发布）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/cli.py tests/test_cli_pipeline.py
git commit -m "feat(REQ-calligraphy-hd-image-system): tile/manifest CLI 端到端"
```

---

## 全量验证

`conda run --no-capture-output -n zgy_hd_py311 python -m pytest` 全绿；`ruff check .`；`black --check .`；`isort --check .`；`mypy hd_image_system`。

## Self-Review 结论

- 覆盖：§7（金字塔/一致性）、§8（缩略图/jump2x）、§9.2（瓦片/缩略图/Manifest 对象键）、§10（Manifest 契约）、AC-08…AC-14。
- JPEG 质量数值仍为待定项，默认 90 可配置。
