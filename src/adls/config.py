"""Configuration. The ONLY module in adls that reads environment variables.

Credential hygiene (CLAUDE.md section 3.5, Safety Boundaries): the FRED key is
read from the environment, held in a repr-suppressed field, and never logged,
echoed, or embedded in errors. validate_for_fetch() checks presence without
reading the value into any message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

FRED_API_KEY_ENV = "FRED_API_KEY"

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    fred_api_key: str = field(
        default_factory=lambda: os.getenv(FRED_API_KEY_ENV, ""), repr=False
    )
    data_dir: Path = REPO_ROOT / "data"
    db_path: Path = REPO_ROOT / "data" / "adls.sqlite"
    canonical_dir: Path = REPO_ROOT / "canonical"
    archive_dir: Path = REPO_ROOT / "data_archive"
    outputs_dir: Path = REPO_ROOT / "outputs"

    def validate_for_fetch(self) -> None:
        """Raise if fetch prerequisites are missing. Never echoes values."""
        if not self.fred_api_key:
            raise ValueError(
                f"{FRED_API_KEY_ENV} is not set. Export it in your shell or a "
                "git-ignored .env (see .env.example). Values are never logged."
            )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
