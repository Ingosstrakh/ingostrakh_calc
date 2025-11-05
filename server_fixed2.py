"""
server_fixed4.py — универсальный сервер для проверки расчётов
Совместим с фронтендом v40 (где payload не содержит client_total/server_total).
"""
import os, json, datetime
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import OpenAI

LOG_FILE = "gpt_check_log.json"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1996")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("⚠️ OpenAI init failed:", e)

app = FastAPI(title="Insurance Calculator Checker (server_fixed4)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

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

def save_log(entry):
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try: logs = json.load(f)
                except: logs = []
        logs.append(entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ Log write failed:", e)

def normalize_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Convert both new and old payload formats into standard CheckRequest-like dict."""
    if "client_total" in req and "server_total" in req and "lines" in req:
        return req  # already correct
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

@app.get("/")
async def root():
    return {"status": "ok", "message": "server_fixed4 running"}

@app.post("/check")
async def check(req: Dict[str, Any]):
    norm = normalize_request(req)
    entry = {"timestamp": datetime.datetime.utcnow().isoformat()+"Z", "request": norm}
    gpt_result = call_gpt(norm)
    entry["result"] = gpt_result
    save_log(entry)
    return JSONResponse(content={"ok": True, "data": gpt_result})

@app.get("/admin/logs")
async def admin_logs(password: Optional[str] = Query(None)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not os.path.exists(LOG_FILE):
        return {"logs": []}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        try: logs = json.load(f)
        except: logs = []
    return {"logs": logs}
