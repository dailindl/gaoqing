def test_package_importable() -> None:
    import hd_image_system  # noqa: F401

    assert hd_image_system.__doc__ is not None
