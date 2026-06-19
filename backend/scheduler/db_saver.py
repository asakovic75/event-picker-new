import asyncpg
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def save_events_to_db(events):
    if not events:
        print("No events to save")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        for event in events:
            date_start = None
            date_end = None
            
            if event.get('дата_начала'):
                try:
                    date_start = datetime.strptime(event['дата_начала'], '%Y-%m-%d')
                except:
                    date_start = None
            
            if event.get('дата_конца'):
                try:
                    date_end = datetime.strptime(event['дата_конца'], '%Y-%m-%d')
                except:
                    date_end = None
            
            exists = await conn.fetchval(
                "SELECT 1 FROM events WHERE id = $1", 
                event.get('id')
            )
            
            if exists:
                await conn.execute("""
                    UPDATE events SET
                        title = $1,
                        description = $2,
                        category = $3,
                        city = $4,
                        venue = $5,
                        date_start = $6,
                        date_end = $7,
                        price_min = $8,
                        price_max = $9,
                        age_restriction = $10,
                        poster_url = $11,
                        ticket_url = $12,
                        updated_at = NOW()
                    WHERE id = $13
                """,
                    event.get('название'),
                    event.get('описание'),
                    event.get('раздел'),
                    event.get('город'),
                    event.get('место'),
                    date_start,
                    date_end,
                    event.get('цена_мин'),
                    event.get('цена_макс'),
                    event.get('возраст'),
                    event.get('постер'),
                    event.get('ссылка'),
                    event.get('id')
                )
                print(f"Updated: {event.get('название')}")
            else:
                await conn.execute("""
                    INSERT INTO events (
                        id, title, description, category, city,
                        venue, date_start, date_end, price_min, price_max,
                        age_restriction, poster_url, ticket_url
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                    event.get('id'),
                    event.get('название'),
                    event.get('описание'),
                    event.get('раздел'),
                    event.get('город'),
                    event.get('место'),
                    date_start,
                    date_end,
                    event.get('цена_мин'),
                    event.get('цена_макс'),
                    event.get('возраст'),
                    event.get('постер'),
                    event.get('ссылка')
                )
                print(f"Inserted: {event.get('название')}")
        
        print(f"Saved {len(events)} events to database")
        
    except Exception as e:
        print(f"Error saving events: {e}")
    finally:
        await conn.close()