import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, set_rls_user_id
from app.models import User, RefreshTokenBlocklist

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserCreateRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class PasswordResetRequest(BaseModel):
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: Optional[str] = None
    is_admin: bool
    must_change_password: bool
    created_at: datetime


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.SERVER_SECRET, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.SERVER_SECRET, algorithm="HS256")


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    if x_api_key and settings.API_KEY and x_api_key == settings.API_KEY:
        admin = db.query(User).filter(User.is_admin == True).first()
        if admin:
            set_rls_user_id(db, admin.id)
            return admin

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, settings.SERVER_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    set_rls_user_id(db, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


def bootstrap_admin(db: Session):
    """Ensure at least one admin user exists based on environment configuration."""
    admin_count = db.query(User).filter(User.is_admin == True).count()
    if admin_count > 0:
        return

    settings = get_settings()
    existing = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if existing:
        existing.is_admin = True
        db.commit()
        return

    hashed = ph.hash(settings.ADMIN_PASSWORD)
    admin = User(
        email=settings.ADMIN_EMAIL,
        display_name="Admin",
        password_hash=hashed,
        is_admin=True,
    )
    db.add(admin)
    db.commit()


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        ph.verify(user.password_hash, req.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(req: RefreshRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        payload = jwt.decode(req.refresh_token, settings.SERVER_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = int(payload.get("sub"))
        exp_ts = int(payload.get("exp"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    issued_at = datetime.fromtimestamp(int(payload.get("iat", 0)), tz=timezone.utc)
    if user.refresh_token_invalidated_at and issued_at <= user.refresh_token_invalidated_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    # Check blocklist
    token_h = hash_token(req.refresh_token)
    blocked = db.query(RefreshTokenBlocklist).filter(RefreshTokenBlocklist.token_hash == token_h).first()
    if blocked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    # Invalidate current refresh token
    exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    block_entry = RefreshTokenBlocklist(token_hash=token_h, expires_at=exp_dt)
    db.add(block_entry)
    db.commit()

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    req: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req and req.refresh_token:
        try:
            settings = get_settings()
            payload = jwt.decode(req.refresh_token, settings.SERVER_SECRET, algorithms=["HS256"])
            exp_ts = int(payload.get("exp"))
            token_h = hash_token(req.refresh_token)
            exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            db.merge(RefreshTokenBlocklist(token_hash=token_h, expires_at=exp_dt))
            db.commit()
        except Exception:
            pass
    return None


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=List[UserRead])
def list_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.id.asc()).all()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed = ph.hash(req.password)
    user = User(
        email=req.email,
        password_hash=hashed,
        display_name=req.display_name,
        is_admin=False,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()
    return None


@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int,
    req: PasswordResetRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = ph.hash(req.password)
    user.must_change_password = True
    user.refresh_token_invalidated_at = datetime.now(timezone.utc)
    db.commit()
    return None


@router.put("/me/password", response_model=UserRead)
def change_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters",
        )
    try:
        ph.verify(current_user.password_hash, req.current_password)
    except VerifyMismatchError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    current_user.password_hash = ph.hash(req.new_password)
    current_user.must_change_password = False
    current_user.refresh_token_invalidated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user
