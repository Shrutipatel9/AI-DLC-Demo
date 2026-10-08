#!/usr/bin/env python3
"""Fail when a client requirement ID has no test mapping (US1.13, AC1.13.1).

Reads every ``FR-``, ``AUTH-``, ``BR-`` and ``FE-`` ID from ``client_requirements.md`` and
checks ``docs/requirement-test-map.json``: each ID must list at least one test file that
exists, or be ``N/A`` / ``Deferred`` with a reason. Standard library only.

Usage: python scripts/check-requirement-map.py [repo-root]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ID_PATTERN = re.compile(r"\b(?:FR|AUTH|BR|FE)-\d{3}\b")
NON_TEST_STATUSES = {"N/A", "Deferred"}


def required_ids(root: Path) -> set[str]:
    """Every client ID mentioned in the requirements document."""
    text = (root / "client_requirements.md").read_text(encoding="utf-8")
    return set(ID_PATTERN.findall(text))


def check(root: Path, map_path: Path | None = None) -> list[str]:
    """Return the problems found (empty when the map is complete)."""
    path = map_path or root / "docs" / "requirement-test-map.json"
    entries: dict[str, dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))[
        "requirements"
    ]
    problems: list[str] = []
    for req_id in sorted(required_ids(root)):
        entry = entries.get(req_id)
        if entry is None:
            problems.append(f"{req_id}: not in the requirement-to-test map")
            continue
        status = entry.get("status")
        if status in NON_TEST_STATUSES:
            if not str(entry.get("reason", "")).strip():
                problems.append(f"{req_id}: {status} needs a reason")
            continue
        tests = entry.get("tests")
        if not isinstance(tests, list) or not tests:
            problems.append(f"{req_id}: no test listed")
            continue
        problems.extend(
            f"{req_id}: test file not found: {test}"
            for test in tests
            if not (root / str(test)).is_file()
        )
    problems.extend(
        f"{req_id}: in the map but not in client_requirements.md"
        for req_id in sorted(set(entries) - required_ids(root))
    )
    return problems


def main(argv: list[str]) -> int:
    """Command-line entry point; exit 1 on any problem."""
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems = check(root)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"requirement map OK ({len(required_ids(root))} IDs)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
