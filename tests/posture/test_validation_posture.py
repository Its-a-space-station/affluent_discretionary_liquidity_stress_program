"""Keep the Slice 6 harness local, cache-only, and assumption-scoped."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "src" / "adls" / "validation"
FORBIDDEN_MODULES = {
    "http",
    "httpx",
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "adls.alfred.client",
}


def _validation_files() -> list[Path]:
    return sorted(VALIDATION.rglob("*.py"))


def test_validation_package_exists_and_has_no_network_surface() -> None:
    files = _validation_files()
    assert files, "Slice 6 validation package is missing"
    offenders: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            for module in modules:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in FORBIDDEN_MODULES
                ):
                    offenders.append(f"{path.name}:{node.lineno}: {module}")
    assert not offenders, f"validation network imports: {offenders}"


def test_historical_final_assumption_is_confined_to_engine_and_validation_source() -> None:
    source_root = ROOT / "src" / "adls"
    offenders = []
    allowed = {
        source_root / "engine" / "core.py",
        source_root / "validation" / "reconstruction.py",
    }
    for path in source_root.rglob("*.py"):
        has_assumption = "HISTORICAL_FINAL_ASSUMPTION" in path.read_text(encoding="utf-8")
        if has_assumption and path not in allowed:
            offenders.append(path)
    assert not offenders, f"historical-final assumption escaped its boundary: {offenders}"


def test_validation_payload_has_no_wall_clock_calls() -> None:
    offenders: list[str] = []
    for path in _validation_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"now", "today", "utcnow"}:
                offenders.append(f"{path.name}:{node.lineno}: {node.attr}")
    assert not offenders, f"wall-clock data in deterministic validation payload: {offenders}"
