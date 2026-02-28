import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core import config
from app.core.config import ALLOWED_ORIGINS
from app.core.database import engine, get_session, init_db
from migrate_db import migrate_chat_table
from app.models import RefreshToken, User
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.projects import router as projects_router
from app.routers.tts import router as tts_router
from app.routers.ocr_v3 import router as ocr_v3_router
from app.services.auth import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    clear_auth_cookies,
    create_token,
    set_auth_cookies,
)

app = FastAPI(title="Logicum V2 API")

# --- JWT Configuration ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback_secret_for_development_only")
JWT_ALGORITHM = "HS256"



class KronosAuthRequest(BaseModel):
    code: str

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


def _normalize_kronos_code(value: str) -> str:
    return (
        (value or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def _load_kronos_codes() -> set[str]:
    raw = os.environ.get("KRONOS_CODES", "")
    env_codes = {_normalize_kronos_code(c) for c in raw.split(",") if c.strip()}
    # Keep test/fallback codes active for tester access.
    fallback_codes = {"123", "TEST123", "PR0METE0"}
    return env_codes | fallback_codes


KRONOS_CODES = _load_kronos_codes()

@app.on_event("startup")
def on_startup():
    init_db()
    migrate_chat_table()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(projects_router)
app.include_router(tts_router)
app.include_router(ocr_v3_router)

@app.get("/")
async def root():
    return {"status": "online", "message": "Logicum V2 Backend is running"}

@app.get("/health")
async def health_check():
    return {"status": "online", "message": "ok"}


@app.post("/auth/kronos")
async def auth_kronos(payload: KronosAuthRequest, response: Response):
    code = _normalize_kronos_code(payload.code)
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    if code not in KRONOS_CODES:
        raise HTTPException(status_code=401, detail="Invalid Kronos code")

    email = "kronos.tester@logicum.ai"
    
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, name="Kronos Tester")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        user_id = user.id

    access_token = create_token(user_id, "access", timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(user_id, "refresh", timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS))
    
    set_auth_cookies(response, access_token, refresh_token)
    
    user_data = {
        "email": email,
        "id": str(user_id),
        "role": "tester",
        "auth_provider": "kronos",
    }
    return {"user": user_data}


@app.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
    """Verifies refresh token and issues new access/refresh tokens."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id_str = payload.get("user_id")
        user_id = uuid.UUID(user_id_str)
        
        # Check if token is in DB and not revoked
        with Session(engine) as db_session:
            db_token = db_session.exec(
                select(RefreshToken).where(RefreshToken.token == token, RefreshToken.revoked == False)
            ).first()
            if not db_token:
                raise HTTPException(status_code=401, detail="Token revoked or not found")
            
            # Rotation: Issue new tokens
            new_access = create_token(user_id, "access", timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
            new_refresh = create_token(user_id, "refresh", timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS))
            
            # Update DB
            db_token.revoked = True
            session_token = RefreshToken(
                token=new_refresh,
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            db_session.add(db_token)
            db_session.add(session_token)
            db_session.commit()
            
            set_auth_cookies(response, new_access, new_refresh)
            return {"ok": True}
            
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")




@app.get("/me")
async def get_me(user_id: uuid.UUID = Depends(get_current_user_id)):
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.id == user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name or user.preferred_name or "",
            "created_at": user.created_at
        }

class UpdateProfileRequest(BaseModel):
    preferred_name: str

@app.post("/update-profile")
async def update_profile(
    payload: UpdateProfileRequest,
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.id == user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.preferred_name = payload.preferred_name
        user.name = payload.preferred_name  # Sync name as well for legacy compatibility
        db_session.add(user)
        db_session.commit()
    
    return {"ok": True, "preferred_name": payload.preferred_name}


@app.post("/auth/logout")
async def auth_logout(response: Response, request: Request):
    # Revoke refresh token if present
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        with Session(engine) as db_session:
            db_token = db_session.exec(
                select(RefreshToken).where(RefreshToken.token == refresh_token)
            ).first()
            if db_token:
                db_token.revoked = True
                db_session.add(db_token)
                db_session.commit()

    clear_auth_cookies(response)
    return {"ok": True}
