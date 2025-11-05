from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Union
from openai import OpenAI

# Инициализация FastAPI
app = FastAPI(title="Ingos Insurance API")

# Разрешаем запросы с любых источников (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # при желании можешь ограничить доменом сайта
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация клиента OpenAI
client = OpenAI(api_key="YOUR_OPENAI_API_KEY_HERE")  # вставь свой ключ

# --- МОДЕЛИ ---
class LineItem(BaseModel):
    label: str
    value: Union[str, float, int]  # теперь можно и числа, и текст
    issum: bool


class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: List[LineItem]


# --- ЭНДПОИНТЫ ---
@app.get("/")
async def root():
    """Тестовый маршрут для проверки статуса API"""
    return JSONResponse(
        content={"status": "ok", "message": "API запущен и готов принимать запросы"}
    )


@app.post("/check")
async def check(request: CheckRequest):
    """
    Проверка корректности расчёта страховой суммы.
    GPT сверяет данные клиента и сервера.
    """
    try:
        # Формируем описание задачи для GPT
        prompt = (
            f"Проверь совпадение итогов. "
            f"Итог по клиенту: {request.client_total}. "
            f"Итог по серверу: {request.server_total}. "
            f"Данные по позициям: {', '.join([f'{l.label}={l.value}' for l in request.lines])}. "
            f"Ответь JSONом вида {{'match': true/false, 'reason': 'пояснение'}}."
        )

        # Отправляем запрос в OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        answer = response.choices[0].message.content.strip()
        return {"success": True, "response": answer}

    except Exception as e:
        return {"success": False, "error": str(e)}
