#!/usr/bin/env python3
"""Dangling-code audit — complements pyflakes.

pyflakes finds *unused* names; this finds *wired-but-incomplete* code that
pyflakes is blind to:

  * stub methods/functions whose body is only ``pass`` / ``...`` (+ docstring),
  * exception handlers that swallow errors silently (``except ...: pass``)
    without an explanatory comment.

Stubs fail the run (exit 1) — they are pure surface and should be gutted or
finished. Silently-swallowed excepts are reported as warnings so a human can
confirm each is intentional (add a one-line comment to clear it).

Usage:  python tools/audit.py [path ...]   (defaults to src/pacer_cli)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Dunder/protocol methods that are legitimately empty are not stubs.
_ALLOWED_EMPTY = {"__init__", "__enter__", "__exit__"}
# Decorator terminal names whose empty body is by design (click containers, etc.).
_CONTAINER_DECORATORS = {"group", "command"}


def _decorator_name(dec: ast.expr) -> str:
    """Terminal attribute/name of a decorator (handles @x.group() and @x.group)."""
    if isinstance(dec, ast.Call):
        dec = dec.func
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    return ""


def _is_container(node) -> bool:
    return any(_decorator_name(d) in _CONTAINER_DECORATORS for d in node.decorator_list)


def _is_stub_body(body: list[ast.stmt]) -> bool:
    stmts = list(body)
    if stmts and isinstance(stmts[0], ast.Expr) and isinstance(
        getattr(stmts[0], "value", None), ast.Constant
    ):
        stmts = stmts[1:]  # drop docstring
    if not stmts:
        return False
    return all(
        isinstance(s, ast.Pass)
        or (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant)
            and s.value.value is Ellipsis)
        for s in stmts
    )


def _audit_file(path: Path) -> tuple[list[str], list[str]]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    lines = src.splitlines()
    stubs: list[str] = []
    swallows: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.name not in _ALLOWED_EMPTY
                and not _is_container(node)
                and _is_stub_body(node.body)
            ):
                stubs.append(f"{path}:{node.lineno}: stub '{node.name}' (body is pass/...)")
        elif isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                # Cleared if an explanatory comment sits anywhere in the handler.
                span = lines[node.lineno - 1 : body[0].lineno]
                if not any("#" in ln for ln in span):
                    swallows.append(
                        f"{path}:{node.lineno}: silent 'except: pass' (add a comment if intentional)"
                    )
    return stubs, swallows


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [Path("src/pacer_cli")]
    files: list[Path] = []
    for t in targets:
        files.extend(sorted(t.rglob("*.py")) if t.is_dir() else [t])

    all_stubs: list[str] = []
    all_swallows: list[str] = []
    for f in files:
        stubs, swallows = _audit_file(f)
        all_stubs.extend(stubs)
        all_swallows.extend(swallows)

    for w in all_swallows:
        print(f"WARN  {w}")
    for s in all_stubs:
        print(f"ERROR {s}")

    if all_stubs:
        print(f"\n{len(all_stubs)} stub(s) found — gut or finish them.")
        return 1
    print(f"audit clean: {len(files)} files, {len(all_swallows)} swallowed-except warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
