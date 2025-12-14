import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from difflib import SequenceMatcher
from paddleocr import PaddleOCR

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# -------- LOG --------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(APP_DIR, "server.log")

def log(msg):
    line = f"{datetime.utcnow().isoformat()} {msg}"
    print(line)

# -------- OCR --------
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

    # ❗ cls=True УДАЛЕНО
    result = ocr.ocr(filepath)

    text = "\n".join([line[1][0] for line in result[0]])

    return jsonify({"ok": True, "text": text})


# -------- PARSER --------

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
    return ""

@app.get("/")
def root():
    return jsonify({"ok": True, "msg": "Parser server + OCR работает"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
