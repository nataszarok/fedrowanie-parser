"""Static code-quality invariants for the parser package."""
from __future__ import annotations

import ast
import builtins
import re
import symtable
from pathlib import Path

PKG = Path(__file__).parents[1] / "src" / "fedrowanie_parser"


def test_module_api_and_style_invariants():
    violations = []

    for path in PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        rel = str(path.relative_to(PKG))

        if ast.get_docstring(tree) is None:
            violations.append((rel, "missing module docstring"))

        seen_private = False
        public_functions = []
        has_all = False

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_"):
                    seen_private = True
                else:
                    public_functions.append(node.name)
                    if seen_private:
                        violations.append(
                            (rel, f"public function after private helper: {node.name}")
                        )
                    if ast.get_docstring(node) is None:
                        violations.append(
                            (rel, f"missing public docstring: {node.name}")
                        )

            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in targets
                ):
                    has_all = True
                if rel != "constants.py":
                    for target in targets:
                        if isinstance(target, ast.Name) and re.fullmatch(
                            r"[A-Z][A-Z0-9_]*", target.id
                        ):
                            violations.append(
                                (rel, f"constant outside constants.py: {target.id}")
                            )

        if public_functions and not has_all:
            violations.append((rel, "public module missing __all__"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        allowed = rel == "pipeline.py" and node.module in {
                            "processing.api",
                            "parsing.tables",
                            "parsing.layouts",
                            "parsing.plain_text",
                            "enrichment.api",
                            "special_cases.api",
                        }
                        if not allowed:
                            violations.append(
                                (rel, f"unexpected wildcard import: {node.module}")
                            )
                    if alias.name.startswith("_") and not alias.name.startswith("__"):
                        violations.append(
                            (rel, f"private cross-module import: {alias.name}")
                        )

    assert violations == []


def test_no_undefined_global_dependencies():
    violations = []

    for path in PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        table = symtable.symtable(text, str(path), "exec")

        defined = set()
        for name in table.get_identifiers():
            symbol = table.lookup(name)
            if symbol.is_imported() or symbol.is_assigned() or symbol.is_namespace():
                defined.add(name)

        def walk(scope):
            for child in scope.get_children():
                for name in child.get_identifiers():
                    symbol = child.lookup(name)
                    if (
                        symbol.is_referenced()
                        and symbol.is_global()
                        and name not in defined
                        and name not in dir(builtins)
                    ):
                        violations.append(
                            (str(path.relative_to(PKG)), child.get_name(), name)
                        )
                walk(child)

        walk(table)

    assert violations == []
