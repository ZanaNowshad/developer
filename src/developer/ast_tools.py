"""Utilities for analysing and transforming Python source code using ASTs."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List


@dataclass
class FunctionSignature:
    name: str
    arguments: List[str]
    lineno: int


def extract_function_signatures(source: str) -> List[FunctionSignature]:
    tree = ast.parse(source)
    signatures: List[FunctionSignature] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            signatures.append(FunctionSignature(name=node.name, arguments=args, lineno=node.lineno))
    return signatures


def rename_function(source: str, old: str, new: str) -> str:
    tree = ast.parse(source)

    class Renamer(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
            if node.name == old:
                node.name = new
            self.generic_visit(node)
            return node

        def visit_Call(self, node: ast.Call):  # type: ignore[override]
            if isinstance(node.func, ast.Name) and node.func.id == old:
                node.func.id = new
            return self.generic_visit(node)

    tree = Renamer().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def list_imports(source: str) -> List[str]:
    tree = ast.parse(source)
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(name.name for name in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
    return sorted(set(imports))


__all__ = ["FunctionSignature", "extract_function_signatures", "list_imports", "rename_function"]
