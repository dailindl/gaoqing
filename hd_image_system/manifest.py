"""Manifest 装配与校验（REQ §10）。"""

import math
from typing import Any

from hd_image_system.mapping import TILE_SIZE, level_size, zmax_for_size
from hd_image_system.models import ManifestValidation, ThumbnailInfo
from hd_image_system.records import ProcessingRecord


def _tile_template(root_prefix: str, version_id: str, kind: str) -> str:
    """构造瓦片 URL 模板。"""
    return f"{root_prefix}/{version_id}/tiles/{kind}/{{z}}/{{x}}_{{y}}.jpg"


def build_manifest(
    version_id: str,
    record: ProcessingRecord,
    thumbnails: list[ThumbnailInfo],
    root_prefix: str = "/storage",
) -> dict[str, Any]:
    """装配统一 Manifest（REQ §10）。

    Args:
        version_id: 作品级唯一标识。
        record: 处理记录（含尺寸、状态与来源信息）。
        thumbnails: 缩略图导航信息。
        root_prefix: 存储根前缀。

    Returns:
        Manifest 字典。
    """
    original = record.original or {}
    width = int(original.get("width") or 0)
    height = int(original.get("height") or 0)
    zmax = zmax_for_size(width, height)
    layers = []
    for z in range(zmax + 1):
        level_w, level_h = level_size(width, height, z, zmax)
        layers.append(
            {
                "z": z,
                "tile_count_x": math.ceil(level_w / TILE_SIZE),
                "tile_count_y": math.ceil(level_h / TILE_SIZE),
            }
        )
    status = record.status
    url_template = (
        _tile_template(root_prefix, version_id, "original")
        if status["original"] in ("generating_tiles", "published")
        else ""
    )
    url_template_bw = (
        _tile_template(root_prefix, version_id, "bw") if status["bw"] == "published" else ""
    )
    url_template_hook = (
        _tile_template(root_prefix, version_id, "hook") if status["hook"] == "published" else ""
    )
    thumb_list = [t.model_dump() for t in thumbnails]
    thumb_list.sort(key=lambda t: t["index"], reverse=True)
    return {
        "manifest_version": 1,
        "version_id": version_id,
        "orig_width": width,
        "orig_height": height,
        "max_z": zmax,
        "tile_size": TILE_SIZE,
        "url_template": url_template,
        "url_template_bw": url_template_bw,
        "url_template_hook": url_template_hook,
        "show_thumbnails": True,
        "layers": layers,
        "thumbnails": thumb_list,
    }


def validate_manifest(manifest: dict[str, Any]) -> ManifestValidation:
    """校验 Manifest 契约（AC-09/10/13/14）。

    Args:
        manifest: 待校验的 Manifest 字典。

    Returns:
        校验结果与错误列表。
    """
    errors: list[str] = []
    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version 必须为 1")
    if not manifest.get("version_id"):
        errors.append("缺少 version_id")
    width = int(manifest.get("orig_width") or 0)
    height = int(manifest.get("orig_height") or 0)
    zmax = int(manifest.get("max_z") or 0)
    layers = manifest.get("layers") or []
    if len(layers) != zmax + 1:
        errors.append("layers 数量与 max_z 不一致")
    else:
        for z, layer in enumerate(layers):
            if layer.get("z") != z:
                errors.append(f"layers[{z}] 的 z 不连续")
                break
            level_w, level_h = level_size(width, height, z, zmax)
            expected_x = math.ceil(level_w / TILE_SIZE)
            expected_y = math.ceil(level_h / TILE_SIZE)
            if layer.get("tile_count_x") != expected_x or layer.get("tile_count_y") != expected_y:
                errors.append(f"layers[{z}] 瓦片网格与层级公式不一致")
    if manifest.get("url_template") == "":
        errors.append("url_template 必须非空（原图发布）")
    thumbnails = manifest.get("thumbnails") or []
    indexes = [t.get("index") for t in thumbnails]
    if indexes != sorted(indexes, reverse=True):
        errors.append("thumbnails 未按 index 倒序")
    for thumb in thumbnails:
        jump2x = thumb.get("jump2x") or []
        if len(jump2x) != zmax + 1:
            errors.append(f"thumbnails[{thumb.get('index')}] jump2x 层级数不足")
            continue
        seen = {int(item.get("z")) for item in jump2x}
        if seen != set(range(zmax + 1)):
            errors.append(f"thumbnails[{thumb.get('index')}] jump2x 层级不完整")
            continue
        for item in jump2x:
            z = int(item.get("z"))
            x = int(item.get("x"))
            tile_x_count = int(layers[z].get("tile_count_x"))
            if not 0 <= x < tile_x_count:
                errors.append(f"thumbnails[{thumb.get('index')}] jump2x z={z} x={x} 越界")
    return ManifestValidation(valid=not errors, errors=errors)
