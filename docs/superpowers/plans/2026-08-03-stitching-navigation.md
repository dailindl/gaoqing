# 拼接与导航模块（M3）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现原图拼接与导航映射：高度统一等比缩放（§4.3）、从右向左拼接（§5.1）、来源位置映射（§5.2）、金字塔层级公式（§7.1/§8.4），并接入 `stitch` CLI。

**Architecture:** 新增 `mapping.py`（层级公式与 tile 映射）与 `stitcher.py`（高度统一 + pyvips 流式拼接 + 放置计算）；`models.py` 增加 `LayerMap`/`SourceMap`；`cli.py` 增加 `stitch` 子命令并回写 `records/processing.json`。

**Tech Stack:** Python 3.11（conda env `zgy_hd_py311`）、pyvips/libvips 8.18.3、Pillow、pydantic v2、pytest、ruff、mypy、black、isort。

## Global Constraints

- Python 3.11+；所有函数必须有 type hints，docstring 使用 Google 风格（AGENTS.md）。
- 路径操作必须使用 `pathlib.Path`，禁止 `os.path`（AGENTS.md）。
- 拼接方向从右向左：`img_num=1` 位于最右侧，原点 `(0,0)` 为左上角（REQ §5.1）。
- 高度统一：取最小公共高度 `min_h` 等比缩放，使用高质量重采样（Pillow LANCZOS）（REQ §4.3）。
- 金字塔公式：`Zmax = ceil(log2(max(W,H)/256))`，`scale_z = 2^(z-Zmax)`（DESIGN D1）。
- 运行测试：`conda run -n zgy_hd_py311 python -m pytest`；质量门禁同 M2。
- 提交信息关联需求编号（AGENTS.md D3）。

---

### Task 1: 位置映射与金字塔公式（mapping.py）

**Files:**
- Modify: `hd_image_system/models.py`（新增 `LayerMap`、`SourceMap`）
- Create: `hd_image_system/mapping.py`
- Test: `tests/test_mapping.py`

**Interfaces:**
- Consumes: `Placement`（Task 2 定义，`source_index/x_start/x_end`）。
- Produces: `zmax_for_size(width,height)->int`、`tile_x_range(x_start,x_end,z,zmax)->tuple[int,int]`、`tile_x_for_center(x_start,x_end,z,zmax)->int`、`build_source_maps(placements,width,height)->list[SourceMap]`。

- [ ] **Step 1: 写失败测试**

`tests/test_mapping.py`：
```python
from hd_image_system.mapping import build_source_maps, tile_x_for_center, tile_x_range, zmax_for_size
from hd_image_system.stitcher import Placement


def test_zmax_for_size() -> None:
    assert zmax_for_size(80000, 5000) == 9
    assert zmax_for_size(256, 256) == 0


def test_tile_x_range_known_canvas() -> None:
    # 画布 1024x512，Zmax=2；z2 为全分辨率层
    assert tile_x_range(0, 256, 2, 2) == (0, 0)
    assert tile_x_range(768, 1024, 2, 2) == (3, 3)
    # z1 scale=0.5：x[768,1024) -> x'[384,512) -> tile 1
    assert tile_x_range(768, 1024, 1, 2) == (1, 1)
    # z0 scale=0.25：x[768,1024) -> x'[192,256) -> tile 0
    assert tile_x_range(768, 1024, 0, 2) == (0, 0)


def test_tile_x_for_center() -> None:
    assert tile_x_for_center(0, 256, 2, 2) == 0
    assert tile_x_for_center(768, 1024, 2, 2) == 3


def test_build_source_maps() -> None:
    placements = [
        Placement(source_index=1, x_start=768, x_end=1024),
        Placement(source_index=2, x_start=0, x_end=768),
    ]

    maps = build_source_maps(placements, 1024, 512)

    assert len(maps) == 2
    first = maps[0]
    assert first.x_start == 768
    assert first.x_end == 1024
    assert [layer.z for layer in first.layers] == [0, 1, 2]
    assert first.layers[-1].tile_x_start == 3
    assert first.layers[-1].tile_x_end == 3
    assert first.layers[-1].tile_x_center == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_mapping.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`models.py` 追加：
```python
class LayerMap(BaseModel):
    """某层级下来源图覆盖的 tile-X 信息。"""

    z: int
    tile_x_start: int
    tile_x_end: int
    tile_x_center: int


class SourceMap(BaseModel):
    """单个来源图在拼接原图中的位置映射（REQ §5.2）。"""

    source_index: int
    x_start: int
    x_end: int
    center_x: float
    layers: list[LayerMap]
```

`mapping.py`：
```python
"""瓦片金字塔层级与来源位置映射（REQ §5.2、§7.1、§8.4）。"""

import math

from hd_image_system.models import LayerMap, SourceMap
from hd_image_system.stitcher import Placement

TILE_SIZE = 256


def zmax_for_size(width: int, height: int, tile_size: int = TILE_SIZE) -> int:
    max_dim = max(width, height)
    if max_dim <= tile_size:
        return 0
    return math.ceil(math.log2(max_dim / tile_size))


def scale_for_z(z: int, zmax: int) -> float:
    return 2.0 ** (z - zmax)


def tile_x_range(
    x_start: int, x_end: int, z: int, zmax: int, tile_size: int = TILE_SIZE
) -> tuple[int, int]:
    scale = scale_for_z(z, zmax)
    start = math.floor((x_start * scale) / tile_size)
    end = math.floor(((x_end - 1) * scale) / tile_size)
    return start, end


def tile_x_for_center(
    x_start: int, x_end: int, z: int, zmax: int, tile_size: int = TILE_SIZE
) -> int:
    center = (x_start + x_end - 1) / 2.0
    scale = scale_for_z(z, zmax)
    return math.floor((center * scale) / tile_size)


def build_source_maps(
    placements: list[Placement], width: int, height: int, tile_size: int = TILE_SIZE
) -> list[SourceMap]:
    zmax = zmax_for_size(width, height, tile_size)
    maps: list[SourceMap] = []
    for placement in placements:
        center = (placement.x_start + placement.x_end - 1) / 2.0
        layers = []
        for z in range(zmax + 1):
            t_start, t_end = tile_x_range(placement.x_start, placement.x_end, z, zmax, tile_size)
            layers.append(
                LayerMap(
                    z=z,
                    tile_x_start=t_start,
                    tile_x_end=t_end,
                    tile_x_center=tile_x_for_center(placement.x_start, placement.x_end, z, zmax, tile_size),
                )
            )
        maps.append(
            SourceMap(
                source_index=placement.source_index,
                x_start=placement.x_start,
                x_end=placement.x_end,
                center_x=center,
                layers=layers,
            )
        )
    return maps
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_mapping.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/models.py hd_image_system/mapping.py tests/test_mapping.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 金字塔层级与来源位置映射"
```

---

### Task 2: 高度统一与从右向左拼接（stitcher.py）

**Files:**
- Create: `hd_image_system/stitcher.py`
- Test: `tests/test_stitcher.py`

**Interfaces:**
- Consumes: `DownloadResult`。
- Produces: `UnifiedImage(...)`、`Placement(source_index,x_start,x_end)`、`unify_heights(sources,dest_dir)->list[UnifiedImage]`、`compute_placements(images)->list[Placement]`、`stitch(images,dest_path,quality=95)->tuple[int,int]`。

- [ ] **Step 1: 写失败测试**

`tests/test_stitcher.py`：
```python
from pathlib import Path

from PIL import Image

from hd_image_system.models import DownloadResult
from hd_image_system.stitcher import UnifiedImage, compute_placements, stitch, unify_heights


def _make_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color).save(path, format="PNG")


def _source(index: int, path: Path, size: tuple[int, int]) -> DownloadResult:
    return DownloadResult(
        source_index=index,
        img_id=f"u{index}",
        source_url="http://example.com/x.jpg",
        status="ok",
        local_path=str(path),
        file_format="png",
        width=size[0],
        height=size[1],
    )


def test_unify_heights_scales_to_min(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _make_png(a, (200, 100), (255, 0, 0))
    _make_png(b, (160, 80), (0, 255, 0))
    _make_png(c, (120, 60), (0, 0, 255))

    unified = unify_heights([_source(1, a, (200, 100)), _source(2, b, (160, 80)), _source(3, c, (120, 60))], tmp_path / "out")

    assert [u.unified_size[1] for u in unified] == [60, 60, 60]
    assert [u.scaled for u in unified] == [True, True, False]
    assert unified[0].unified_size[0] == 120
    assert unified[2].unified_path == c


def test_compute_placements_right_to_left() -> None:
    images = [
        UnifiedImage(1, "u1", Path("a"), Path("a"), (200, 60), (200, 60), False),
        UnifiedImage(2, "u2", Path("b"), Path("b"), (160, 60), (160, 60), False),
        UnifiedImage(3, "u3", Path("c"), Path("c"), (120, 60), (120, 60), False),
    ]

    placements = compute_placements(images)

    assert [(p.source_index, p.x_start, p.x_end) for p in placements] == [
        (1, 280, 480),
        (2, 120, 280),
        (3, 0, 120),
    ]


def _assert_color_close(pixel: tuple[int, int, int], expected: tuple[int, int, int], tol: int = 12) -> None:
    assert all(abs(a - b) <= tol for a, b in zip(pixel, expected))


def test_stitch_right_to_left(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _make_png(a, (200, 60), (255, 0, 0))
    _make_png(b, (160, 60), (0, 255, 0))
    _make_png(c, (120, 60), (0, 0, 255))
    images = [
        UnifiedImage(1, "u1", a, a, (200, 60), (200, 60), False),
        UnifiedImage(2, "u2", b, b, (160, 60), (160, 60), False),
        UnifiedImage(3, "u3", c, c, (120, 60), (120, 60), False),
    ]

    width, height = stitch(images, tmp_path / "original.jpg", quality=90)

    assert (width, height) == (480, 60)
    out = Image.open(tmp_path / "original.jpg").convert("RGB")
    assert out.size == (480, 60)
    _assert_color_close(out.getpixel((420, 30)), (255, 0, 0))  # 最右侧：第 1 张
    _assert_color_close(out.getpixel((200, 30)), (0, 255, 0))  # 中间：第 2 张
    _assert_color_close(out.getpixel((60, 30)), (0, 0, 255))  # 最左侧：第 3 张
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_stitcher.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`stitcher.py`：高度统一用 Pillow LANCZOS；拼接用 pyvips 流式 join（倒序使第 1 项位于最右侧）；JPEG 输出，alpha 合并到白底。

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_stitcher.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/stitcher.py tests/test_stitcher.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 高度统一与从右向左拼接"
```

---

### Task 3: stitch CLI 与记录回写

**Files:**
- Modify: `hd_image_system/cli.py`
- Test: `tests/test_cli_stitch.py`

**Interfaces:**
- Consumes: `unify_heights`、`compute_placements`、`stitch`、`build_source_maps`、`load_record`/`save_record`。
- Produces: `main(["stitch", "--version-id", ..., "--storage-root", ..., "--quality", ...]) -> int`。

- [ ] **Step 1: 写失败测试**

`tests/test_cli_stitch.py`：
```python
from pathlib import Path

from PIL import Image

from hd_image_system.cli import main
from hd_image_system.models import DownloadResult
from hd_image_system.records import load_record, new_record, save_record


def _make_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


def test_cli_stitch_ok(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    source_dir = storage / "v1" / "source"
    _make_png(source_dir / "1.png", (200, 100), (255, 0, 0))
    _make_png(source_dir / "2.png", (120, 60), (0, 0, 255))
    record = new_record("v1")
    record.sources = [
        DownloadResult(source_index=1, img_id="u1", source_url="http://x", status="ok", local_path=str(source_dir / "1.png"), file_format="png", width=200, height=100),
        DownloadResult(source_index=2, img_id="u2", source_url="http://x", status="ok", local_path=str(source_dir / "2.png"), file_format="png", width=120, height=60),
    ]
    save_record(record, storage / "v1" / "records" / "processing.json")

    rc = main(["stitch", "--version-id", "v1", "--storage-root", str(storage), "--quality", "90"])

    assert rc == 0
    assert (storage / "v1" / "original.jpg").is_file()
    loaded = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert loaded.status["original"] == "selected"
    assert loaded.original is not None
    assert loaded.original["width"] == 240
    assert loaded.sources[0].x_range == (120, 240)
    assert loaded.sources[1].x_range == (0, 120)
    assert loaded.sources[0].scaled is True
    assert len(loaded.original["source_maps"]) == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_cli_stitch.py -v`
Expected: FAIL（stitch 子命令不存在）

- [ ] **Step 3: 实现**

`cli.py`：新增 `stitch` 子命令（`--version-id`、`--storage-root`、`--quality` 默认 95）；读取记录 → `unify_heights` → `compute_placements` → `stitch` → `build_source_maps` → 回写来源 `x_range/scaled/original_size/unified_size`、`original` 字段与状态 `selected`。

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_cli_stitch.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/cli.py tests/test_cli_stitch.py
git commit -m "feat(REQ-calligraphy-hd-image-system): stitch CLI 与位置映射回写"
```

---

## 全量验证

`conda run -n zgy_hd_py311 python -m pytest` 全绿；`ruff check .`；`black --check .`；`isort --check .`；`mypy hd_image_system`。

## Self-Review 结论

- 覆盖：§4.3（高度统一）、§5.1（从右向左拼接）、§5.2（位置映射）、§7.1（金字塔公式）、§8.4（中心点 tile-X）、§6.3（原图状态 selected）均有任务。
- 无占位符；`Placement` 在 mapping/stitcher/CLI 间签名一致；`SourceMap`/`LayerMap` 字段一致。
- 待技术方案确认项（JPEG 质量数值）以 `--quality` 可配置默认 95 处理，后续收口。
