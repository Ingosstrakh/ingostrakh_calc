import os
import json
import re
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from difflib import SequenceMatcher
from paddleocr import PaddleOCR
from PIL import Image

APP_DIR = os.path.dirname(os.path.abspath(__file__))
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

# ------------------- OCR -------------------
log("Loading PaddleOCR model...")
ocr = PaddleOCR(use_angle_cls=True, lang="ru")
log("PaddleOCR loaded.")

@app.post("/ocr")
def ocr_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "Файл не получен"}), 400

    file = request.files["file"]
    filepath = "/tmp/upload.png"
    file.save(filepath)

    # ❗ cls=True УДАЛЕНО (ВОТ ЭТО И ЛЕЧИТ ОШИБКУ)
    result = ocr.ocr(filepath)

    text = "\n".join([line[1][0] for line in result[0]])

    return jsonify({"ok": True, "text": text})


# ------------------- PARSER -------------------

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
    return res

@app.get("/")
def root():
    return jsonify({"ok": True, "msg": "Parser server v6 работает"})

@app.post("/parse")
def parse_endpoint():
    text = ""
    try:
        j = request.get_json(force=True, silent=True)
        if isinstance(j, dict):
            text = j.get("text", "") or j.get("message", "")
    except:
        pass

    if not text:
        text = request.data.decode("utf-8") if request.data else ""

    if not text.strip():
        return jsonify({"ok": False, "error": "Empty text"}), 400

    parsed = parse_text(text)
    return jsonify({"ok": True, "data": parsed})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
