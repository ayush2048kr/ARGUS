from app.auth.jwt import create_access_token, decode_access_token


def test_create_and_decode_access_token():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "EMP001"
    assert payload["role"] == "analyst"


def test_invalid_access_token():
    payload = decode_access_token("invalid-token")

    assert payload is None
