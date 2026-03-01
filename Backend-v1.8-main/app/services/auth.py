import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response
from passlib.context import CryptContext

from app.core import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    if len(password.encode('utf-8')) > 72:
        raise ValueError("Password cannot be longer than 72 bytes due to bcrypt limitation")
    return pwd_context.hash(password)

# JWT Configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback_secret_for_development_only")
JWT_ALGORITHM = "HS256"

def create_token(user_id: uuid.UUID, token_type: str, expires_delta: timedelta):
    """Generates an Access or Refresh Token."""
    payload = {
        "user_id": str(user_id),
        "exp": datetime.now(timezone.utc) + expires_delta,
        "type": token_type
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Sets both Access and Refresh tokens as httpOnly cookies with configurable security."""
    # Access Token (short-lived)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/",
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    # Refresh Token (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/",
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

def clear_auth_cookies(response: Response):
    """Clears both auth cookies."""
    response.delete_cookie(
        key="access_token", 
        path="/", 
        samesite=config.COOKIE_SAMESITE, 
        secure=config.COOKIE_SECURE
    )
    response.delete_cookie(
        key="refresh_token", 
        path="/", 
        samesite=config.COOKIE_SAMESITE, 
        secure=config.COOKIE_SECURE
    )
