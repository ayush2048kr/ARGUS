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


def test_password_over_72_bytes_is_rejected():
    password = "a" * 73

    with pytest.raises(ValueError):
        hash_password(password)
