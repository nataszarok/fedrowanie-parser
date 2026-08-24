"""SQL source-format conventions."""
from __future__ import annotations

import ast
import re
from pathlib import Path

PKG = Path(__file__).parents[1] / "src" / "fedrowanie_parser"
SQL_RE = re.compile(
    r"\\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|PRAGMA)\\b", re.I
)


def test_multiline_sql_uses_triple_quotes():
    """Multiline SQL literals must be represented by triple-quoted source strings."""
    violations = []
    triple_double = chr(34) * 3
    triple_single = chr(39) * 3

    for path in PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "\\n" in node.value
                and SQL_RE.search(node.value)
            ):
                source = (ast.get_source_segment(text, node) or "").lstrip()
                if not source.startswith((triple_double, triple_single)):
                    violations.append((str(path.relative_to(PKG)), node.lineno))

    assert violations == []
