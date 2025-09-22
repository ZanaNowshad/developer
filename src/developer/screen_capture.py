"""Screen capture utilities leveraging the MSS and PyGetWindow libraries."""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from typing import List, Optional

# Pillow is optional; fall back gracefully when unavailable.
try:  # pragma: no cover - import guard
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - Pillow not installed
    Image = None  # type: ignore

from .content import CallToolResult, Content, Role
from .errors import ToolError

try:  # pragma: no cover - optional dependency during import
    import mss
except ImportError:  # pragma: no cover - handled at runtime
    mss = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency during import
    import pygetwindow as gw
except ImportError:  # pragma: no cover
    gw = None  # type: ignore[assignment]

MAX_WIDTH = 768


class ScreenCapture:
    """Provides display and window screenshots."""

    async def capture(
        self, display: Optional[int], window_title: Optional[str]
    ) -> CallToolResult:
        if Image is None:
            raise ToolError.internal_error(
                "Screen capture requires the Pillow package to be installed"
            )
        if mss is None:
            raise ToolError.internal_error(
                "Screen capture is unavailable because the 'mss' package is not installed"
            )
        if window_title and gw is None:
            raise ToolError.internal_error(
                "Capturing windows by title requires the 'pygetwindow' package"
            )
        screenshot = await asyncio.to_thread(
            self._capture_sync, display or 0, window_title
        )
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return CallToolResult.success_result(
            [
                Content.text_content("Screenshot captured", audience=[Role.ASSISTANT]),
                Content.image_content(encoded, "image/png", priority=0.0),
            ]
        )

    async def list_windows(self) -> CallToolResult:
        if gw is None:
            message = (
                "Window enumeration requires the 'pygetwindow' package. Install it to use this tool."
            )
            return CallToolResult.success_result(
                [
                    Content.text_content(message, audience=[Role.ASSISTANT]),
                    Content.text_content(message, audience=[Role.USER], priority=0.0),
                ]
            )
        titles = await asyncio.to_thread(self._list_window_titles)
        if titles:
            text = "Available windows:\n" + "\n".join(titles)
        else:
            text = "No windows found"
        return CallToolResult.success_result(
            [
                Content.text_content(text, audience=[Role.ASSISTANT]),
                Content.text_content(text, audience=[Role.USER], priority=0.0),
            ]
        )

    @staticmethod
    def _capture_sync(display: int, window_title: Optional[str]) -> Image.Image:
        with mss.mss() as sct:  # type: ignore[call-arg]
            if window_title:
                windows = gw.getWindowsWithTitle(window_title)  # type: ignore[union-attr]
                if not windows:
                    raise ToolError.invalid_params(
                        f"No window found with title '{window_title}'"
                    )
                window = windows[0]
                box = {
                    "left": window.left,
                    "top": window.top,
                    "width": window.width,
                    "height": window.height,
                }
                shot = sct.grab(box)
            else:
                monitors = sct.monitors
                if display + 1 >= len(monitors):
                    raise ToolError.invalid_params(
                        f"{display} was not an available monitor, {len(monitors) - 1} found."
                    )
                shot = sct.grab(monitors[display + 1])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            new_height = int(image.height * ratio)
            image = image.resize((MAX_WIDTH, new_height), Image.LANCZOS)
        return image

    @staticmethod
    def _list_window_titles() -> List[str]:
        titles = []
        for title in gw.getAllTitles():  # type: ignore[union-attr]
            normalized = title.strip()
            if normalized and normalized != "<No Title>":
                titles.append(normalized)
        return titles
