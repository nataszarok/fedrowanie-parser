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


def test_pipeline_public_functions_precede_private_helpers():
    """Pipeline public API must be visible before implementation helpers."""
    path = PKG / "pipeline.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    first_private = next((i for i, name in enumerate(functions) if name.startswith("_")), len(functions))
    assert all(not name.startswith("_") for name in functions[:first_private])
    assert all(name.startswith("_") for name in functions[first_private:])
