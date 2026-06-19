import os
import re
import asyncpg
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

CITIES = {
    'минск': 'Минск',
    'гродно': 'Гродно',
    'брест': 'Брест',
    'витебск': 'Витебск',
    'гомель': 'Гомель',
    'могилев': 'Могилев'
}

def is_query_relevant(query: str) -> bool:
    return True

def parse_date_from_query(query: str) -> Dict[str, Any]:
    q = query.lower()
    today = datetime.now().date()
    result = {'date_from': None, 'date_to': None}

    if 'сегодня' in q:
        result['date_from'] = today
        result['date_to'] = today
    elif 'завтра' in q:
        result['date_from'] = today + timedelta(days=1)
        result['date_to'] = today + timedelta(days=1)
    elif 'выходн' in q:
        days_ahead = 5 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        result['date_from'] = today + timedelta(days=days_ahead)
        result['date_to'] = result['date_from'] + timedelta(days=1)
    else:
        match = re.search(r'(\d{1,2})\.(\d{2})\.(\d{4})', q)
        if match:
            try:
                date_obj = datetime.strptime(f"{match.group(1)}.{match.group(2)}.{match.group(3)}", '%d.%m.%Y').date()
                result['date_from'] = date_obj
                result['date_to'] = date_obj
            except:
                pass

    return result

async def search_events(query: str, city: Optional[str] = None, offset: int = 0, limit: int = 5, user_id: Optional[str] = None) -> Dict[str, Any]:
    q_lower = query.lower()
    
    search_city = city
    for key, value in CITIES.items():
        if key in q_lower:
            search_city = value
            break
    
    category = None
    category_map = {
        'концерт': 'Концерты',
        'концерты': 'Концерты',
        'спектакль': 'Спектакли',
        'спектакли': 'Спектакли',
        'кино': 'Кино',
        'фильм': 'Кино',
        'выставк': 'Выставки',
        'фестивал': 'Фестивали',
        'квест': 'Квесты',
        'спорт': 'Спорт',
        'детск': 'Детская афиша',
        'обучени': 'Обучение'
    }
    for key, value in category_map.items():
        if key in q_lower:
            category = value
            break
    
    price_min = None
    price_max = None
    if 'бесплатн' in q_lower:
        price_max = 0
    elif 'дешев' in q_lower:
        price_max = 30
    elif 'дорог' in q_lower:
        price_min = 50
    
    date_filters = parse_date_from_query(query)
    date_from = date_filters.get('date_from')
    date_to = date_filters.get('date_to')
    
    conditions = []
    params = []
    param_idx = 1
    
    if search_city:
        conditions.append(f"city = ${param_idx}")
        params.append(search_city)
        param_idx += 1
    
    if category:
        conditions.append(f"category = ${param_idx}")
        params.append(category)
        param_idx += 1
    
    if date_from and date_to:
        conditions.append(f"date_start >= ${param_idx} AND date_start <= ${param_idx + 1}")
        params.append(date_from)
        params.append(date_to)
        param_idx += 2
    elif date_from:
        conditions.append(f"date_start >= ${param_idx}")
        params.append(date_from)
        param_idx += 1
    elif date_to:
        conditions.append(f"date_start <= ${param_idx}")
        params.append(date_to)
        param_idx += 1
    
    if price_min is not None:
        conditions.append(f"price_min >= ${param_idx}")
        params.append(price_min)
        param_idx += 1
    
    if price_max is not None:
        conditions.append(f"price_min <= ${param_idx}")
        params.append(price_max)
        param_idx += 1
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT 
            id, title, description, category, city, venue,
            date_start, date_end, price_min, price_max,
            age_restriction, poster_url, ticket_url,
            latitude, longitude
        FROM events
        WHERE {where_clause}
        ORDER BY date_start ASC, price_min ASC
        LIMIT {limit} OFFSET {offset}
    """
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch(sql, *params)
        await conn.close()
        
        results = []
        for row in rows:
            results.append({
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
                'ссылка': row['ticket_url'],
                'latitude': row['latitude'],
                'longitude': row['longitude']
            })
        
        if user_id and results:
            try:
                conn = await asyncpg.connect(DATABASE_URL)
                for event in results:
                    await conn.execute(
                        "INSERT INTO views (user_id, event_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        user_id, event['id']
                    )
                await conn.close()
            except Exception as e:
                print(f"Views error: {e}")
        
        ai_text = generate_response(query, results, search_city)
        
        return {
            "status": "ok",
            "results": results,
            "ai_text": ai_text,
            "total": len(results),
            "offset_next": offset + limit if len(results) == limit else None,
            "filters_applied": {
                "city": search_city,
                "category": category,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
                "price_min": price_min,
                "price_max": price_max
            }
        }
    except Exception as e:
        print(f"DB error: {e}")
        return {
            "status": "error",
            "results": [],
            "ai_text": "Ошибка поиска",
            "total": 0,
            "offset_next": None,
            "error": str(e)
        }

def generate_response(query: str, events: List[Dict], city: str) -> str:
    if not events:
        return f"В {city} по твоему запросу ничего не нашлось. Попробуй изменить даты или категорию!"
    
    events_text = ""
    for i, ev in enumerate(events[:5], 1):
        price = f"{ev.get('цена_мин')} - {ev.get('цена_макс')}" if ev.get('цена_мин') else "Цена уточняется"
        if ev.get('цена_мин') == 0:
            price = "БЕСПЛАТНО!"
        events_text += f"{i}. {ev.get('название')}\n"
        events_text += f"   Место: {ev.get('место')}\n"
        events_text += f"   Дата: {ev.get('дата_начала')}\n"
        events_text += f"   Цена: {price}\n\n"
    
    import httpx
    import os
    
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    prompt = f"""
Ты дружелюбный помощник по поиску событий.

Запрос пользователя: "{query}"
Найденные события:
{events_text}

Задача:
1. Дружелюбно представь найденные события
2. Для каждого события дай краткое описание (что это, для кого, чем интересно)
3. Если есть бесплатные - обязательно подчеркни это
4. Скажи, что можно сказать "другие" для следующих событий
5. Будь кратким и позитивным, используй эмодзи
6. Максимум 5 предложений на событие
"""
    
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Ты дружелюбный помощник по поиску событий. Отвечай кратко, по-русски, используй эмодзи."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq error in search: {e}")

    return f"🎉 Нашёл для вас {len(events)} событий в {city}! Скажите «другие», чтобы увидеть ещё."