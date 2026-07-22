"""Deterministic, local-only weekly research reporting."""

from .generator import run_weekly_report
from .models import ReportRunResult

__all__ = ["ReportRunResult", "run_weekly_report"]
