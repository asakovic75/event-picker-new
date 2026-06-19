from typing import List, Optional
import bcrypt
import jwt
import os
import redis
import asyncpg
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
from dotenv import load_dotenv

from .errors import AppException, ErrorCode

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

class UserRegister(BaseModel):
    username: str
    password: str
    name: str = ""
    city: str = "Минск"
    interests: List[str] = []

class UserLogin(BaseModel):
    username: str
    password: str

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire.timestamp()}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire.timestamp()}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_db():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return await asyncpg.connect(DATABASE_URL)

def get_redis():
    return redis.Redis(host='redis', port=6379, decode_responses=True)

async def register_user(data: UserRegister):
    conn = await get_db()
    try:
        exists = await conn.fetchval("SELECT 1 FROM users WHERE username = $1", data.username)
        if exists:
            await conn.close()
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Пользователь уже существует",
                status_code=400
            )
        
        user_id = data.username
        hashed = hash_password(data.password)
        
        await conn.execute(
            "INSERT INTO users (id, username, name, password_hash, city, interests) VALUES ($1, $2, $3, $4, $5, $6)",
            user_id, data.username, data.name, hashed, data.city, data.interests
        )
        
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        
        await conn.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)",
            user_id, refresh_token, datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        await conn.close()
        
        r = get_redis()
        r.setex(f"access_token:{user_id}", ACCESS_TOKEN_EXPIRE_MINUTES * 60, access_token)
        r.close()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id
        }
    
    except AppException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise AppException(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            status_code=500
        )

async def login_user(data: UserLogin, response: Response):
    conn = await get_db()
    try:
        user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", data.username)
        if not user:
            await conn.close()
            raise AppException(
                code=ErrorCode.INVALID_CREDENTIALS,
                message="Неверный логин или пароль",
                status_code=401
            )
        
        if not verify_password(data.password, user['password_hash']):
            await conn.close()
            raise AppException(
                code=ErrorCode.INVALID_CREDENTIALS,
                message="Неверный логин или пароль",
                status_code=401
            )
        
        user_id = user['id']
        
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        
        await conn.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)",
            user_id, refresh_token, datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        await conn.close()
        
        r = get_redis()
        r.setex(f"access_token:{user_id}", ACCESS_TOKEN_EXPIRE_MINUTES * 60, access_token)
        r.close()
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )

        return {
            "user_id": user_id,
            "username": user['username'],
            "access_token": access_token
        }
    
    except AppException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise AppException(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            status_code=500
        )

async def logout_user(request: Request, response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    
    user_id = request.cookies.get("user_id")
    if user_id:
        r = get_redis()
        r.delete(f"access_token:{user_id}")
        r.close()
    
    return {"message": "Выход выполнен"}

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]
    else:
        token = request.cookies.get("access_token")
    
    if not token:
        raise AppException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Требуется авторизация",
            status_code=401
        )
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return {"user_id": user_id}
    except Exception as e:
        print(f"JWT decode error: {e}")
    
    raise AppException(
        code=ErrorCode.TOKEN_EXPIRED,
        message="Токен истек",
        status_code=401
    )