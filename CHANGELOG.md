# CHANGELOG

## 2026-08-03（修改前记录，REQ-calligraphy-hd-image-system V1.1 → V1.2）

修改意图：
- 明确输入清单契约：输入为 JSON 数组清单，实测样例 `deepseek_json_20260731_ba67e1.json`，字段 `img_id` / `source_url` / `img_num`；`img_num`（1 起始）为多图拼接权威排序字段。
- 确认三版本（原图、黑白图、双钩图）保持拼接原图原始大小，拼接时仅允许等比例缩放。
- 确认缩略图对应区域高度不足 1920 像素时不做特殊处理（不放大、不填充、不强制裁切），按实际高度输出。
- 澄清黑白图 `0`/`255` 严格二值约束适用于已选黑白图 master 文件（PNG）；对外瓦片为 JPEG，允许有损压缩。
- 状态：需求完善中，待最终确认后生成任务列表。

## 2026-08-03（实际变更，V1.2 已确认）

- 完成上述修订，需求状态置为「已确认，待技术方案设计与开发」。
- 作品级标识定名为 `version_id`（由任务参数提供）；来源图 `img_id` 仅作来源追溯；存储对象键与 Manifest 改用 `version_id`。
- 候选图保留策略：人工选择完成前全部候选全分辨率保留；整套作品处理完毕后未选候选可删除。
- Manifest 增加 `manifest_version` 字段（当前为 1）。
- 已执行 `git init` 并将上述文件作为首次提交。
- 生成任务列表 `TASKLIST-calligraphy-hd-image-system.md`（需求 V1.2 已确认）。
- 生成方案设计文档 `DESIGN-calligraphy-hd-image-system.md`（D0.1，含开源调研结论与备选方案，待人工确认）。
- 方案 D0.1 已按推荐确认（2026-08-03）。
- 新增实施计划 `docs/superpowers/plans/2026-08-03-download-archive.md`（M1+M2 切片）。
- 完成 M1+M2「基建 + 获取归档」开发：
  - 新增 `hd_image_system` 包（config/models/downloader/records/cli）。
  - 输入清单解析（img_num 权威排序、单图/多图判定）、来源图片下载与校验归档、processing.json 处理记录、download CLI。
  - 测试：pytest 15 项通过；ruff/black/isort/mypy 全量通过。
- 完成 M3「拼接与导航」开发（2026-08-03）：
  - 新增 `mapping.py`（Zmax/层级公式、tile-X 映射、来源位置映射）与 `stitcher.py`（高度统一等比缩放、pyvips 从右向左流式拼接）。
  - `stitch` CLI：生成 original.jpg、回写来源 x_range/scaled/尺寸与位置映射，原图状态置为 selected。
  - 新增实施计划 `docs/superpowers/plans/2026-08-03-stitching-navigation.md`。
  - 测试：pytest 23 项通过；ruff/black/isort/mypy 全量通过。
- 完成 M4「黑白候选生成」开发（2026-08-03）：
  - 新增 `binarize.py`：Otsu / 自适应均值 / 自适应高斯 / Sauvola / Wolf 共 8 个候选策略，红色印章掩码归入前景，极性统一为白底黑字。
  - `bw` CLI：生成候选到 bw/candidates、回写记录并置状态 pending_selection。
  - `validate_bw_master`：已选黑白图 master 的质量边界校验（尺寸、二值、白底黑字）。
  - 新增实施计划 `docs/superpowers/plans/2026-08-03-binarize.md`。
  - 测试：pytest 28 项通过；ruff/black/isort/mypy 全量通过。
- 完成 M5「书法双钩候选生成」开发（2026-08-03）：
  - 新增 `hook.py`：外轮廓 / 全层级轮廓 / Canny / 骨架化共 8 个候选策略，输出白底黑线 PNG。
  - `hook` CLI：从已选黑白图生成候选到 hook/candidates、回写记录并置状态 pending_selection。
  - 环境补充安装 `opencv-contrib-python`（提供 ximgproc.thinning）。
  - 新增实施计划 `docs/superpowers/plans/2026-08-03-hook.md`。
  - 测试：pytest 31 项通过；ruff/black/isort/mypy 全量通过。
- 完成 M6「人工评审工具」开发（2026-08-04）：
  - 新增 `review/` 子包：FastAPI 后端（候选列表、原图/候选服务、选择确认接口）+ OpenSeadragon 前端（双视图同步缩放、并排比较、坐标对照）。
  - `review` CLI：启动评审服务（uvicorn）。
  - 选择确认：复制候选为 `{kind}/selected.png`，记录候选标识/策略/参数/路径/时间/操作者，状态置 selected。
  - 新增实施计划 `docs/superpowers/plans/2026-08-04-review-tool.md`。
  - 测试：pytest 38 项通过；ruff/black/isort/mypy 全量通过。
- 修改意图（2026-08-04，M7）：新增瓦片/缩略图/Manifest 装配模块（tiling/thumbnails/manifest + CLI），实现 REQ §7/§8/§10 与 AC-08…AC-14；完成后更新实际变更。
- 完成 M7「瓦片/缩略图/Manifest 装配」开发（2026-08-04）：
  - 新增 `tiling.py`：pyvips 逐层生成统一金字塔瓦片（z=0 最小层 → z=Zmax 原始分辨率，256×256，JPEG）。
  - 新增 `thumbnails.py`：单图 1080px 分段 / 多图按分屏图区间生成 9:16 缩略图与 jump2x；高度不足 1920 不做特殊处理。
  - 新增 `manifest.py`：统一 Manifest 装配（manifest_version/version_id/layers/URL 模板状态规则/thumbnails 倒序）与契约校验（AC-09/10/13/14）。
  - `tile`/`manifest` CLI：瓦片按 kind 生成；manifest 自动补齐原图瓦片与缩略图后装配、校验、发布，原图状态置 published。
  - 新增实施计划 `docs/superpowers/plans/2026-08-04-tiling-manifest.md`。
  - 测试：pytest 48 项通过；ruff/black/isort/mypy 全量通过。
