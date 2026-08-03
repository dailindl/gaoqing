# 人工评审工具模块（M6）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供独立的人工评审工具（§11）：黑白/双钩候选并排比较、缩放与坐标对照、选择确认并回写 `processing.json`（T5.1–T5.4；AC-15）。

**Architecture:** `hd_image_system/review/` 子包：`api.py`（FastAPI：候选列表、原图/候选文件服务、选择确认接口）+ `static/index.html`（OpenSeadragon 双视图同步缩放）；`cli.py` 增加 `review` 子命令启动服务。

**Tech Stack:** Python 3.11（conda env `zgy_hd_py311`）、FastAPI、uvicorn、pydantic v2、OpenSeadragon 4.1.0（CDN）、pytest（TestClient）。

## Global Constraints

- Python 3.11+；所有函数必须有 type hints，docstring 使用 Google 风格（AGENTS.md）。
- 路径操作必须使用 `pathlib.Path`，禁止 `os.path`（AGENTS.md）。
- 评审工具为独立 standalone 工具，不属于移动端瓦片 API（REQ §11）。
- 支持同类型 2–10 候选并排比较、缩放、细节查看、与原图同一物理坐标对照（REQ §11；AC-15）。
- 选择确认必须记录候选标识、参数/策略、路径、选择时间、操作者，并触发正式版本状态流转（§6.3、§11；AC-15）。
- 未确认选择时，候选不得作为已发布版本输出（AC-09 由 Manifest 阶段保证）。
- 运行测试：`conda run --no-capture-output -n zgy_hd_py311 python -m pytest`；质量门禁同前。
- 提交信息关联需求编号（AGENTS.md D3）。

---

### Task 1: FastAPI 后端（review/api.py）

**Files:**
- Create: `hd_image_system/review/__init__.py`
- Create: `hd_image_system/review/api.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes: `load_record`/`save_record`。
- Produces: `create_app(storage_root: Path) -> FastAPI`：
  - `GET /api/versions/{version_id}/candidates/{kind}` → 候选列表 + selected
  - `GET /api/versions/{version_id}/original` → 原图文件
  - `GET /api/versions/{version_id}/candidates/{kind}/{candidate_id}.png` → 候选文件
  - `POST /api/versions/{version_id}/select`（body: kind/candidate_id/operator）→ 复制为 `{kind}/selected.png`、回写记录、状态置 `selected`

- [ ] **Step 1: 写失败测试**（TestClient：候选列表、原图服务、候选文件、确认选择、未知候选 404、index 页面）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（FastAPI 应用；选择确认用 `shutil.copyfile` 复制候选为 selected.png，回写 `record.bw/hook.selected` 与状态）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/review/__init__.py hd_image_system/review/api.py tests/test_review.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 评审工具 FastAPI 后端"
```

---

### Task 2: 前端页面与 review CLI

**Files:**
- Create: `hd_image_system/review/static/index.html`
- Modify: `hd_image_system/cli.py`

**Interfaces:**
- Consumes: 后端 API。
- Produces: `main(["review", "--storage-root", ..., "--host", ..., "--port", ...])` 启动 uvicorn。

- [ ] **Step 1: 写失败测试**（index 页面包含 OpenSeadragon 与确认按钮；parser 支持 review 子命令）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（静态页：双 OpenSeadragon 视图同步缩放、候选列表按钮、确认选择 fetch；`cmd_review` 启动 uvicorn）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add hd_image_system/review/static/index.html hd_image_system/cli.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 评审工具前端与 review CLI"
```

---

## 全量验证

`conda run --no-capture-output -n zgy_hd_py311 python -m pytest` 全绿；`ruff check .`；`black --check .`；`isort --check .`；`mypy hd_image_system`。

## Self-Review 结论

- 覆盖：§11（并排比较/缩放/坐标对照/确认记录）、§6.3（selected 状态）、AC-15。
- 瓦片生成触发（T5.4）由选择后状态 `selected` 承接，正式瓦片生成在 M7 实现。
