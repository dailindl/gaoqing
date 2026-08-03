from hd_image_system.mapping import (
    build_source_maps,
    tile_x_for_center,
    tile_x_range,
    zmax_for_size,
)
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
