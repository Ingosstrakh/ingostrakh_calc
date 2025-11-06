"""
server_fixed2.py
Версия с поддержкой /parse (GPT-5) для автоматического распознавания текста клиентов.
Остальные маршруты ("/check", "/admin/logs") не изменены.
"""

import os
import json
import datetime
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI

# ======================================================
# 🧠 НАСТРОЙКИ
# ======================================================
LOG_FILE = "gpt_check_log.json"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1996")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация клиента OpenAI
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialized")
    except Exception as e:
        print("⚠️ OpenAI init failed:", e)

app = FastAPI(title="Ingosstrakh Calculator Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ======================================================
# 📦 МОДЕЛИ ДАННЫХ
# ======================================================

class LineItem(BaseModel):
    label: str
    value: Union[str, float, int, None] = None
    isSum: Optional[bool] = None
    issum: Optional[bool] = None

class CheckRequest(BaseModel):
    client_total: Optional[float] = None
    server_total: Optional[float] = None
    lines: Optional[List[LineItem]] = None
    client_debug: Optional[Dict[str, Any]] = None


# ======================================================
# 🧩 УТИЛИТЫ
# ======================================================

def save_log(entry):
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except:
                    logs = []
        logs.append(entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ Log write failed:", e)


def normalize_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Приводит payload к стандартному виду CheckRequest."""
    if "client_total" in req and "server_total" in req and "lines" in req:
        return req  # формат уже нормализован
    dbg = req.get("client_debug") or {}
    lines = dbg.get("lines") or []
    client_total = 0.0
    for it in lines:
        if not it.get("isSum") and isinstance(it.get("value"), (int, float)):
            client_total += it["value"]
    return {
        "client_total": float(client_total),
        "server_total": float(client_total),
        "lines": lines,
        "client_debug": dbg
    }


def call_gpt(payload):
    """Вспомогательная функция проверки расчёта через GPT-4o-mini."""
    if client is None:
        return {"error": "OpenAI client not initialized (OPENAI_API_KEY missing)."}
    prompt = (
        "Ты эксперт по страховым расчетам. Проверь совпадают ли итоги расчета.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Ответь строго JSON: {\"match\": true|false, \"reason\": \"...\"}"
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Ты эксперт по страхованию."},
                      {"role": "user", "content": prompt}],
            temperature=0
        )
        raw = resp.choices[0].message.content
        try:
            return {"ok": True, "parsed": json.loads(raw)}
        except Exception:
            import re
            m = re.search(r'\{.*\}', raw, flags=re.S)
            if m:
                return {"ok": True, "parsed": json.loads(m.group(0))}
            return {"ok": False, "raw": raw}
    except Exception as e:
        return {"error": str(e)}


# ======================================================
# 🌐 МАРШРУТЫ API
# ======================================================

@app.get("/")
async def root():
    return {"status": "ok", "message": "server_fixed2 running"}


@app.post("/check")
async def check(req: Dict[str, Any]):
    """Проверка расчёта через GPT-4o-mini (осталось как было)."""
    norm = normalize_request(req)
    entry = {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "request": norm}
    gpt_result = call_gpt(norm)
    entry["result"] = gpt_result
    save_log(entry)
    return JSONResponse(content={"ok": True, "data": gpt_result})


@app.get("/admin/logs")
async def admin_logs(password: Optional[str] = Query(None)):
    """Просмотр логов (доступ с паролем)."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not os.path.exists(LOG_FILE):
        return {"logs": []}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        try:
            logs = json.load(f)
        except:
            logs = []
    return {"logs": logs}


# ======================================================
# 🧠 НОВЫЙ /parse — распознаёт текст клиента через GPT-5
# ======================================================

MANUAL_RATE_BANKS = ["альфа", "альфабанк", "альфа банк", "убрир", "у б р и р", "ubrir"]

@app.post("/parse")
async def parse_text(req: Request):
    """Распознаёт текст клиента и возвращает структурированный JSON."""
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized")

    try:
        data = await req.json()
        text = data.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Нет текста")

        prompt = f"""
Ты работаешь в страховом калькуляторе. 
Из текста клиента выдели строго следующие данные:
- банк (bank)
- сумму кредита (loan)
- пол ("male" или "female")
- дату рождения (birth, формат YYYY-MM-DD)
- тип недвижимости (propType: house, apartment, townhouse)
- материал (material: stone, wood, gas)
- год постройки (year)
Если банк в списке [{', '.join(MANUAL_RATE_BANKS)}], то также найди процент (rate, float).
Игнорируй всё остальное: "жизнь", "имущ", "газ", "ип", "гп", "скидка", "страховка" и т.п.
Ответь строго JSON без комментариев и текста.
Пример:
{{
  "bank": "Альфа-Банк",
  "loan": 3588000,
  "gender": "male",
  "birth": "1989-02-02",
  "propType": "apartment",
  "material": "stone",
  "year": 2025,
  "rate": 6.0
}}

Текст клиента:
{text}
"""

        resp = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        raw = resp.choices[0].message.content.strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            return JSONResponse(
                content={"error": "GPT-5 вернул невалидный JSON", "raw": raw},
                status_code=500
            )

        return JSONResponse(content=parsed)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
