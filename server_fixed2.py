from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import openai

# Инициализация приложения
app = FastAPI()

# ✅ Разрешаем CORS (чтобы браузер мог обращаться к серверу Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # можно указать конкретный домен, например ["https://ingostrakh-calc.onrender.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Инициализация OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Проверочная модель данных
class Line(BaseModel):
    label: str
    value: float | int | str
    issum: bool

class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: list[Line]

@app.post("/check")
async def check_data(data: CheckRequest):
    """
    Проверка корректности данных страхового расчёта.
    GPT анализирует параметры и сообщает, совпадает ли сумма клиента с расчётной.
    """

    if not openai.api_key:
        return {"error": "Переменная окружения OPENAI_API_KEY не установлена!"}

    # Формируем текст запроса к GPT
    user_message = f"""
    Проверь данные страхового расчёта.
    Общая сумма по серверу: {data.server_total}
    Общая сумма по клиенту: {data.client_total}
    Параметры:
    {data.lines}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты проверяешь корректность страхового расчёта."},
                {"role": "user", "content": user_message},
            ],
        )

        answer = response.choices[0].message["content"]

        return {"match": "ошибок не найдено" not in answer.lower(), "gpt_response": answer}

    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    return {"status": "OK", "message": "API запущен и готов принимать запросы!"}
