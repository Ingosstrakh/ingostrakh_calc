# server_fixed4.py
"""
Updated parser server (server_fixed4.py)
- /           GET  -> {"ok": True, "msg": ...}
- /check      GET  -> simple health check
- /parse      POST -> accepts JSON {"text": "..."} or raw body
- /training   GET  -> returns recent training examples
- /logs       GET  -> returns server log file (if exists)
- saves training examples to training_data.json
- CORS enabled
"""

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

# Ensure training file exists
if not os.path.exists(TRAIN_FILE):
    try:
        with open(TRAIN_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        log("Created training_data.json")
    except Exception as e:
        log(f"Error creating training_data.json: {e}")

def load_training():
    try:
        with open(TRAIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def append_training(record):
    arr = load_training()
    arr.append(record)
    try:
        with open(TRAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Error writing training file: {e}")

# --- parsing helpers (kept same logic as previous) ---
BANKS = [
    "альфабанк","альфа","сбербанк","сбер","втб","убрир","юникредит",
    "тинькофф","ренессанс","газпром","дом рф","домрф","абсолют"
]

PROP_TYPES = ["квартира", "дом", "апарт", "дача", "коттедж", "таунхаус"]
MATERIALS = ["кирпич", "жб", "бетон", "дерев", "бревно", "пеноблок"]
INSURANCE_KEYWORDS = {
    "life": ["жизн", "страховка жизни", "жизнь"],
    "property": ["имуще", "имущ", "квар", "дом", "страхование квартиры", "страхование имущества"],
    "title": ["титул", "title"]
}
GENDER_PATTERNS = {
    "male": ["муж", "мужч", "мужчина"],
    "female": ["жен", "жена", "женщ"]
}

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def find_bank(text):
    t = text.lower()
    for b in BANKS:
        if b in t:
            return b
    tokens = re.findall(r"[а-яa-z0-9]+", t)
    for tok in tokens:
        for b in BANKS:
            if similar(tok, b) > 0.8:
                return b
    return ""

def find_loan(text):
    t = text.replace("\xa0"," ")
    m = re.search(r"(\d{1,3}(?:[ \u00A0]\d{3})+|\d{4,})", t)
    if m:
        s = m.group(1)
        num = int(re.sub(r"[^\d]", "", s))
        return num
    m2 = re.search(r"(\d+[.,]?\d*)\s*млн", t)
    if m2:
        return int(float(m2.group(1).replace(",", ".")) * 1_000_000)
    return None

def find_rate(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if m:
        return float(m.group(1).replace(",", "."))
    m2 = re.search(r"\b(\d+[.,]\d+)\b", text)
    if m2 and 1 <= float(m2.group(1).replace(",", ".")) <= 30:
        return float(m2.group(1).replace(",", "."))
    return None

def find_birth(text):
    m = re.search(r"(\d{2}[./-]\d{2}[./-]\d{4})", text)
    if m:
        return m.group(1)
    return ""

def find_year(text):
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        return int(m.group(0))
    return None

def find_gender(text):
    t = text.lower()
    for g, pats in GENDER_PATTERNS.items():
        for p in pats:
            if p in t:
                return g
    return ""

def find_prop_type(text):
    t = text.lower()
    for p in PROP_TYPES:
        if p in t:
            return "Квартира" if "квар" in p else ("Дом" if "дом" in p or "дач" in p else p)
    return ""

def find_material(text):
    t = text.lower()
    for m_ in MATERIALS:
        if m_ in t:
            return m_
    return ""

def find_insurance(text):
    out = []
    t = text.lower()
    for kind, keys in INSURANCE_KEYWORDS.items():
        for k in keys:
            if k in t:
                out.append(kind)
                break
    return out

def parse_text(text):
    res = {
        "bank": "",
        "loan": None,
        "rate": None,
        "gender": "",
        "birth": "",
        "propType": "",
        "material": "",
        "year": None,
        "insurance": []
    }

    training = load_training()
    known_banks = set()
    for rec in training:
        parsed = rec.get("parsed") or {}
        b = parsed.get("bank")
        if b:
            known_banks.add(b.lower())

    t_lower = text.lower()
    for b in known_banks:
        if b and b in t_lower:
            res["bank"] = b
            break

    if not res["bank"]:
        res["bank"] = find_bank(text)

    res["loan"] = find_loan(text)
    res["rate"] = find_rate(text)
    res["gender"] = find_gender(text)
    res["birth"] = find_birth(text)
    res["year"] = find_year(text)
    res["propType"] = find_prop_type(text)
    res["material"] = find_material(text)
    res["insurance"] = find_insurance(text)

    if isinstance(res["loan"], int) and res["loan"] < 1000:
        res["loan"] = None

    return res

# --- endpoints ---
@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "msg": "Parser server alive"})

@app.route("/check", methods=["GET"])
def check():
    # lightweight check to confirm server and training file access
    ok = True
    count = 0
    try:
        arr = load_training()
        count = len(arr)
    except Exception:
        ok = False
    return jsonify({"ok": ok, "training_examples": count})

@app.route("/parse", methods=["POST"])
def parse_endpoint():
    text = ""
    try:
        j = request.get_json(force=True, silent=True)
        if isinstance(j, dict):
            text = j.get("text", "") or j.get("message", "") or ""
    except Exception:
        text = ""

    if not text:
        try:
            text = request.data.decode("utf-8") if request.data else ""
        except Exception:
            text = ""

    if not text:
        return jsonify({"ok": False, "error": "Empty text"}), 400

    t0 = time.time()
    parsed = parse_text(text)
    elapsed = time.time() - t0

    record = {
        "text": text,
        "parsed": parsed,
        "ts": datetime.utcnow().isoformat()
    }
    try:
        append_training(record)
    except Exception as e:
        log(f"Error append training: {e}")

    log(f"/parse processed in {elapsed:.3f}s parsed={parsed}")
    return jsonify({"ok": True, "data": parsed})

@app.route("/training", methods=["GET"])
def get_training():
    arr = load_training()
    return jsonify({"ok": True, "count": len(arr), "examples": arr[-200:]})

@app.route("/logs", methods=["GET"])
def get_logs():
    try:
        return send_file(LOG_FILE)
    except Exception:
        return jsonify({"ok": False, "error": "no logs"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"
    log(f"Starting server_fixed4 on {host}:{port}")
    app.run(host=host, port=port)
