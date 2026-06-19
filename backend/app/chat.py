import os
import httpx
import asyncio
import asyncpg
import re
import random
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
from datetime import datetime

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

CITIES_LIST = ['Минск', 'Гродно', 'Брест', 'Витебск', 'Гомель', 'Могилев']

GROQ_MODEL = "llama-3.3-70b-versatile"

async def call_groq(prompt: str, retry_count: int = 0) -> Optional[str]:
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
    "model": GROQ_MODEL,
    "messages": [
        {"role": "system", "content": """Ты - помощник по поиску событий (концерты, театр, спорт, фестивали, выставки, кино, квесты, детские мероприятия).

ПРАВИЛА:
1. Отвечай ТОЛЬКО на вопросы о событиях, культурных мероприятиях, досуге.
2. Если пользователь спрашивает о курсе доллара, погоде, рецептах, политике, науке или других темах - вежливо скажи, что ты помогаешь только с поиском событий.
3. На вопросы о событиях отвечай кратко, по-русски, используй эмодзи.
4. Если есть события - представь их.
5. Если нет - предложи изменить запрос.
6. Всегда предлагай сказать "другие" для следующих событий."""},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.7,
    "max_tokens": 700
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            
            if response.status_code == 429 and retry_count < 3:
                wait_time = (2 ** retry_count) + 1
                print(f"Rate limit, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                return await call_groq(prompt, retry_count + 1)
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                print(f"Groq error: {response.status_code} - {response.text[:200]}")
                return None
    except Exception as e:
        print(f"Groq error: {e}")
        return None

def generate_smart_response(query: str, events: list, city: str, filters: dict) -> str:
    if not events:
        responses = [
            f"😕 В {city} по вашему запросу ничего не нашлось. Попробуйте изменить даты или категорию!",
            f"🔍 В {city} ничего не нашлось. Может, посмотрим в другом городе?",
            f"🤔 Похоже, в {city} нет таких событий. Попробуйте поискать что-то другое!"
        ]
        return random.choice(responses)
    
    events_text = ""
    free_events = []
    for i, ev in enumerate(events[:5], 1):
        title = ev.get('название', 'Событие')
        venue = ev.get('место', 'Место не указано')
        date = ev.get('дата_начала', 'Дата не указана')
        price = ev.get('цена_мин', 0)
        price_text = f"{price} руб." if price > 0 else "БЕСПЛАТНО! 🎉"
        if price == 0:
            free_events.append(title)
        events_text += f"{i}. {title}\n   📍 {venue}\n   📅 {date}\n   💰 {price_text}\n\n"
    
    intro = random.choice([
        f"🎉 Отличный выбор! Нашёл для вас {len(events)} событий в {city}:",
        f"🔥 В {city} есть {len(events)} интересных событий по вашему запросу:",
        f"✨ Держите {len(events)} событий в {city}, которые могут вас заинтересовать:"
    ])
    
    free_note = ""
    if free_events:
        free_note = f"\n🎁 Обратите внимание на бесплатные события: {', '.join(free_events[:3])}!"
    
    next_note = "\n💡 Хотите увидеть другие варианты? Скажите «другие»!"
    
    return f"{intro}\n\n{events_text}{free_note}{next_note}"

async def get_or_create_dialog(user_id: str) -> int:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow(
            "SELECT id FROM dialogs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user_id
        )
        if row:
            return row['id']
        
        dialog_id = await conn.fetchval(
            "INSERT INTO dialogs (user_id) VALUES ($1) RETURNING id",
            user_id
        )
        return dialog_id
    finally:
        await conn.close()

async def save_message(dialog_id: int, role: str, content: str):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO messages (dialog_id, role, content) VALUES ($1, $2, $3)",
            dialog_id, role, content
        )
    finally:
        await conn.close()

async def get_dialog_history(dialog_id: int, limit: int = 10) -> List[Dict]:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE dialog_id = $1 ORDER BY created_at ASC LIMIT $2",
            dialog_id, limit
        )
        return [{"role": row['role'], "content": row['content']} for row in rows]
    finally:
        await conn.close()

def detect_city(query: str, user_city: Optional[str] = None) -> str:
    for city in CITIES_LIST:
        if city.lower() in query.lower():
            return city
    return user_city or 'Минск'

def detect_category(query: str) -> Optional[str]:
    categories = {
        'концерт': 'Концерты',
        'спектакль': 'Спектакли',
        'кино': 'Кино',
        'выставк': 'Выставки',
        'фестивал': 'Фестивали',
        'квест': 'Квесты',
        'спорт': 'Спорт',
        'детск': 'Детская афиша',
        'обучени': 'Обучение'
    }
    q = query.lower()
    for key, value in categories.items():
        if key in q:
            return value
    return None

def detect_price_filter(query: str) -> Optional[str]:
    q = query.lower()
    if 'бесплатн' in q:
        return 'free'
    elif 'дешев' in q:
        return 'cheap'
    elif 'дорог' in q:
        return 'expensive'
    return None

async def chat_with_groq(query: str, user_id: str, city: Optional[str] = None, offset: int = 0) -> Dict[str, Any]:
    from .search import search_events
    
    dialog_id = await get_or_create_dialog(user_id)
    await save_message(dialog_id, 'user', query)
    
    detected_city = detect_city(query, city)
    category = detect_category(query)
    price_filter = detect_price_filter(query)
    
    search_result = await search_events(query, detected_city, offset, 5, user_id)
    events = search_result.get('results', [])
    
    filters = {"category": category, "price_filter": price_filter}
    
    history = await get_dialog_history(dialog_id)
    history_text = ""
    for msg in history[-5:]:
        role_name = "Пользователь" if msg['role'] == 'user' else "Бот"
        history_text += f"{role_name}: {msg['content']}\n"
    
    events_text = ""
    if events:
        for i, ev in enumerate(events[:5], 1):
            title = ev.get('название', 'Событие')
            venue = ev.get('место', 'Место не указано')
            date = ev.get('дата_начала', 'Дата не указана')
            price = ev.get('цена_мин', 0)
            price_text = f"{price} руб." if price > 0 else "БЕСПЛАТНО!"
            events_text += f"{i}. {title} | {venue} | {date} | {price_text}\n"
    else:
        events_text = "Событий не найдено."
    
    prompt = f"""
История диалога:
{history_text}

Город: {detected_city}
Запрос пользователя: "{query}"
Категория: {category or 'не определена'}

Найденные события:
{events_text}

Задача:
1. Дружелюбно ответь пользователю (2-3 предложения)
2. Если есть события — кратко представь их
3. Если есть бесплатные — подчеркни это 🎉
4. Скажи, что можно сказать "другие" для следующих событий
5. Если событий нет — предложи изменить запрос
6. Если пользователь сказал "другие" - покажи следующие события (offset: {offset})
"""
    
    groq_response = await call_groq(prompt)
    
    if groq_response:
        response = groq_response
    else:
        response = generate_smart_response(query, events, detected_city, filters)
    
    await save_message(dialog_id, 'assistant', response)
    
    return {
        "dialog_id": dialog_id,
        "response": response,
        "events": events,
        "total": search_result.get('total', 0),
        "offset_next": search_result.get('offset_next'),
        "city": detected_city,
        "filters": filters
    }