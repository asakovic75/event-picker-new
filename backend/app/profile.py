import asyncpg
import os
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def get_profile(user_id: str):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT id, username, name, city, interests FROM users WHERE id = $1",
            user_id
        )
        await conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            'id': row['id'],
            'username': row['username'],
            'name': row['name'] or row['username'],
            'city': row['city'] or 'Минск',
            'interests': row['interests'] or []
        }
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))

async def update_profile(user_id: str, data: dict):
    conn = await get_db()
    try:
        updates = []
        params = []
        param_count = 1
        
        if data.get('name') is not None:
            updates.append(f"name = ${param_count}")
            params.append(data['name'])
            param_count += 1
        
        if data.get('city') is not None:
            updates.append(f"city = ${param_count}")
            params.append(data['city'])
            param_count += 1
        
        if data.get('interests') is not None:
            updates.append(f"interests = ${param_count}")
            params.append(data['interests'])
            param_count += 1
        
        if not updates:
            await conn.close()
            return {"status": "ok", "message": "Нет данных для обновления"}
        
        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        await conn.execute(sql, *params)
        await conn.close()
        
        return {"status": "ok", "message": "Профиль обновлён"}
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))

async def update_profile(user_id: str, data: dict):
    conn = await get_db()
    try:
        updates = []
        params = []
        param_count = 1
        
        if data.get('name') is not None:
            updates.append(f"username = ${param_count}")
            params.append(data['name'])
            param_count += 1
        
        if data.get('city') is not None:
            updates.append(f"city = ${param_count}")
            params.append(data['city'])
            param_count += 1
        
        if data.get('interests') is not None:
            updates.append(f"interests = ${param_count}")
            params.append(data['interests'])
            param_count += 1
        
        if not updates:
            await conn.close()
            return {"status": "ok", "message": "Нет данных для обновления"}
        
        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        await conn.execute(sql, *params)
        await conn.close()
        
        return {"status": "ok", "message": "Профиль обновлён"}
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))