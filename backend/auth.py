"""
auth.py — JWT Authentication + Authorization for Movie & TV Recommendation Engine.

Provides:
  - /token          POST — OAuth2 password flow (access + refresh token)
  - /api/register   POST — create a new user account
  - /api/refresh    POST — exchange a valid refresh token for a new access token
  - get_current_user()  FastAPI dependency (any authenticated user)
  - require_admin()     FastAPI dependency (admin role only)

Users are stored in the application database (`users` table in database.py).
The DB is seeded with an admin account from env vars by database.init_db().

Refresh token design
--------------------
Refresh tokens are long-lived JWTs signed with the same SECRET_KEY but carrying
  - "type": "refresh"  — so they are rejected by access-token validators
  - longer "exp" — controlled by REFRESH_TOKEN_EXPIRE_DAYS (default 30 days)

Storing refresh tokens in the DB (blocklist / allowlist) is intentionally left
as a future enhancement; for the current scope a signed JWT with a "type" claim
is sufficient and stateless.
"""

import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db, get_user_by_username, User

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "30"))

# Minimum password length enforced at registration
MIN_PASSWORD_LENGTH = 8

# ── Password Hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Database-Backed User Helpers ──────────────────────────────────────────────

def get_user(db: Session, username: str) -> Optional[dict]:
    """Return the user as a plain dict, or None."""
    user_obj = get_user_by_username(db, username)
    return user_obj.to_dict() if user_obj else None


def authenticate_user(db: Session, username: str, password: str) -> Optional[dict]:
    """Verify credentials against the DB. Returns user dict or None."""
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    if user.get("disabled"):
        return None
    return user


def create_db_user(db: Session, username: str, password: str, role: str = "user") -> dict:
    """
    Insert a new user into the database.

    Raises HTTPException 409 if the username is already taken.
    """
    if get_user_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' is already registered.",
        )
    new_user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        disabled=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user.to_dict()


# ── Token Helpers ─────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int           # seconds until access token expires
    refresh_expires_in: int   # seconds until refresh token expires


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived access JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a long-lived refresh JWT.

    The "type": "refresh" claim distinguishes it from access tokens so that
    presenting a refresh token to a protected endpoint is rejected.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _issue_token_pair(user: dict) -> Token:
    """Build a Token response containing both access and refresh tokens."""
    access = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh = create_refresh_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return Token(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


# ── FastAPI OAuth2 Scheme ─────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """
    Dependency: decode the JWT and return the authenticated user dict.

    Rejects refresh tokens (type != "access") so they cannot be used directly
    to call protected endpoints.  The DB is consulted on every request so that
    account disablement takes effect immediately.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Reject refresh tokens presented to access-protected endpoints
        if payload.get("type") != "access":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=payload.get("role"))
    except JWTError:
        raise credentials_exception

    user = get_user(db, token_data.username)
    if user is None or user.get("disabled"):
        raise credentials_exception
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: requires admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user


# ── Pydantic Request Models ───────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username may only contain letters, digits, underscores, hyphens, and dots.")
        return v

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 password flow.

    Returns both an access token (short-lived) and a refresh token (long-lived).
    Store the refresh token securely client-side (httpOnly cookie preferred);
    use it to obtain new access tokens via POST /api/refresh.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token_pair(user)


@router.post("/api/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account.

    - Validates username format and minimum password length.
    - Hashes the password with bcrypt before storage.
    - Returns 409 Conflict if the username is already taken.

    New accounts are assigned the "user" role.  Promote to "admin" manually
    via the database or a future admin endpoint.
    """
    user = create_db_user(db, body.username, body.password, role="user")
    return {
        "status": "created",
        "username": user["username"],
        "role": user["role"],
        "message": "Account created successfully. You can now log in via POST /token.",
    }


@router.post("/api/refresh", response_model=Token)
async def refresh_access_token(
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a fresh access + refresh token pair.

    The submitted token must:
      - Have "type": "refresh" in its payload.
      - Not be expired.
      - Belong to an active (non-disabled) user.

    Both tokens in the response are newly issued — the old refresh token is
    rotated (replaced) on each call, limiting the blast radius of a stolen token.
    """
    invalid_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise invalid_exception
        username: str = payload.get("sub")
        if not username:
            raise invalid_exception
    except JWTError:
        raise invalid_exception

    user = get_user(db, username)
    if user is None or user.get("disabled"):
        raise invalid_exception

    # Rotate: issue a completely new pair so old refresh token is implicitly invalidated
    return _issue_token_pair(user)
