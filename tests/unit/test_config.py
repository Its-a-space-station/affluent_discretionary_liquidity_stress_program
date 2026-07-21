from __future__ import annotations

import pytest

from adls.config import Config


def test_validate_raises_without_key_and_never_echoes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    cfg = Config()
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_for_fetch()
    assert "FRED_API_KEY" in str(exc_info.value)


def test_key_value_never_in_repr_or_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = "fake-key-value-123456789"
    monkeypatch.setenv("FRED_API_KEY", fake)
    cfg = Config()
    cfg.validate_for_fetch()  # passes
    assert fake not in repr(cfg)
    assert fake not in str(cfg)
