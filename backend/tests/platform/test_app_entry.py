"""`uvicorn app.main:app` entry point (built lazily from the settings on first access)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

import app.main as main


def test_module_app_is_built_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[FastAPI] = []

    def fake_create_app() -> FastAPI:
        built.append(FastAPI())
        return built[-1]

    monkeypatch.setattr(main, "create_app", fake_create_app)
    monkeypatch.delitem(vars(main), "app", raising=False)
    first = main.app
    assert main.app is first
    assert built == [first]
    monkeypatch.delitem(vars(main), "app")


def test_unknown_attribute_still_raises() -> None:
    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        _ = main.nope  # type: ignore[attr-defined]
