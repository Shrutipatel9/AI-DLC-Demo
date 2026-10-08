"""The requirement-to-test map check (US1.13, AC1.13.1): CI fails on an unmapped ID."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_requirement_map", ROOT / "scripts" / "check-requirement-map.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _copy_repo_inputs(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    shutil.copy(ROOT / "client_requirements.md", tmp_path / "client_requirements.md")
    shutil.copy(ROOT / "docs" / "requirement-test-map.json", tmp_path / "docs")
    return tmp_path


def test_every_client_id_is_mapped_to_an_existing_test_or_has_a_reason() -> None:
    assert checker.check(ROOT) == []


def test_all_57_client_ids_are_present_in_the_map() -> None:
    ids = checker.required_ids(ROOT)
    assert len(ids) == 57
    assert {i.split("-")[0] for i in ids} == {"FR", "AUTH", "BR", "FE"}


def test_an_unmapped_id_fails_the_check(tmp_path: Path) -> None:
    root = _copy_repo_inputs(tmp_path)
    path = root / "docs" / "requirement-test-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["requirements"]["FR-001"]
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any(p.startswith("FR-001:") for p in checker.check(root))


def test_a_missing_test_file_and_a_reasonless_deferral_fail_the_check(tmp_path: Path) -> None:
    root = _copy_repo_inputs(tmp_path)
    path = root / "docs" / "requirement-test-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["requirements"]["FR-002"] = {"status": "mapped", "tests": ["backend/tests/nope.py"]}
    data["requirements"]["FR-019"] = {"status": "Deferred", "reason": " "}
    path.write_text(json.dumps(data), encoding="utf-8")

    problems = checker.check(root)

    assert any("FR-002: test file not found" in p for p in problems)
    assert any("FR-019: Deferred needs a reason" in p for p in problems)


def test_main_exits_non_zero_when_the_map_is_incomplete(tmp_path: Path) -> None:
    root = _copy_repo_inputs(tmp_path)
    path = root / "docs" / "requirement-test-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["requirements"]["BR-001"]
    path.write_text(json.dumps(data), encoding="utf-8")

    assert checker.main(["check", str(root)]) == 1
    assert checker.main(["check", str(ROOT)]) == 0


@pytest.mark.parametrize("bad", ["FR-1", "AUTH-17"])
def test_ids_must_have_three_digits_to_count(bad: str) -> None:
    assert checker.ID_PATTERN.findall(f"see {bad} here") == []
