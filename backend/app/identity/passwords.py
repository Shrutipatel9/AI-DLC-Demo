"""Password hashing and the password rule (BR1.2, BR1.5, BR3.1; NFR2.2-NFR2.4).

- Argon2id with OWASP parameters (19 MiB, t=2, p=1, 16-byte salt, 32-byte hash), all
  configurable. ``verify_and_maybe_rehash`` returns a new hash when the parameters
  change, and the login service stores it.
- ``verify_dummy`` runs one full Argon2 verification against a module-made dummy hash,
  so a login for a missing or unverified account costs the same as a real one.
- The rule: 8-128 characters, at least one letter and one digit, not on the bundled
  list of the 10,000 most common passwords (SecLists ``10k-most-common.txt``, MIT
  licence), compared case-insensitively.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

COMMON_PASSWORDS_FILE = Path(__file__).resolve().parent / "data" / "common-passwords.txt"
MIN_LENGTH = 8
MAX_LENGTH = 128


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    """The bundled common-password list, lower-cased, loaded once."""
    lines = COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip())


class PasswordRule(StrEnum):
    """Which part of the password rule failed (shown next to the field)."""

    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    NEEDS_LETTER = "NEEDS_LETTER"
    NEEDS_DIGIT = "NEEDS_DIGIT"
    TOO_COMMON = "TOO_COMMON"


class PasswordPolicy:
    """The password rule (BR1.2)."""

    def violations(self, password: str) -> list[PasswordRule]:
        """Return every rule the password breaks (empty when it is acceptable)."""
        problems: list[PasswordRule] = []
        if len(password) < MIN_LENGTH:
            problems.append(PasswordRule.TOO_SHORT)
        if len(password) > MAX_LENGTH:
            problems.append(PasswordRule.TOO_LONG)
        if not any(char.isalpha() for char in password):
            problems.append(PasswordRule.NEEDS_LETTER)
        if not any(char.isdigit() for char in password):
            problems.append(PasswordRule.NEEDS_DIGIT)
        if password.lower() in common_passwords():
            problems.append(PasswordRule.TOO_COMMON)
        return problems

    def is_acceptable(self, password: str) -> bool:
        """True when no rule is broken."""
        return not self.violations(password)


@dataclass(frozen=True)
class Argon2Params:
    """Argon2id cost parameters (from settings)."""

    memory_kib: int = 19_456
    time_cost: int = 2
    parallelism: int = 1


class PasswordHasher:
    """Argon2id hashing with re-hash on parameter change and a dummy-hash path.

    Args:
        params: Cost parameters.
    """

    def __init__(self, params: Argon2Params | None = None) -> None:
        chosen = params or Argon2Params()
        self._hasher = Argon2Hasher(
            time_cost=chosen.time_cost,
            memory_cost=chosen.memory_kib,
            parallelism=chosen.parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        """Return a salted Argon2id hash (never store the password itself)."""
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """True when ``password`` matches ``password_hash``."""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verify_and_maybe_rehash(self, password_hash: str, password: str) -> tuple[bool, str | None]:
        """Verify, and return a fresh hash when the stored one uses old parameters."""
        if not self.verify(password_hash, password):
            return False, None
        if self._hasher.check_needs_rehash(password_hash):
            return True, self._hasher.hash(password)
        return True, None

    def verify_dummy(self, password: str) -> None:
        """Spend one Argon2 verification so missing accounts take the same time."""
        self.verify(self._dummy_hash, password)
