from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_MODULES = {
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "sqlite3",
    "sqlalchemy",
    "boto3",
    "botocore",
    "PIL",
    "httpx",
    "os",
    "pathlib",
}


def test_domain_layer_has_no_framework_db_or_io_imports() -> None:
    domain_dir = Path(__file__).resolve().parents[1] / "app" / "domain"
    py_files = sorted(domain_dir.glob("*.py"))
    assert len(py_files) >= 3

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".", 1)[0]
                    assert (
                        top_level not in FORBIDDEN_MODULES
                    ), f"Forbidden import '{alias.name}' in {py_file.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level = node.module.split(".", 1)[0]
                assert (
                    top_level not in FORBIDDEN_MODULES
                ), f"Forbidden import-from '{node.module}' in {py_file.name}"
