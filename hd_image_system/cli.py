"""命令行入口（获取与归档阶段，REQ §4）。"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from hd_image_system.binarize import generate_bw_candidates
from hd_image_system.downloader import download_source
from hd_image_system.hook import generate_hook_candidates
from hd_image_system.manifest import build_manifest, validate_manifest
from hd_image_system.mapping import build_source_maps
from hd_image_system.models import ThumbnailInfo, parse_input_list, processing_mode
from hd_image_system.records import load_record, save_record
from hd_image_system.stitcher import compute_placements, stitch, unify_heights
from hd_image_system.thumbnails import generate_thumbnails
from hd_image_system.tiling import generate_tiles


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        含 download 子命令的解析器。
    """
    parser = argparse.ArgumentParser(prog="hd-image", description="书法高清大图处理管线")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="下载并归档来源图片（REQ §4）")
    download.add_argument("--version-id", required=True, help="作品级唯一标识")
    download.add_argument("--input-list", required=True, type=Path, help="输入清单 JSON 路径")
    download.add_argument("--storage-root", type=Path, default=Path("storage"), help="存储根前缀")

    stitch_parser = subparsers.add_parser("stitch", help="拼接原图并生成位置映射（REQ §5）")
    stitch_parser.add_argument("--version-id", required=True, help="作品级唯一标识")
    stitch_parser.add_argument(
        "--storage-root", type=Path, default=Path("storage"), help="存储根前缀"
    )
    stitch_parser.add_argument("--quality", type=int, default=95, help="JPEG 质量（1-100）")

    bw_parser = subparsers.add_parser("bw", help="生成黑白候选（REQ §6.1）")
    bw_parser.add_argument("--version-id", required=True, help="作品级唯一标识")
    bw_parser.add_argument("--storage-root", type=Path, default=Path("storage"), help="存储根前缀")

    hook_parser = subparsers.add_parser("hook", help="生成书法双钩候选（REQ §6.2）")
    hook_parser.add_argument("--version-id", required=True, help="作品级唯一标识")
    hook_parser.add_argument(
        "--storage-root", type=Path, default=Path("storage"), help="存储根前缀"
    )

    review_parser = subparsers.add_parser("review", help="启动人工评审工具（REQ §11）")
    review_parser.add_argument(
        "--storage-root", type=Path, default=Path("storage"), help="存储根前缀"
    )
    review_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    review_parser.add_argument("--port", type=int, default=8000, help="监听端口")

    tile_parser = subparsers.add_parser("tile", help="生成版本瓦片（REQ §7）")
    tile_parser.add_argument("--version-id", required=True, help="作品级唯一标识")
    tile_parser.add_argument(
        "--storage-root", type=Path, default=Path("storage"), help="存储根前缀"
    )
    tile_parser.add_argument(
        "--kind", choices=("original", "bw", "hook"), required=True, help="版本类型"
    )
    tile_parser.add_argument("--quality", type=int, default=90, help="JPEG 质量（1-100）")

    manifest_parser = subparsers.add_parser("manifest", help="装配并发布 Manifest（REQ §10）")
    manifest_parser.add_argument("--version-id", required=True, help="作品级唯一标识")
    manifest_parser.add_argument(
        "--storage-root", type=Path, default=Path("storage"), help="存储根前缀"
    )
    manifest_parser.add_argument("--quality", type=int, default=90, help="JPEG 质量（1-100）")
    return parser


def cmd_download(args: argparse.Namespace) -> int:
    """执行下载与归档阶段。

    Args:
        args: 解析后的命令行参数。

    Returns:
        全部成功返回 0，存在失败返回 1。
    """
    items = parse_input_list(args.input_list)
    mode = processing_mode(items)
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    dest_dir = args.storage_root / args.version_id / "source"

    results = []
    for index, source in enumerate(items, start=1):
        result = download_source(source, index, dest_dir)
        results.append(result)
        if result.status == "failed":
            print(f"下载失败 source_index={index}: {result.failure_reason}")
    record.sources = results
    save_record(record, records_path)

    failed = sum(1 for r in results if r.status == "failed")
    print(f"模式={mode} 来源数={len(results)} 成功={len(results) - failed} 失败={failed}")
    return 0 if failed == 0 else 1


def cmd_stitch(args: argparse.Namespace) -> int:
    """执行原图拼接与导航映射阶段。

    Args:
        args: 解析后的命令行参数。

    Returns:
        成功返回 0，无可用来源图返回 1。
    """
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    ok_sources = [s for s in record.sources if s.status == "ok"]
    if not ok_sources:
        print("没有可用来源图，请先执行 download")
        return 1

    unified = unify_heights(
        ok_sources, args.storage_root / args.version_id / "original" / "segments"
    )
    placements = compute_placements(unified)
    original_path = args.storage_root / args.version_id / "original.jpg"
    width, height = stitch(unified, original_path, quality=args.quality)
    maps = build_source_maps(placements, width, height)

    by_index = {p.source_index: p for p in placements}
    unified_by_index = {u.source_index: u for u in unified}
    for source in record.sources:
        placement = by_index.get(source.source_index)
        if placement:
            source.x_range = (placement.x_start, placement.x_end)
        unified_item = unified_by_index.get(source.source_index)
        if unified_item:
            source.scaled = unified_item.scaled
            source.original_size = unified_item.original_size
            source.unified_size = unified_item.unified_size

    record.original = {
        "width": width,
        "height": height,
        "path": str(original_path),
        "source_maps": [m.model_dump() for m in maps],
    }
    record.status["original"] = "selected"
    save_record(record, records_path)
    print(f"拼接完成: {width}x{height}, 来源映射 {len(maps)} 条")
    return 0


def cmd_bw(args: argparse.Namespace) -> int:
    """生成黑白候选并回写处理记录（REQ §6.1）。

    Args:
        args: 解析后的命令行参数。

    Returns:
        成功返回 0，原图缺失返回 1。
    """
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    if not record.original or not record.original.get("path"):
        print("请先执行 stitch 生成原图")
        return 1
    original_path = Path(record.original["path"])
    if not original_path.is_file():
        print(f"原图不存在: {original_path}")
        return 1
    dest_dir = args.storage_root / args.version_id / "bw" / "candidates"
    candidates = generate_bw_candidates(original_path, dest_dir)
    record.bw = {
        "candidates": [c.model_dump() for c in candidates],
        "selected": None,
    }
    record.status["bw"] = "pending_selection"
    save_record(record, records_path)
    print(f"黑白候选生成: {len(candidates)} 个")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """生成书法双钩候选并回写处理记录（REQ §6.2）。

    Args:
        args: 解析后的命令行参数。

    Returns:
        成功返回 0，已选黑白图缺失返回 1。
    """
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    selected_path: str | None = None
    if record.bw and isinstance(record.bw.get("selected"), dict):
        selected = record.bw["selected"]
        if isinstance(selected, dict):
            path_value = selected.get("path")
            if isinstance(path_value, str):
                selected_path = path_value
    if not selected_path:
        selected_path = str(args.storage_root / args.version_id / "bw" / "selected.png")
    bw_selected = Path(selected_path)
    if not bw_selected.is_file():
        print(f"已选黑白图不存在: {bw_selected}，请先人工选择并放置 bw/selected.png")
        return 1
    dest_dir = args.storage_root / args.version_id / "hook" / "candidates"
    candidates = generate_hook_candidates(bw_selected, dest_dir)
    record.hook = {
        "candidates": [c.model_dump() for c in candidates],
        "selected": None,
    }
    record.status["hook"] = "pending_selection"
    save_record(record, records_path)
    print(f"双钩候选生成: {len(candidates)} 个")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """启动人工评审工具服务（REQ §11）。

    Args:
        args: 解析后的命令行参数。

    Returns:
        服务退出后返回 0。
    """
    import uvicorn

    from hd_image_system.review.api import create_app

    app = create_app(args.storage_root)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def cmd_tile(args: argparse.Namespace) -> int:
    """生成指定版本的统一金字塔瓦片（REQ §7）。

    Args:
        args: 解析后的命令行参数。

    Returns:
        成功返回 0，master 缺失返回 1。
    """
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    if args.kind == "original":
        if not record.original or not record.original.get("path"):
            print("请先执行 stitch 生成原图")
            return 1
        master = Path(record.original["path"])
    elif args.kind == "bw":
        master = args.storage_root / args.version_id / "bw" / "selected.png"
    else:
        master = args.storage_root / args.version_id / "hook" / "selected.png"
    if not master.is_file():
        print(f"{args.kind} master 不存在: {master}")
        return 1
    out_dir = args.storage_root / args.version_id / "tiles" / args.kind
    info = generate_tiles(master, out_dir, quality=args.quality)
    record.status[args.kind] = "generating_tiles" if args.kind == "original" else "published"
    save_record(record, records_path)
    print(f"瓦片生成完成 {args.kind}: {info}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    """装配、校验并发布统一 Manifest（REQ §10）。

    原图瓦片或缩略图缺失时自动生成。

    Args:
        args: 解析后的命令行参数。

    Returns:
        发布成功返回 0，前置缺失或校验失败返回 1。
    """
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    if not record.original or not record.original.get("path") or not record.original.get("width"):
        print("请先执行 stitch 生成原图")
        return 1
    original_path = Path(record.original["path"])
    if not original_path.is_file():
        print(f"原图不存在: {original_path}")
        return 1

    tiles_dir = args.storage_root / args.version_id / "tiles" / "original"
    if (
        record.status["original"] not in ("generating_tiles", "published")
        or not (tiles_dir / "0").is_dir()
    ):
        generate_tiles(original_path, tiles_dir, quality=args.quality)
        record.status["original"] = "generating_tiles"

    thumbnails: list[ThumbnailInfo] | None = None
    if record.original.get("thumbnails"):
        thumbnails = [ThumbnailInfo.model_validate(item) for item in record.original["thumbnails"]]
    if thumbnails is None:
        mode = "single" if len(record.sources) <= 1 else "multi"
        source_maps = record.original.get("source_maps") or []
        thumbs_dir = args.storage_root / args.version_id / "thumbs"
        thumbnails = generate_thumbnails(
            original_path,
            thumbs_dir,
            args.version_id,
            mode,
            source_maps,
            quality=args.quality,
        )
        record.original["thumbnails"] = [t.model_dump() for t in thumbnails]

    manifest = build_manifest(args.version_id, record, thumbnails)
    validation = validate_manifest(manifest)
    if not validation.valid:
        print("Manifest 校验失败: " + "; ".join(validation.errors))
        return 1
    manifest_path = args.storage_root / args.version_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record.manifest = {
        "path": str(manifest_path),
        "published_at": datetime.now(UTC).isoformat(),
    }
    record.status["original"] = "published"
    save_record(record, records_path)
    print(f"Manifest 发布: {manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """程序入口。

    Args:
        argv: 命令行参数列表；None 表示使用 sys.argv。

    Returns:
        退出码。
    """
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return cmd_download(args)
    if args.command == "stitch":
        return cmd_stitch(args)
    if args.command == "bw":
        return cmd_bw(args)
    if args.command == "hook":
        return cmd_hook(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "tile":
        return cmd_tile(args)
    if args.command == "manifest":
        return cmd_manifest(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
