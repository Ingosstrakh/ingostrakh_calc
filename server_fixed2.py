from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
import os

# Инициализация клиента OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Инициализация FastAPI
app = FastAPI()

# Разрешаем CORS (иначе браузер блокирует запросы с HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # можно указать конкретный домен, например твой фронт
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- МОДЕЛИ ----------
class LineItem(BaseModel):
    label: str
    value: float
    issum: bool


class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: list[LineItem]


# ---------- МАРШРУТЫ ----------
@app.get("/")
async def root():
    """Проверка, что сервер запущен"""
    return JSONResponse(
        content={"status": "ok", "message": "API запущен и готов принимать запросы"}
    )


@app.post("/check")
async def check(request: CheckRequest):
    """Проверка корректности расчёта страховой суммы через GPT"""
    try:
        prompt = (
            f"Проверь совпадение итогов. "
            f"Итог по клиенту: {request.client_total}. "
            f"Итог по серверу: {request.server_total}. "
            f"Данные по позициям: {', '.join([f'{l.label}={l.value}' for l in request.lines])}. "
            f"Ответь JSONом вида {{'match': true/false, 'reason': 'пояснение'}}."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # можно заменить на gpt-3.5-turbo при необходимости
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        answer = response.choices[0].message.content.strip()
        return {"success": True, "response": answer}

    except Exception as e:
        return {"success": False, "error": str(e)}
