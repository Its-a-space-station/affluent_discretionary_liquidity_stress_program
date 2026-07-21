"""Structural posture tests (credential hygiene + import discipline +
forbidden vocabulary). Pattern: Kalshi tests/test_shadow_posture.py.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "adls"

ENV_TOKENS = re.compile(r"os\.environ|getenv|dotenv|load_dotenv")
# label_policy: action words may not appear as identifiers/labels.
# "sort_order" (FRED API param) and prose negations are exempt by design;
# scan for word-bounded tokens with the known-safe exemption applied.
FORBIDDEN = re.compile(
    r"\b(buy|sell|trade)\b|(?<!sort_)\border\b(?!\s+by)", re.IGNORECASE
)  # exemptions: FRED's sort_order param, SQL ORDER BY


def _py_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_env_access_only_in_config() -> None:
    offenders = [
        p for p in _py_files()
        if p.name != "config.py" and ENV_TOKENS.search(p.read_text())
    ]
    assert not offenders, f"env access outside config.py: {offenders}"


def test_requests_imported_only_under_alfred() -> None:
    offenders = []
    for p in _py_files():
        if "alfred" in p.parts:
            continue
        text = p.read_text()
        if re.search(r"^\s*import requests|^\s*from requests", text, re.MULTILINE):
            offenders.append(p)
    assert not offenders, f"requests imported outside alfred/: {offenders}"


def test_forbidden_vocabulary_absent() -> None:
    offenders: list[str] = []
    for p in _py_files():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            stripped = line.strip()
            # prose negations live in comments/docstrings referencing safety policy
            if stripped.startswith("#") or "safety" in stripped.lower():
                continue
            if FORBIDDEN.search(line):
                offenders.append(f"{p.name}:{i}: {stripped}")
    assert not offenders, f"forbidden vocabulary: {offenders}"


def test_no_scheduler_artifacts() -> None:
    repo = SRC.parents[1]
    plists = list(repo.rglob("*.plist"))
    assert not plists, f"scheduler artifacts are gated: {plists}"
