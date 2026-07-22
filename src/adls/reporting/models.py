"""Immutable result contract for a weekly report run."""

from __future__ import annotations

from dataclasses import dataclass

from adls.contracts import ValidationResult


@dataclass(frozen=True)
class ReportRunResult:
    assembly_bytes: bytes
    artifact_bytes: bytes
    markdown: str
    validation: ValidationResult
