
import pytest

from app.auth.password import hash_password, verify_password


def test_password_hash_and_verify():
    password = "SecurePassword123!"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password) is True


def test_wrong_password_fails():
    password = "SecurePassword123!"
    wrong_password = "WrongPassword123!"

    hashed_password = hash_password(password)

    assert verify_password(wrong_password, hashed_password) is False


def test_password_exactly_72_ascii_bytes_is_accepted():
    password = "a" * 72

    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_password_over_72_ascii_bytes_is_rejected():
    password = "a" * 73

    with pytest.raises(ValueError):
        hash_password(password)


def test_password_exactly_72_unicode_bytes_is_accepted():
    # Each euro symbol occupies 3 UTF-8 bytes.
    password = "€" * 24

    assert len(password.encode("utf-8")) == 72

    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_password_over_72_unicode_bytes_is_rejected():
    # 25 euro symbols occupy 75 UTF-8 bytes.
    password = "€" * 25

    assert len(password.encode("utf-8")) == 75

    with pytest.raises(ValueError):
        hash_password(password)


def test_oversized_password_fails_verification():
    stored_password = hash_password("SecurePassword123!")
    oversized_password = "a" * 73

    assert verify_password(oversized_password, stored_password) is False


def test_malformed_bcrypt_hash_returns_false():
    assert verify_password(
        "SecurePassword123!",
        "not-a-valid-bcrypt-hash",
    ) is False
