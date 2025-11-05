# server_fixed2.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os

# Инициализация FastAPI
app = FastAPI()

# Разрешаем CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация клиента OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Модель входных данных
class LineItem(BaseModel):
    label: str
    value: float | str
    issum: bool

class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: list[LineItem]

@app.get("/")
def root():
    return {"status": "ok", "message": "API запущен и готов принимать запросы"}

@app.post("/check")
async def check(request: CheckRequest):
    """
    Проверка корректности расчёта страховой суммы.
    Отправляет данные модели GPT и получает логическую проверку.
    """
    try:
        # Формируем описание для GPT
        prompt = (
            f"Проверь совпадение итогов. "
            f"Итог по клиенту: {request.client_total}. "
            f"Итог по серверу: {request.server_total}. "
            f"Данные по позициям: {', '.join([f'{l.label}={l.value}' for l in request.lines])}. "
            f"Ответь JSONом вида {{'match': true/false, 'reason': 'пояснение'}}."
        )

        # Запрос к модели GPT-4 или GPT-3.5
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # можешь поменять на gpt-3.5-turbo, если нет доступа
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        answer = response.choices[0].message.content.strip()
        return {"success": True, "response": answer}

    except Exception as e:
        return {"success": False, "error": str(e)}

