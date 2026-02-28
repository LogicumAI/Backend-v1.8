"""
Shared FastAPI dependencies.

get_current_user_id lives here so that routers can import it without
creating a circular dependency with main.py.
"""

import os
import uuid

import jwt
from fastapi import HTTPException, Request

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback_secret_for_development_only")
JWT_ALGORITHM = "HS256"


def get_current_user_id(request: Request):
    """
    Dependency to get the current user ID strictly from the httpOnly access_token cookie.
    """
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id_str = payload.get("user_id")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Token missing user_id")

        return uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
