import asyncio
from pathlib import Path

import pytest

pytest.importorskip("PIL", reason="Pillow required for image processing tests")
from PIL import Image

from developer.image_processor import ImageProcessor
from developer.errors import ToolError


def test_process_nonexistent_file(tmp_path: Path) -> None:
    processor = ImageProcessor()
    with pytest.raises(ToolError):
        asyncio.run(processor.process(tmp_path / "missing.png", None))


def test_process_invalid_resize(tmp_path: Path) -> None:
    processor = ImageProcessor()
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (4, 4), color="red").save(image_path)
    with pytest.raises(ToolError):
        asyncio.run(processor.process(image_path, "1/3"))


def test_process_success(tmp_path: Path) -> None:
    processor = ImageProcessor()
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (10, 10), color="blue").save(image_path)
    result = asyncio.run(processor.process(image_path, None))
    assert result.success is True
    assert result.content[1].type == "image"
