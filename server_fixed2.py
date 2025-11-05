import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

# --- Настройка API-ключа ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("❌ Ошибка: переменная окружения OPENAI_API_KEY не установлена!")

client = OpenAI(api_key=api_key)

# --- Инициализация приложения ---
app = FastAPI(title="Calculator Check API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели данных ---
class LineItem(BaseModel):
    label: str
    value: str | float | int
    issum: bool

class CheckRequest(BaseModel):
    client_total: float
    server_total: float
    lines: list[LineItem]

# --- Маршрут проверки ---
@app.post("/check")
async def check_check_post(data: CheckRequest):
    """
    Сравнивает расчёт клиента и расчёт GPT.
    Если GPT возвращает False — результат сохраняется в лог.
    """

    try:
        # Формируем запрос к GPT
        prompt = (
            "Проверь правильность расчета страховой премии по данным клиента.\n"
            f"{json.dumps(data.dict(), ensure_ascii=False, indent=2)}\n\n"
            "Ответь строго в формате JSON, без комментариев:\n"
            "{ \"match\": true или false, \"reason\": \"пояснение\" }"
        )

        print("\n🔹 Запрос к GPT:")
        print(prompt)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты страховой эксперт. Проверяй точность расчета."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw_reply = response.choices[0].message.content.strip()
        print("\n🔸 Ответ GPT:", raw_reply)

        # Безопасный парсинг JSON
        try:
            gpt_reply = json.loads(raw_reply)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="GPT вернул некорректный JSON")

        match = gpt_reply.get("match", False)
        reason = gpt_reply.get("reason", "Без причины")

        # Логирование ошибок GPT
        if not match:
            with open("calc_check_log.txt", "a", encoding="utf-8") as f:
                f.write(f"Ошибка проверки:\n{json.dumps(data.dict(), ensure_ascii=False)}\nПричина: {reason}\n\n")

        return {"match": match, "reason": reason}

    except Exception as e:
        print("❌ Ошибка сервера:", e)
        raise HTTPException(status_code=500, detail=str(e))
