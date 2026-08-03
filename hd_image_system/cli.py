"""命令行入口（获取与归档阶段，REQ §4）。"""

import argparse
from pathlib import Path

from hd_image_system.binarize import generate_bw_candidates
from hd_image_system.downloader import download_source
from hd_image_system.mapping import build_source_maps
from hd_image_system.models import parse_input_list, processing_mode
from hd_image_system.records import load_record, save_record
from hd_image_system.stitcher import compute_placements, stitch, unify_heights


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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
