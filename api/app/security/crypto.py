import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import get_settings


def _get_fernet() -> Fernet:
    secret = get_settings().SERVER_SECRET.encode("utf-8")
    # Derive a deterministic 32-byte urlsafe key from SERVER_SECRET
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _get_user_fernet(user_id: int) -> Fernet:
    secret = get_settings().SERVER_SECRET.encode("utf-8")
    salt = f"|user:{user_id}".encode("utf-8")
    digest = hashlib.sha256(secret + salt).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt secret: {e}")


def encrypt_for_user(plaintext: str, user_id: int) -> str:
    if not plaintext:
        return ""
    fernet = _get_user_fernet(user_id)
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_for_user(ciphertext: str, user_id: int) -> str:
    if not ciphertext:
        return ""
    fernet = _get_user_fernet(user_id)
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt secret for user {user_id}: {e}")
