\# Event Picker 🎫



Приложение для поиска событий с AI-помощником.



\## 🚀 Функционал



\- 🔐 Регистрация и вход

\- 🤖 Чат с AI (Groq API)

\- 🔍 Поиск событий (концерты, театр, спорт, кино, выставки, квесты)

\- ❤️ Избранное

\- 👤 Личный кабинет

\- 🌍 3 языка: русский, белорусский, английский

\- 🗺️ Карта OpenStreetMap

\- 📅 Парсинг событий раз в неделю



\## 🛠️ Стек



\*\*Backend:\*\* FastAPI, PostgreSQL, Redis, Groq API  

\*\*Frontend:\*\* React, i18next, Axios  

\*\*DevOps:\*\* Docker, Nginx



\## 📦 Запуск



```bash

\# Разработка

docker-compose -f docker-compose.dev.yml up -d



\# Продакшен

docker-compose -f docker-compose.prod.yml up -d



\## 🔑 Переменные окружения (.env)

env

DATABASE\_URL=postgresql://postgres:123456@postgres:5432/events\_db

REDIS\_URL=redis://redis:6379

GROQ\_API\_KEY=ваш\_ключ

JWT\_SECRET=ваш\_секрет



\##📂 Структура

text

backend/     # FastAPI

frontend/    # React

nginx/       # Nginx конфиг

docker-compose.dev.yml

docker-compose.prod.yml

