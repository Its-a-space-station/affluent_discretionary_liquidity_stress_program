"""Enforce the Slice 5 maker/checker code boundary."""

from __future__ import annotations

import ast
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[2] / "src" / "adls" / "checker"
ALLOWED_DIRECT_IMPORTS = {
    "csv",
    "hashlib",
    "json",
    "math",
    "sqlite3",
}
ALLOWED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "calendar": {"monthrange"},
    "collections.abc": {"Sequence"},
    "dataclasses": {"dataclass"},
    "datetime": {"UTC", "date", "datetime", "timedelta"},
    "decimal": {"ROUND_HALF_EVEN", "Decimal", "DecimalException", "InvalidOperation"},
    "pathlib": {"Path", "PurePosixPath"},
    "typing": {"Literal", "TypeAlias", "cast"},
    "adls.config": {"Config"},
}
FORBIDDEN_DYNAMIC_CALLS = {"__import__", "compile", "eval", "exec"}
FORBIDDEN_DYNAMIC_REFERENCES = {
    *FORBIDDEN_DYNAMIC_CALLS,
    "__builtins__",
    "__loader__",
    "__package__",
    "__spec__",
    "globals",
    "locals",
    "vars",
}


def _checker_files() -> list[Path]:
    return sorted(CHECKER.rglob("*.py"))


def test_checker_package_exists() -> None:
    assert _checker_files(), "Slice 5 checker package is missing"


def _posture_offenders(source: str, filename: str) -> list[str]:
    offenders: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_DIRECT_IMPORTS:
                    offenders.append(f"{filename}:{node.lineno}: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1:
                continue
            if node.level > 0:
                allowed_parent = (
                    node.level == 2
                    and node.module == "config"
                    and {alias.name for alias in node.names} <= {"Config"}
                )
                if not allowed_parent:
                    offenders.append(
                        f"{filename}:{node.lineno}: parent-relative {node.module or ''}"
                    )
                continue
            module = node.module or ""
            if module == "adls.checker" or module.startswith("adls.checker."):
                continue
            allowed_symbols = ALLOWED_FROM_IMPORTS.get(module, set())
            imported_symbols = {alias.name for alias in node.names}
            if not imported_symbols <= allowed_symbols:
                offenders.append(
                    f"{filename}:{node.lineno}: {module} imports "
                    f"{','.join(sorted(imported_symbols - allowed_symbols))}"
                )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_DYNAMIC_CALLS
        ):
            offenders.append(f"{filename}:{node.lineno}: dynamic {node.func.id}")
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in FORBIDDEN_DYNAMIC_REFERENCES
        ):
            offenders.append(f"{filename}:{node.lineno}: dynamic reference {node.id}")
        elif isinstance(node, ast.Constant) and node.value in FORBIDDEN_DYNAMIC_CALLS:
            offenders.append(f"{filename}:{node.lineno}: dynamic name {node.value}")
        elif isinstance(node, ast.Attribute) and node.attr in {
            "exec_module",
            "load_module",
            "module_from_spec",
        }:
            offenders.append(f"{filename}:{node.lineno}: dynamic attribute {node.attr}")
    return offenders


def test_checker_imports_no_maker_or_input_implementation() -> None:
    offenders = [
        offender
        for path in _checker_files()
        for offender in _posture_offenders(path.read_text(encoding="utf-8"), path.name)
    ]

    assert not offenders, f"checker imports implementation-owned modules: {offenders}"


def test_posture_guard_rejects_dynamic_imports_and_environment_aliases() -> None:
    bypasses = (
        'import importlib as loader\nloader.import_module("adls.engine")',
        'from importlib import import_module as load\nload("adls.inputs")',
        '__import__("adls.alfred")',
        'load = __import__\nload("adls.engine")',
        'getattr(__builtins__, "__import__")("adls.inputs")',
        'from pathlib import os\nos.getenv("SECRET")',
        '__loader__.load_module("adls.engine")',
        'import os as operating_system\noperating_system.getenv("SECRET")',
        'from os import environ as environment\nvalue = environment.get("SECRET")',
    )
    for index, source in enumerate(bypasses, 1):
        assert _posture_offenders(source, f"bypass-{index}.py"), source
