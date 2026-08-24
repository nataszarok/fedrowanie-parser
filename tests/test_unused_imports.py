"""Static guard against accidental unused explicit imports."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

PKG = Path(__file__).parents[1] / "src" / "fedrowanie_parser"


def _exports(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            try:
                result.update(ast.literal_eval(node.value))
            except (ValueError, TypeError):
                pass
    return result


def test_explicit_imports_are_used_or_reexported():
    """Explicit imports must be referenced locally or intentionally re-exported."""
    violations = []

    for path in PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loads = Counter(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        exports = _exports(tree)

        for node in tree.body:
            if isinstance(node, ast.Import):
                aliases = [(a.asname or a.name.split(".")[0], a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                aliases = [
                    (a.asname or a.name, a.name)
                    for a in node.names
                    if a.name != "*"
                ]
            else:
                continue

            for bound_name, original_name in aliases:
                if loads[bound_name] == 0 and bound_name not in exports:
                    violations.append(
                        (str(path.relative_to(PKG)), node.lineno, original_name)
                    )

    assert violations == []
