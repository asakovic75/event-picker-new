import asyncpg
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_recommendations(user_id: str, limit: int = 5) -> List[Dict]:
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        fav_categories = await conn.fetch("""
            SELECT DISTINCT e.category
            FROM favorites f
            JOIN events e ON f.event_id = e.id
            WHERE f.user_id = $1 AND e.category IS NOT NULL AND e.category != ''
        """, user_id)
        
        categories = [row['category'] for row in fav_categories]
        
        if not categories:
            rows = await conn.fetch("""
                SELECT 
                    id, title, description, category, city, venue,
                    date_start, date_end, price_min, price_max,
                    age_restriction, poster_url, ticket_url
                FROM events
                WHERE date_start >= CURRENT_DATE
                ORDER BY date_start ASC
                LIMIT $1
            """, limit)
            
            await conn.close()
            return format_events(rows)
        
        placeholders = ', '.join(f'${i+2}' for i in range(len(categories)))
        sql = f"""
            SELECT 
                id, title, description, category, city, venue,
                date_start, date_end, price_min, price_max,
                age_restriction, poster_url, ticket_url
            FROM events
            WHERE category IN ({placeholders})
                AND date_start >= CURRENT_DATE
                AND id NOT IN (
                    SELECT event_id FROM favorites WHERE user_id = $1
                )
            ORDER BY date_start ASC, price_min ASC
            LIMIT ${len(categories) + 2}
        """
        
        params = [user_id] + categories + [limit]
        rows = await conn.fetch(sql, *params)
        await conn.close()
        
        if not rows:
            return []
        
        return format_events(rows)
        
    except Exception as e:
        print(f"Recommendations error: {e}")
        await conn.close()
        return []

def format_events(rows) -> List[Dict]:
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