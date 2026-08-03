"""命令行入口（获取与归档阶段，REQ §4）。"""

import argparse
from pathlib import Path

from hd_image_system.downloader import download_source
from hd_image_system.models import parse_input_list, processing_mode
from hd_image_system.records import load_record, save_record


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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
