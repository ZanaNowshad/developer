"""Image processing utilities used by the MCP server."""

from __future__ import annotations

import asyncio
import base64
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

# Pillow is optional; gracefully degrade if unavailable.
try:  # pragma: no cover - import guard
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - Pillow not installed
    Image = None  # type: ignore

from .content import CallToolResult, Content, Role
from .errors import ToolError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_WIDTH = 768


class ImageProcessor:
    """Processes image files and returns base64 data."""

    MAC_SCREENSHOT_RE = re.compile(
        r"^Screenshot \d{4}-\d{2}-\d{2} at \d{1,2}\.\d{2}\.\d{2} (AM|PM|am|pm)(?:\(\d+\))?\.png$"
    )

    def __init__(self) -> None:
        pass

    @staticmethod
    def normalize_mac_screenshot_path(path: Path) -> Path:
        if not path.name:
            return path
        filename = path.name
        match = ImageProcessor.MAC_SCREENSHOT_RE.match(filename)
        if not match:
            return path
        meridian = match.group(1)
        space_pos = filename.lower().rfind(meridian.lower())
        if space_pos == -1:
            return path
        prefix = filename[:space_pos].rstrip()
        suffix = filename[space_pos:]
        new_filename = f"{prefix}\u202F{suffix[1:]}"
        return path.with_name(new_filename)

    async def process(self, path: Path, resize: Optional[str]) -> CallToolResult:
        if Image is None:
            raise ToolError.internal_error(
                "Image processing requires the Pillow package to be installed"
            )
        if path.exists() and path.is_dir():
            raise ToolError.invalid_params(f"The path '{path}' is a directory, not an image file")

        if not path.exists():
            raise ToolError.invalid_params(f"File '{path}' does not exist")

        stat = await asyncio.to_thread(path.stat)
        if stat.st_size > MAX_FILE_SIZE_BYTES:
            raise ToolError.invalid_params(
                (
                    f"File '{path}' is too large ({stat.st_size / (1024 * 1024):.2f}MB)."
                    " Maximum size is 10MB."
                )
            )

        try:
            image = await asyncio.to_thread(Image.open, path)
        except Exception as exc:  # pragma: no cover - pillow errors vary
            raise ToolError.internal_error(f"Failed to open image file: {exc}") from exc

        image = image.convert("RGBA") if image.mode not in {"RGB", "RGBA"} else image
        image = await asyncio.to_thread(self._resize_to_max_width, image)

        if resize is not None:
            image = await asyncio.to_thread(self._apply_resize_factor, image, resize)

        output_format, mime_type = self._determine_format(path)
        data = await asyncio.to_thread(self._encode_image, image, output_format)

        resize_info = f" (resized by {resize})" if resize else ""
        success_text = (
            f"Successfully processed image from {path}{resize_info}."
            f" Final dimensions: {image.width}x{image.height}, format: {mime_type}"
        )
        return CallToolResult.success_result(
            [
                Content.text_content(success_text, audience=[Role.ASSISTANT]),
                Content.image_content(data, mime_type, priority=0.0),
            ]
        )

    @staticmethod
    def _resize_to_max_width(image: Image.Image) -> Image.Image:
        if image.width <= MAX_WIDTH:
            return image
        ratio = MAX_WIDTH / image.width
        new_height = int(image.height * ratio)
        return image.resize((MAX_WIDTH, new_height), Image.LANCZOS)

    @staticmethod
    def _apply_resize_factor(image: Image.Image, factor: str) -> Image.Image:
        mapping = {"1/2": 0.5, "1/4": 0.25}
        if factor not in mapping:
            raise ToolError.invalid_params(
                f"Invalid resize factor '{factor}'. Allowed values: '1/2', '1/4'"
            )
        scale = mapping[factor]
        width = max(int(image.width * scale), 1)
        height = max(int(image.height * scale), 1)
        return image.resize((width, height), Image.LANCZOS)

    @staticmethod
    def _determine_format(path: Path) -> tuple[str, str]:
        ext = path.suffix.lower()
        if ext in {".jpg", ".jpeg", ".webp"}:
            return "JPEG", "image/jpeg"
        return "PNG", "image/png"

    @staticmethod
    def _encode_image(image: Image.Image, fmt: str) -> str:
        buffer = BytesIO()
        params = {}
        if fmt == "JPEG":
            params["quality"] = 85
            if image.mode == "RGBA":
                image = image.convert("RGB")
        image.save(buffer, format=fmt, **params)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
