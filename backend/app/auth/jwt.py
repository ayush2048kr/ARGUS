from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

from dotenv import load_dotenv
from jose import jwt, JWTError


# Load the backend .env file independently of the terminal's working directory.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)


# Never use a hardcoded fallback for the JWT signing key.
SECRET_KEY = os.getenv("ARGUS_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "ARGUS_SECRET_KEY is missing. Configure it in backend/.env."
    )

if SECRET_KEY == "generate-a-secure-random-secret":
    raise RuntimeError(
        "Replace the placeholder ARGUS_SECRET_KEY with a secure random secret."
    )

if len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError(
        "ARGUS_SECRET_KEY must be at least 32 bytes long."
    )


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(user_id: str, role: str) -> str:
    expire_time = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire_time,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError:
        return None
