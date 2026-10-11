def test_password_hash_is_salted_and_verifies():
    from app.utils.security import hash_password, verify_password

    first = hash_password("local-test-password")
    second = hash_password("local-test-password")

    assert first != second
    assert verify_password("local-test-password", first)
    assert not verify_password("wrong-password", first)


def test_access_token_contains_admin_subject(monkeypatch):
    from app.config.settings import get_settings
    from app.utils.security import create_access_token, decode_access_token

    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "unit-test-secret-32-bytes-long-value")
    get_settings.cache_clear()
    token = create_access_token("7", "admin")
    payload = decode_access_token(token)

    assert payload["sub"] == "7"
    assert payload["username"] == "admin"
    get_settings.cache_clear()
