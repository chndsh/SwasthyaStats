import pytest
from app.security.crypto import encrypt_secret, decrypt_secret


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
