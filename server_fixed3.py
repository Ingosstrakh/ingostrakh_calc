import os
import json
import re
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from difflib import SequenceMatcher

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_FILE = os.path.join(APP_DIR, "training_data.json")
LOG_FILE = os.path.join(APP_DIR, "server.log")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def log(msg):
    line = f"{datetime.utcnow().isoformat()} {msg}\n"
    print(line.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

# ------------------- Настройки -------------------
BANKS = [
    "альфабанк", "альфа", "сбербанк", "сбер", "втб", "убрир",
    "юникредит", "тинькофф", "ренессанс", "газпром", "дом рф",
    "домрф", "абсолют", "россельхоз", "рсхб", "псб", "уралсиб"
]

BANK_MAP = {
    "сбер": "SBERBANK",
    "сбербанк": "SBERBANK",
    "втб": "VTB",
    "дом рф": "DOMRF",
    "домрф": "DOMRF",
    "россельхоз": "RSHB",
    "рсхб": "RSHB",
    "альфа": "ALFA",
    "альфабанк": "ALFA",
    "псб": "PSB",
    "уралсиб": "URAL",
}

MATERIAL_MAP = {
    "дерев": "деревянный",
    "брус": "деревянный",
    "брев": "деревянный",
    "кирп": "каменный",
    "бетон": "каменный",
    "жб": "каменный",
    "блок": "каменный",
}

PROP_TYPES = ["квартира", "дом", "дача", "таунхаус", "коттедж", "апарт"]

# ------------------- Основные функции -------------------
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def normalize_bank(name: str):
    if not name:
        return ""
    name = name.lower().strip()
    return BANK_MAP.get(name, name.upper())

def find_bank(text):
    t = text.lower()
    for b in BANKS:
        if b in t:
            return normalize_bank(b)
    tokens = re.findall(r"[а-яa-z0-9]+", t)
    for tok in tokens:
        for b in BANKS:
            if similar(tok, b) > 0.8:
                return normalize_bank(b)
    return ""

def find_loan(text):
    m = re.search(r"(\d{1,3}(?:[ \u00A0]\d{3})+|\d{5,})", text)
    if m:
        s = m.group(1)
        num = int(re.sub(r"[^\d]", "", s))
        return num
    m2 = re.search(r"(\d+[.,]?\d*)\s*млн", text)
    if m2:
        return int(float(m2.group(1).replace(",", ".")) * 1_000_000)
    return None

def find_birth(text):
    m = re.search(r"(\d{2}[./-]\d{2}[./-]\d{4})", text)
    return m.group(1) if m else ""

def find_rate(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None

def find_material(text):
    t = text.lower()
    for k, v in MATERIAL_MAP.items():
        if k in t:
            return v
    return ""

def find_prop_type(text):
    t = text.lower()
    for p in PROP_TYPES:
        if p in t:
            return "Дом" if "дом" in p else "Квартира"
    return ""

def find_gender(text):
    t = text.lower()
    if "муж" in t:
        return "Мужчина"
    if "жен" in t:
        return "Женщина"
    return ""

def parse_text(text):
    text = text or ""
    res = {
        "bank": find_bank(text),
        "loan": find_loan(text),
        "rate": find_rate(text),
        "birth": find_birth(text),
        "gender": find_gender(text),
        "propType": find_prop_type(text),
        "material": find_material(text),
    }

    # Если дом указан, но не найден материал — пытаемся угадать по словам
    if res["propType"] == "Дом" and not res["material"]:
        if "дер" in text.lower() or "брус" in text.lower():
            res["material"] = "деревянный"
        elif "кирп" in text.lower() or "жб" in text.lower() or "бетон" in text.lower():
            res["material"] = "каменный"

    return res

# ------------------- Flask маршруты -------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "msg": "Parser server v5 работает"})

@app.route("/parse", methods=["POST"])
def parse_endpoint():
    text = ""
    try:
        j = request.get_json(force=True, silent=True)
        if isinstance(j, dict):
            text = j.get("text", "") or j.get("message", "")
    except Exception:
        pass

    if not text:
        text = request.data.decode("utf-8") if request.data else ""

    if not text.strip():
        return jsonify({"ok": False, "error": "Empty text"}), 400

    t0 = time.time()
    parsed = parse_text(text)
    elapsed = time.time() - t0
    log(f"/parse processed in {elapsed:.3f}s -> {parsed}")
    return jsonify({"ok": True, "data": parsed})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"
    log(f"Starting server_fixed5 on {host}:{port}")
    app.run(host=host, port=port)



from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="ru")

@app.post("/ocr")
def ocr_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "Файл не получен"}), 400
    file = request.files["file"]
    filename = "/tmp/upload.png"
    file.save(filename)
    result = ocr.ocr(filename, cls=True)
    text = "\n".join([line[1][0] for line in result[0]])
    return jsonify({"ok": True, "text": text})
