import asyncio
from collections.abc import Awaitable
from contextlib import suppress

import pytest

from developer import app as app_module
from developer.app import build_app
from developer.config import AppSettings
from developer.server import Developer
from developer.stubs import fastapi as fastapi_stub


@pytest.fixture(autouse=True)
def _force_fastapi_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "FastAPI", fastapi_stub.FastAPI)
    monkeypatch.setattr(app_module, "HTTPException", fastapi_stub.HTTPException)
    monkeypatch.setattr(app_module, "JSONResponse", fastapi_stub.JSONResponse)
    monkeypatch.setattr(app_module, "WebSocket", fastapi_stub.WebSocket)
    monkeypatch.setattr(app_module, "WebSocketDisconnect", fastapi_stub.WebSocketDisconnect)
    monkeypatch.setattr(app_module, "status", fastapi_stub.status)


def _run(coro: Awaitable[None]) -> None:
    asyncio.run(coro)


def test_app_token_flow_and_routes() -> None:
    settings = AppSettings()
    developer = Developer(settings=settings)
    app = build_app(settings=settings, developer=developer)

    async def scenario() -> None:
        await app.trigger_event("startup")
        try:
            with pytest.raises(Exception) as exc_info:
                await app.dispatch("GET", "/tools")
            assert getattr(exc_info.value, "status_code", None) == fastapi_stub.status.HTTP_401_UNAUTHORIZED.value

            token_payload = await app.dispatch(
                "POST",
                "/oauth/token",
                client_id=settings.security.oauth_client_id,
                client_secret=settings.security.oauth_client_secret,
            )
            token = token_payload["access_token"]

            tools_response = await app.dispatch("GET", "/tools", token=token)
            tool_names = {tool["name"] for tool in tools_response["tools"]}
            assert "text_editor" in tool_names

            analysis = await app.dispatch(
                "POST",
                "/analysis/ast",
                token=token,
                source="def sample():\n    return 1\n",
                mode="signatures",
            )
            texts = [item["text"] for item in analysis["content"]]
            assert any("sample" in text for text in texts)
        finally:
            await app.trigger_event("shutdown")

    _run(scenario())


def test_app_websocket_broadcast() -> None:
    settings = AppSettings()
    developer = Developer(settings=settings)
    app = build_app(settings=settings, developer=developer)

    async def scenario() -> None:
        await app.trigger_event("startup")
        try:
            websocket = fastapi_stub.WebSocket()
            websocket_task = asyncio.create_task(app.dispatch_websocket("/ws/events", websocket))
            await asyncio.sleep(0)

            await developer.realtime.broadcast(
                "tool_executed", {"tool": "demo", "success": True}
            )
            message = await asyncio.wait_for(websocket._next_sent(), timeout=1)
            assert message["event"] == "tool_executed"
            assert message["payload"]["tool"] == "demo"
            assert message["payload"]["success"] is True

            websocket_task.cancel()
            with suppress(asyncio.CancelledError):
                await websocket_task
        finally:
            await app.trigger_event("shutdown")

    _run(scenario())


def test_role_based_access_control() -> None:
    settings = AppSettings()
    developer = Developer(settings=settings)
    app = build_app(settings=settings, developer=developer)

    async def scenario() -> None:
        await app.trigger_event("startup")
        try:
            security = app.state.security  # type: ignore[attr-defined]
            observer_token = await security.issue_token(roles=["observer"])

            tools_response = await app.dispatch("GET", "/tools", token=observer_token)
            tool_names = {tool["name"] for tool in tools_response["tools"]}
            assert "text_editor" in tool_names
            assert "code_analysis" not in tool_names

            with pytest.raises(Exception) as exc_info:
                await app.dispatch(
                    "POST",
                    "/analysis/ast",
                    token=observer_token,
                    source="def sample():\n    return 1\n",
                    mode="signatures",
                )
            assert (
                getattr(exc_info.value, "status_code", None)
                == fastapi_stub.status.HTTP_403_FORBIDDEN.value
            )

            with pytest.raises(Exception) as exc_info:
                await app.dispatch("POST", "/plugins/reload", token=observer_token)
            assert (
                getattr(exc_info.value, "status_code", None)
                == fastapi_stub.status.HTTP_403_FORBIDDEN.value
            )

            admin_token = await security.issue_token(roles=["admin"])
            reload_response = await app.dispatch("POST", "/plugins/reload", token=admin_token)
            assert reload_response["status"] == "reloaded"
        finally:
            await app.trigger_event("shutdown")

    _run(scenario())
