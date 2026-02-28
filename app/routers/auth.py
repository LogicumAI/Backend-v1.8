import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.core import config
from app.core.database import get_session
from app.models import RefreshToken, User
from app.schemas import AuthRequest
from app.services.auth import (
    create_token,
    get_password_hash,
    set_auth_cookies,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register(payload: AuthRequest, response: Response, session: Session = Depends(get_session)):
    # Check if user already exists
    statement = select(User).where(User.email == payload.email)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    try:
        hashed_pwd = get_password_hash(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    new_user = User(
        email=payload.email,
        hashed_password=hashed_pwd,
        name=payload.email.split("@")[0]
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    access_token = create_token(new_user.id, "access", timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(new_user.id, "refresh", timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS))
    
    # Store refresh token in DB
    db_token = RefreshToken(
        token=refresh_token,
        user_id=new_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    session.add(db_token)
    session.commit()
    
    set_auth_cookies(response, access_token, refresh_token)
    
    return {
        "user": {"email": new_user.email, "id": str(new_user.id)},
        "access_token": access_token
    }

@router.post("/login")
async def login(payload: AuthRequest, response: Response, session: Session = Depends(get_session)):
    statement = select(User).where(User.email == payload.email)
    user = session.exec(statement).first()
    
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_token(user.id, "access", timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(user.id, "refresh", timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS))
    
    # Store refresh token in DB
    db_token = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    session.add(db_token)
    session.commit()
    
    set_auth_cookies(response, access_token, refresh_token)
    
    return {
        "user": {"email": user.email, "id": str(user.id)},
        "access_token": access_token
    }
