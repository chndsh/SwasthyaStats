import pytest
from app.security.crypto import (
    encrypt_secret,
    decrypt_secret,
    encrypt_for_user,
    decrypt_for_user,
)


def test_crypto_roundtrip():
    plaintext = "gsk_test_secret_api_key_12345"
    encrypted = encrypt_secret(plaintext)
    assert encrypted != plaintext
    decrypted = decrypt_secret(encrypted)
    assert decrypted == plaintext


def test_crypto_empty_string():
    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""


def test_crypto_invalid_ciphertext():
    with pytest.raises(ValueError):
        decrypt_secret("invalid-ciphertext-not-fernet")


def test_encrypt_for_user_roundtrip():
    ct = encrypt_for_user("HbA1c: 7.2", user_id=1)
    assert ct != "HbA1c: 7.2"
    assert decrypt_for_user(ct, user_id=1) == "HbA1c: 7.2"


def test_encrypt_for_user_isolation():
    ct = encrypt_for_user("secret health data", user_id=1)
    with pytest.raises(Exception):
        decrypt_for_user(ct, user_id=2)


def test_encrypt_for_user_empty():
    assert encrypt_for_user("", user_id=1) == ""
    assert decrypt_for_user("", user_id=1) == ""

