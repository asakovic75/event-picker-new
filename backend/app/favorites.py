import asyncpg
import os
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def add_favorite(user_id: str, event_id: str):
    conn = await get_db()
    try:
        event = await conn.fetchrow("SELECT 1 FROM events WHERE id = $1", event_id)
        if not event:
            await conn.close()
            raise HTTPException(status_code=404, detail="Событие не найдено")
        
        exists = await conn.fetchval(
            "SELECT 1 FROM favorites WHERE user_id = $1 AND event_id = $2",
            user_id, event_id
        )
        if exists:
            await conn.close()
            raise HTTPException(status_code=400, detail="Уже в избранном")
        
        await conn.execute(
            "INSERT INTO favorites (user_id, event_id) VALUES ($1, $2)",
            user_id, event_id
        )
        await conn.close()
        return {"status": "ok", "message": "Добавлено в избранное"}
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))

async def remove_favorite(user_id: str, event_id: str):
    conn = await get_db()
    try:
        result = await conn.execute(
            "DELETE FROM favorites WHERE user_id = $1 AND event_id = $2",
            user_id, event_id
        )
        await conn.close()
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Не в избранном")
        return {"status": "ok", "message": "Удалено из избранного"}
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))

async def get_favorites(user_id: str):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT e.* FROM events e
            JOIN favorites f ON e.id = f.event_id
            WHERE f.user_id = $1
            ORDER BY f.added_at DESC
        """, user_id)
        await conn.close()
        
        result = []
        for row in rows:
            result.append({
                'id': row['id'],
                'название': row['title'],
                'описание': row['description'],
                'раздел': row['category'] or 'Событие',
                'город': row['city'],
                'место': row['venue'],
                'дата_начала': str(row['date_start']) if row['date_start'] else None,
                'дата_конца': str(row['date_end']) if row['date_end'] else None,
                'цена_мин': row['price_min'],
                'цена_макс': row['price_max'],
                'возраст': row['age_restriction'],
                'постер': row['poster_url'],
                'ссылка': row['ticket_url']
            })
        return result
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=str(e))