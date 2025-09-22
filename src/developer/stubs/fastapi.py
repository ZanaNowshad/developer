"""Compact FastAPI stand-in used for testing without external dependencies."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

__all__ = [
    "APIRouter",
    "BackgroundTasks",
    "Depends",
    "FastAPI",
    "HTTPException",
    "JSONResponse",
    "Response",
    "WebSocket",
    "WebSocketDisconnect",
    "status",
    "OAuth2PasswordBearer",
]


class status:
    HTTP_200_OK = HTTPStatus.OK
    HTTP_201_CREATED = HTTPStatus.CREATED
    HTTP_202_ACCEPTED = HTTPStatus.ACCEPTED
    HTTP_204_NO_CONTENT = HTTPStatus.NO_CONTENT
    HTTP_400_BAD_REQUEST = HTTPStatus.BAD_REQUEST
    HTTP_401_UNAUTHORIZED = HTTPStatus.UNAUTHORIZED
    HTTP_403_FORBIDDEN = HTTPStatus.FORBIDDEN
    HTTP_404_NOT_FOUND = HTTPStatus.NOT_FOUND
    HTTP_500_INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Optional[str] = None) -> None:
        super().__init__(detail or "HTTPException")
        self.status_code = status_code
        self.detail = detail or ""


class Response:
    def __init__(self, content: Any, status_code: int = HTTPStatus.OK) -> None:
        self.content = content
        self.status_code = status_code


class JSONResponse(Response):
    pass


class BackgroundTasks:
    def __init__(self) -> None:
        self._tasks: List[Tuple[Callable[..., Any], tuple, dict]] = []

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._tasks.append((func, args, kwargs))

    async def run(self) -> None:
        for func, args, kwargs in self._tasks:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                await result


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class OAuth2PasswordBearer:
    def __init__(self, tokenUrl: str) -> None:
        self.tokenUrl = tokenUrl

    async def __call__(self) -> str:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token retrieval not implemented in stub")


class WebSocketDisconnect(Exception):
    pass


class WebSocket:
    def __init__(self) -> None:
        self._incoming: asyncio.Queue[Any] = asyncio.Queue()
        self._outgoing: asyncio.Queue[Any] = asyncio.Queue()
        self.client_state = "connecting"

    async def accept(self) -> None:
        self.client_state = "connected"

    async def close(self) -> None:
        self.client_state = "closed"
        await self._outgoing.put({"event": "close"})

    async def send_json(self, data: Any) -> None:
        if self.client_state != "connected":
            raise WebSocketDisconnect()
        await self._outgoing.put(data)

    async def receive_json(self) -> Any:
        if self.client_state != "connected":
            raise WebSocketDisconnect()
        return await self._incoming.get()

    # Helpers used in tests
    async def _queue_receive(self, data: Any) -> None:
        await self._incoming.put(data)

    async def _next_sent(self) -> Any:
        return await self._outgoing.get()


@dataclass
class _Route:
    method: str
    path: str
    endpoint: Callable[..., Any]


@dataclass
class _WebSocketRoute:
    path: str
    endpoint: Callable[[WebSocket], Awaitable[Any]]


class APIRouter:
    def __init__(self) -> None:
        self.routes: List[_Route] = []
        self.websocket_routes: List[_WebSocketRoute] = []

    def get(self, path: str, **_: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("GET", path)

    def post(self, path: str, **_: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("POST", path)

    def put(self, path: str, **_: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("PUT", path)

    def delete(self, path: str, **_: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("DELETE", path)

    def websocket(self, path: str) -> Callable[[Callable[[WebSocket], Awaitable[Any]]], Callable[[WebSocket], Awaitable[Any]]]:
        def decorator(func: Callable[[WebSocket], Awaitable[Any]]) -> Callable[[WebSocket], Awaitable[Any]]:
            self.websocket_routes.append(_WebSocketRoute(path=path, endpoint=func))
            return func

        return decorator

    def _add_route(self, method: str, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append(_Route(method=method.upper(), path=path, endpoint=func))
            return func

        return decorator


class FastAPI(APIRouter):
    def __init__(self, *, title: str = "FastAPI", version: str = "0.1.0") -> None:
        super().__init__()
        self.title = title
        self.version = version
        self.state = SimpleNamespace()
        self._event_handlers: Dict[str, List[Callable[[], Any]]] = {"startup": [], "shutdown": []}
        self._routers: List[Tuple[APIRouter, str]] = []

    def include_router(self, router: APIRouter, *, prefix: str = "") -> None:
        self._routers.append((router, prefix))

    def on_event(self, event_type: str) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
        def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
            self.add_event_handler(event_type, func)
            return func

        return decorator

    def add_event_handler(self, event_type: str, handler: Callable[[], Any]) -> None:
        self._event_handlers.setdefault(event_type, []).append(handler)

    async def trigger_event(self, event_type: str) -> None:
        for handler in self._event_handlers.get(event_type, []):
            result = handler()
            if asyncio.iscoroutine(result):
                await result

    async def dispatch(self, method: str, path: str, **kwargs: Any) -> Any:
        route, path_params = self._resolve_route(method.upper(), path)
        if not route:
            raise HTTPException(status.HTTP_404_NOT_FOUND.value, f"Route {method} {path} not found")
        return await _call_endpoint(route.endpoint, path_params, kwargs)

    async def dispatch_websocket(self, path: str, websocket: Optional[WebSocket] = None) -> WebSocket:
        ws_route = self._resolve_websocket(path)
        if not ws_route:
            raise HTTPException(status.HTTP_404_NOT_FOUND.value, f"WebSocket {path} not found")
        websocket = websocket or WebSocket()
        await websocket.accept()
        await ws_route.endpoint(websocket)
        return websocket

    def _resolve_route(self, method: str, path: str) -> Tuple[Optional[_Route], Dict[str, str]]:
        for collection, prefix in self._iter_routes():
            for route in collection.routes:
                candidate = self._join_path(prefix, route.path)
                match, params = _match_path(candidate, path)
                if match and route.method == method:
                    return route, params
        return None, {}

    def _resolve_websocket(self, path: str) -> Optional[_WebSocketRoute]:
        for collection, prefix in self._iter_routes():
            for route in collection.websocket_routes:
                candidate = self._join_path(prefix, route.path)
                match, _ = _match_path(candidate, path)
                if match:
                    return route
        return None

    def _iter_routes(self) -> List[Tuple[APIRouter, str]]:
        return [(self, "")] + self._routers

    @staticmethod
    def _join_path(prefix: str, path: str) -> str:
        return f"/{'/'.join(filter(None, (prefix.strip('/'), path.strip('/'))))}".replace("//", "/")


async def _call_endpoint(
    endpoint: Callable[..., Any], path_params: Dict[str, str], body_params: Dict[str, Any]
) -> Any:
    sig = inspect.signature(endpoint)
    kwargs: Dict[str, Any] = {}
    background: Optional[BackgroundTasks] = None
    for name, param in sig.parameters.items():
        if name in body_params:
            kwargs[name] = body_params[name]
        elif name in path_params:
            kwargs[name] = path_params[name]
        elif isinstance(param.default, Depends):
            dependency = param.default.dependency
            dep_sig = inspect.signature(dependency)
            if dep_sig.parameters:
                value = dependency(**body_params)
            else:
                value = dependency()
            if asyncio.iscoroutine(value):
                value = await value
            kwargs[name] = value
        elif param.annotation is BackgroundTasks:
            background = BackgroundTasks()
            kwargs[name] = background
        elif param.default is inspect.Parameter.empty:
            raise HTTPException(status.HTTP_400_BAD_REQUEST.value, f"Missing parameter '{name}'")
    result = endpoint(**kwargs)
    if asyncio.iscoroutine(result):
        result = await result
    if background:
        await background.run()
    return result


def _match_path(route_path: str, request_path: str) -> Tuple[bool, Dict[str, str]]:
    route_parts = [part for part in route_path.strip("/").split("/") if part]
    request_parts = [part for part in request_path.strip("/").split("/") if part]
    if len(route_parts) != len(request_parts):
        return False, {}
    params: Dict[str, str] = {}
    for route_part, request_part in zip(route_parts, request_parts):
        if route_part.startswith("{") and route_part.endswith("}"):
            params[route_part[1:-1]] = request_part
        elif route_part != request_part:
            return False, {}
    return True, params
