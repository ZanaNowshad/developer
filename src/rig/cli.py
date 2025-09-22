"""Simplified CLI for interacting with Developer MCP tools."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict

from developer.server import Developer


async def _run_chat() -> None:
    developer = Developer()
    await developer.startup()
    print("Type 'list' to view available tools, 'tool <name> <json>' to invoke, or ':q' to quit.")
    while True:
        try:
            raw = input("rig> ")
        except EOFError:
            break
        command = raw.strip()
        if not command:
            continue
        if command in {":q", "quit", "exit"}:
            break
        if command == "list":
            tools = await developer.list_tools()
            print(json.dumps(tools, indent=2))
            continue
        if command.startswith("tool "):
            _, _, remainder = command.partition(" ")
            name, _, args_str = remainder.partition(" ")
            args: Dict[str, Any]
            if args_str.strip():
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError as exc:
                    print(f"Invalid JSON arguments: {exc}")
                    continue
            else:
                args = {}
            result = await developer.call_tool(name, args)
            print(json.dumps(result.to_dict(), indent=2))
            continue
        print("Unknown command")
    await developer.shutdown()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rig", description="Interactive shell for Developer tools")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("chat", help="Start the interactive chat shell")
    args = parser.parse_args(argv)
    command = args.command or "chat"
    if command == "chat":
        asyncio.run(_run_chat())


if __name__ == "__main__":  # pragma: no cover - CLI execution
    main()
