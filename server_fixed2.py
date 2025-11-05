import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

app = FastAPI()

# ✅ Разрешаем фронтенд-запросы откуда угодно (или укажи свой домен)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно ограничить ["https://твоя_страница.html"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Проверка на запуск
@app.get("/")
async def root():
    return {"status": "OK", "message": "API запущен и готов принимать запросы!"}

# ✅ Проверка ключа OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("⚠️ ВНИМАНИЕ: переменная OPENAI_API_KEY не установлена!")

# ✅ Модель для тела запроса
class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: list

@app.post("/check")
async def check(request: CheckRequest):
    try:
        # Пример логики проверки (вместо OpenAI)
        if request.client_total > request.server_total:
            return {
                "match": False,
                "reason": f"Страховая сумма клиента ({request.client_total}) превышает общую сумму ({request.server_total})"
            }

        # Если всё ок, обращаемся к OpenAI (пример запроса)
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник по страховым расчётам."},
                {"role": "user", "content": f"Проверь корректность расчёта: {request.dict()}"}
            ]
        )

        answer = completion.choices[0].message.content
        return {"match": True, "ai_response": answer}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"error": str(e)}

