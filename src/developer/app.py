"""FastAPI application exposing the developer platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import AppSettings
from .errors import ToolError
from .security import SecurityManager
from .server import Developer

try:  # pragma: no cover - executed when dependency exists
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
    from fastapi.responses import JSONResponse
except ModuleNotFoundError:  # pragma: no cover - fallback path
    from .stubs.fastapi import FastAPI, HTTPException, JSONResponse, WebSocket, WebSocketDisconnect, status


def build_app(settings: Optional[AppSettings] = None, developer: Optional[Developer] = None) -> FastAPI:
    settings = settings or AppSettings()
    developer = developer or Developer(settings=settings)
    security = SecurityManager(settings)

    app = FastAPI(title="Developer Platform API", version="1.1.0")
    app.state.security = security

    @app.on_event("startup")
    async def _startup() -> None:
        await developer.startup()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await developer.shutdown()

    @app.post("/oauth/token")
    async def issue_token(client_id: str, client_secret: str) -> Dict[str, Any]:
        if (
            client_id != settings.security.oauth_client_id
            or client_secret != settings.security.oauth_client_secret
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED.value, "Invalid client credentials")
        token = await security.issue_token(username=client_id)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.security.token_ttl_seconds,
        }

    async def current_user(token: Optional[str] = None):
        return await security.dependency()(token=token)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "time": datetime.now(timezone.utc).isoformat(),
            "plugins": [record.__dict__ for record in developer.plugin_manager.describe()],
        }

    @app.get("/tools")
    async def list_tools(token: Optional[str] = None):
        user = await current_user(token)
        tools = list(await developer.list_tools())
        return {"tools": security.filter_tools(user, tools)}

    @app.post("/tools/{name}/invoke")
    async def invoke_tool(name: str, arguments: Dict[str, Any], token: Optional[str] = None):
        user = await current_user(token)
        try:
            tool_obj = developer.registry.get(name)
        except ToolError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND.value, exc.message) from exc
        security.authorize_tool(user, tool_obj)
        result = await developer.call_tool(name, arguments, tool=tool_obj)
        return result.to_dict()

    @app.get("/plugins")
    async def plugins(token: Optional[str] = None) -> Dict[str, Any]:
        await current_user(token)
        return {"plugins": [record.__dict__ for record in developer.plugin_manager.describe()]}

    @app.post("/plugins/reload")
    async def reload_plugins(token: Optional[str] = None) -> Dict[str, Any]:
        user = await current_user(token)
        security.require_plugin_admin(user)
        await developer.reload_plugins()
        return {"status": "reloaded"}

    @app.get("/audits")
    async def audits(limit: int = 20, token: Optional[str] = None) -> Dict[str, Any]:
        await current_user(token)
        records = await developer.database.recent(limit)
        return {
            "records": [
                {"tool_name": record.tool_name, "payload": record.payload, "created_at": record.created_at.isoformat()}
                for record in records
            ]
        }

    @app.post("/analysis/ast")
    async def ast_analysis(source: str, mode: str = "signatures", token: Optional[str] = None):
        user = await current_user(token)
        try:
            tool_obj = developer.registry.get("code_analysis")
        except ToolError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND.value, exc.message) from exc
        security.authorize_tool(user, tool_obj)
        result = await developer.call_tool(
            "code_analysis", {"source": source, "mode": mode}, tool=tool_obj
        )
        return result.to_dict()

    @app.websocket("/ws/events")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        subscriber = await developer.realtime.connect()
        try:
            while True:
                message = await subscriber.queue.get()
                await websocket.send_json(message)
        except WebSocketDisconnect:  # pragma: no cover - interactive path
            pass
        finally:
            await developer.realtime.disconnect(subscriber)

    return app


__all__ = ["build_app"]
