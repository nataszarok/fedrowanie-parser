"""Architecture invariants for module boundaries."""
from __future__ import annotations
import ast
from pathlib import Path

PKG = Path(__file__).parents[1] / "src" / "fedrowanie_parser"

def test_no_cross_module_private_imports():
    violations = []
    for path in PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name.startswith("_") and not alias.name.startswith("__"):
                        violations.append((str(path.relative_to(PKG)), node.module, alias.name))
    assert violations == []
