from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import json
import sys
import os
import asyncpg
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from .search import search_events
from .chat import chat_with_groq
from .profile import get_profile, update_profile
from .favorites import add_favorite, remove_favorite, get_favorites
from .recommendations import get_recommendations
from .errors import AppException, ErrorCode, error_response
from .auth import (
    register_user, login_user, logout_user, get_current_user,
    UserRegister, UserLogin
)

app = FastAPI(
    title="Event Picker API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("error_logger")

try:
    os.makedirs('/var/log/app', exist_ok=True)
    file_handler = logging.FileHandler('/var/log/app/errors.log')
    file_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")

class ErrorLogRequest(BaseModel):
    code: int
    message: str
    url: Optional[str] = None
    details: Optional[str] = None

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/auth/register")
async def register(data: UserRegister):
    return await register_user(data)

@app.post("/api/auth/login")
async def login(data: UserLogin, response: Response):
    return await login_user(data, response)

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    return await logout_user(request, response)

@app.get("/api/auth/me")
async def me(request: Request):
    return await get_current_user(request)

@app.post("/api/parser/run")
async def run_parser(background_tasks: BackgroundTasks):
    try:
        from app.scheduler.parser import run_parser as parser_run
        
        def run_in_background():
            parser_run()
        
        background_tasks.add_task(run_in_background)
        return {"status": "started", "message": "Parser started in background"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/parser/status")
async def parser_status():
    import csv
    csv_path = Path(__file__).resolve().parent.parent / "afisha_events.csv"
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = sum(1 for _ in reader) - 1
        return {"status": "ok", "events_count": rows, "file": str(csv_path)}
    return {"status": "no_data", "message": "No data yet. Run parser first."}

@app.get("/api/search")
async def search(query: str, request: Request, city: Optional[str] = None, offset: int = 0, limit: int = 5):
    try:
        user = await get_current_user(request)
        user_id = user['user_id']
    except:
        user_id = None
    return await search_events(query, city, offset, limit, user_id)

@app.post("/api/favorites")
async def add_to_favorites(event_id: str, request: Request):
    user = await get_current_user(request)
    return await add_favorite(user['user_id'], event_id)

@app.delete("/api/favorites/{event_id}")
async def delete_favorite(event_id: str, request: Request):
    user = await get_current_user(request)
    return await remove_favorite(user['user_id'], event_id)

@app.get("/api/favorites")
async def get_user_favorites(request: Request):
    user = await get_current_user(request)
    return await get_favorites(user['user_id'])

@app.get("/api/profile")
async def profile(request: Request):
    user = await get_current_user(request)
    return await get_profile(user['user_id'])

@app.put("/api/profile")
async def update_profile_data(request: Request):
    user = await get_current_user(request)
    data = await request.json()
    return await update_profile(user['user_id'], data)

@app.get("/api/recommendations")
async def recommendations(request: Request, limit: int = 3):
    user = await get_current_user(request)
    return await get_recommendations(user['user_id'], limit)

@app.post("/api/error-log")
async def log_error(data: ErrorLogRequest, request: Request):
    try:
        user_id = None
        try:
            user = await get_current_user(request)
            user_id = user['user_id']
        except:
            pass
        
        user_agent = request.headers.get('user-agent', '')
        ip = request.client.host if request.client else None
        
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO error_logs (code, message, user_id, user_agent, url, ip, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
        """, data.code, data.message, user_id, user_agent, data.url, ip)
        await conn.close()
        
        logger.error(f"[{data.code}] {data.message} | User: {user_id} | URL: {data.url} | IP: {ip}")
        
        return {"status": "ok", "logged_at": datetime.utcnow().isoformat()}
    
    except Exception as e:
        logger.error(f"Error logging error: {e}")
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="Ошибка при логировании",
            status_code=500,
            details=str(e)
        )

@app.post("/api/chat")
async def chat(request: Request, body: dict):
    try:
        user = await get_current_user(request)
        user_id = user['user_id']
    except:
        raise AppException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Требуется авторизация",
            status_code=401
        )
    
    query = body.get('query')
    if not query:
        raise AppException(
            code=ErrorCode.VALIDATION_ERROR,
            message="Поле 'query' обязательно",
            status_code=400
        )
    
    city = body.get('city')
    
    return await chat_with_groq(query, user_id, city)

@app.post("/api/scheduler/start")
async def start_scheduler():
    try:
        from scheduler.scheduler import run_scheduler_in_background
        thread = run_scheduler_in_background()
        return {"status": "started", "message": "Scheduler started. Runs every Monday and Thursday at 3:00 AM"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/scheduler/status")
async def scheduler_status():
    return {"status": "running", "schedule": "Monday and Thursday at 3:00 AM"}