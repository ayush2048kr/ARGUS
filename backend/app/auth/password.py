import bcrypt


# =========================
# PASSWORD HASHING
# =========================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    """

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "Password cannot be longer than 72 bytes"
        )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


# =========================
# PASSWORD VERIFICATION
# =========================

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify a plain password against a bcrypt hash.
    """

    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")

    return bcrypt.checkpw(
        password_bytes,
        hashed_bytes
    )