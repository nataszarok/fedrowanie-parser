"""Repository-boundary invariants."""
from pathlib import Path

PKG = Path(__file__).parents[1] / "src" / "fedrowanie_parser"


def test_pipeline_contains_no_sql_or_sqlite_schema_access():
    """Pipeline must orchestrate domain objects, not query the source database."""
    text = (PKG / "pipeline.py").read_text(encoding="utf-8").upper()
    forbidden = ("SELECT ", "INSERT INTO ", "CREATE TABLE ", "DROP TABLE ", "SQLITE3")
    assert not any(token in text for token in forbidden)
