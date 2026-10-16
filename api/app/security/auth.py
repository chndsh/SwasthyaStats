from fastapi import Header, HTTPException, status
from app.config import get_settings


def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    expected = get_settings().API_KEY
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key header (X-API-Key)",
        )
    return True
