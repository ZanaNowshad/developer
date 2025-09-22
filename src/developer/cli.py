"""Command line interface for the Developer MCP platform."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .app import build_app
from .config import AppSettings
from .mcp_server import McpServer
from .server import Developer


async def _run_server() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    developer = Developer()
    server = McpServer(developer)
    await server.serve_stdio()


async def _print_toolbox() -> None:
    schema = await Developer.get_tools_schema_as_json()
    print(schema)


async def _show_plugins() -> None:
    developer = Developer()
    await developer.startup()
    try:
        for record in developer.plugin_manager.describe():
            status = "loaded" if record.loaded else f"error: {record.error}"
            print(f"- {record.name}: {status}")
            if record.registered_tools:
                print(f"  tools: {', '.join(record.registered_tools)}")
    finally:
        await developer.shutdown()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="developer", description="A developer MCP server")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("toolbox", help="Output the tools JSON schema")
    subparsers.add_parser("plugins", help="List plugin load status")
    api_parser = subparsers.add_parser("api", help="Run the FastAPI server (requires uvicorn)")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument("--reload", action="store_true", help="Enable autoreload when supported")
    args = parser.parse_args(argv)
    if args.command == "toolbox":
        asyncio.run(_print_toolbox())
        return
    if args.command == "plugins":
        asyncio.run(_show_plugins())
        return
    if args.command == "api":
        settings = AppSettings()
        app = build_app(settings=settings)
        try:
            import uvicorn
        except ModuleNotFoundError:  # pragma: no cover - optional dependency
            print("uvicorn is not installed; cannot start the API server", file=sys.stderr)
            return
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
        return
    asyncio.run(_run_server())


if __name__ == "__main__":  # pragma: no cover - CLI execution
    main()
