"""Keep the VD-001 coordinator isolated from implementations and side effects."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEANROOM = ROOT / "src" / "adls" / "cleanroom"
FORBIDDEN_MODULES = {
    "http",
    "httpx",
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "adls.alfred",
    "adls.calendarutil",
    "adls.checker",
    "adls.config",
    "adls.contracts",
    "adls.engine",
    "adls.inputs",
    "adls.registry",
    "adls.reporting",
    "adls.validation",
}


def _cleanroom_files() -> list[Path]:
    return sorted(CLEANROOM.rglob("*.py"))


def test_cleanroom_package_has_no_implementation_or_network_imports() -> None:
    files = _cleanroom_files()
    assert files, "Phase 3A clean-room package is missing"
    offenders: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
                modules = (node.module,)
            for module in modules:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in FORBIDDEN_MODULES
                ):
                    offenders.append(f"{path.name}:{node.lineno}: {module}")
    assert not offenders, f"clean-room boundary imports: {offenders}"


def test_cleanroom_package_has_no_environment_network_or_wall_clock_calls() -> None:
    offenders: list[str] = []
    for path in _cleanroom_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {
                "environ",
                "getenv",
                "now",
                "today",
                "utcnow",
                "urlopen",
            }:
                offenders.append(f"{path.name}:{node.lineno}: {node.attr}")
    assert not offenders, f"clean-room side-effect surfaces: {offenders}"


def test_packet_builder_cannot_accept_or_copy_a_reference_sequence() -> None:
    packet_path = CLEANROOM / "packet.py"
    tree = ast.parse(packet_path.read_text(encoding="utf-8"), filename=packet_path.name)
    prepare = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "prepare_packet"
    )
    argument_names = {
        argument.arg
        for argument in (
            *prepare.args.posonlyargs,
            *prepare.args.args,
            *prepare.args.kwonlyargs,
        )
    }
    assert not {"reference", "reference_path", "expected_output"} & argument_names
    source = packet_path.read_text(encoding="utf-8")
    assert "validation_frozen_equivalent" not in source
    assert "validation_results" not in source
