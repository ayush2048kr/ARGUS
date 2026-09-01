from datetime import datetime, timedelta, timezone
import os
from jose import jwt, JWTError


# =========================
# JWT CONFIGURATION
# =========================

SECRET_KEY = os.getenv(
    "ARGUS_SECRET_KEY",
    "ARGUS_DEVELOPMENT_SECRET_KEY_CHANGE_LATER"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


# =========================
# CREATE JWT TOKEN
# =========================

def create_access_token(user_id: str, role: str) -> str:
    """
    Create a JWT access token for an ARGUS user.
    """

    expire_time = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire_time
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# =========================
# DECODE JWT TOKEN
# =========================

def decode_access_token(token: str) -> dict | None:
    """
    Decode and validate a JWT access token.

    Returns the decoded payload when valid.
    Returns None when the token is invalid or expired.
    """

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        return None