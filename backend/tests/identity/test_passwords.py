"""Password rule and Argon2id hashing (BR1.2, BR1.5, BR3.1; NFR2.2-NFR2.4; AC3.1.4, AC3.1.5)."""

from __future__ import annotations

import pytest

from app.identity.passwords import (
    Argon2Params,
    PasswordHasher,
    PasswordPolicy,
    PasswordRule,
    common_passwords,
)

policy = PasswordPolicy()


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Abcdef1", [PasswordRule.TOO_SHORT]),  # 7 characters
        ("Kq7wZp2m", []),  # 8 characters
        ("a1" * 64, []),  # 128 characters
        ("a1" * 64 + "x", [PasswordRule.TOO_LONG]),  # 129 characters
        ("98273645018", [PasswordRule.NEEDS_LETTER]),
        ("Abcdefg1", [PasswordRule.TOO_COMMON]),
        ("Sunrisesunrise", [PasswordRule.NEEDS_DIGIT]),
        ("PASSWORD1", [PasswordRule.TOO_COMMON]),  # case-insensitive
        ("Sunrise2026x", []),
    ],
)
def test_password_rule_table(password: str, expected: list[PasswordRule]) -> None:
    assert policy.violations(password) == expected
    assert policy.is_acceptable(password) is (not expected)


def test_common_list_has_at_least_ten_thousand_entries() -> None:
    assert len(common_passwords()) >= 9_900  # 10k list, de-duplicated case-insensitively
    assert "password1" in common_passwords()


@pytest.fixture(scope="module")
def hasher() -> PasswordHasher:
    return PasswordHasher()


def test_hash_uses_argon2id_owasp_parameters(hasher: PasswordHasher) -> None:
    hashed = hasher.hash("Sunrise2026x")
    assert hashed.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert "Sunrise2026x" not in hashed
    assert hashed != hasher.hash("Sunrise2026x")  # salted


def test_verify_accepts_right_and_rejects_wrong(hasher: PasswordHasher) -> None:
    hashed = hasher.hash("Sunrise2026x")
    assert hasher.verify(hashed, "Sunrise2026x")
    assert not hasher.verify(hashed, "Sunrise2026y")
    assert not hasher.verify("not-a-hash", "Sunrise2026x")


def test_rehash_when_parameters_change(hasher: PasswordHasher) -> None:
    old = PasswordHasher(Argon2Params(memory_kib=8_192, time_cost=1, parallelism=1))
    stored = old.hash("Sunrise2026x")
    ok, new_hash = hasher.verify_and_maybe_rehash(stored, "Sunrise2026x")
    assert ok
    assert new_hash is not None
    assert new_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    current = hasher.hash("Sunrise2026x")
    assert hasher.verify_and_maybe_rehash(current, "Sunrise2026x") == (True, None)
    assert hasher.verify_and_maybe_rehash(current, "wrong") == (False, None)


def test_dummy_verification_does_real_work(
    hasher: PasswordHasher, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = hasher.verify

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(hasher, "verify", spy)
    hasher.verify_dummy("anything")
    assert len(calls) == 1
    assert calls[0].startswith("$argon2id$")
