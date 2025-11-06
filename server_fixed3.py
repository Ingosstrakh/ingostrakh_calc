# server_fixed3.py
"""
server_fixed3.py
Fast Flask parser for calculator /parse endpoint.
- No external API keys
- Saves training examples to training_data.json (self-learning)
- Uses fallback regexp + keyword extraction
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
CORS(app)

# --- utility: logging ---
def log(msg):
    line = f"{datetime.utcnow().isoformat()} {msg}\n"
    print(line.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

# --- ensure training file exists ---
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

# --- helper parsers ---
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
    # direct contains
    for b in BANKS:
        if b in t:
            return b
    # fallback: try tokens with similarity
    tokens = re.findall(r"[а-яa-z0-9]+", t)
    for tok in tokens:
        for b in BANKS:
            if similar(tok, b) > 0.8:
                return b
    return ""

def find_loan(text):
    # Look for "3 588 000", "3588000", "3.588.000", "3 588к", "3.5 млн"
    t = text.replace("\xa0"," ")
    m = re.search(r"(\d{1,3}(?:[ \u00A0]\d{3})+|\d{4,})", t)
    if m:
        s = m.group(1)
        num = int(re.sub(r"[^\d]", "", s))
        return num
    # million
    m2 = re.search(r"(\d+[.,]?\d*)\s*млн", t)
    if m2:
        return int(float(m2.group(1).replace(",", ".")) * 1_000_000)
    return None

def find_rate(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if m:
        return float(m.group(1).replace(",", "."))
    # sometimes written "5.5%" or "5,5"
    m2 = re.search(r"\b(\d+[.,]\d+)\b", text)
    if m2 and 1 <= float(m2.group(1).replace(",", ".")) <= 30:
        return float(m2.group(1).replace(",", "."))
    return None

def find_birth(text):
    m = re.search(r"(\d{2}[./-]\d{2}[./-]\d{4})", text)
    if m:
        return m.group(1)
    # year-month-day possibilities
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
    for m in MATERIALS:
        if m in t:
            return m
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

# core parse function using local heuristics and training hints
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

    # try to use training examples to detect bank names or synonyms
    training = load_training()
    # collect bank names from training
    known_banks = set()
    for rec in training:
        parsed = rec.get("parsed") or {}
        b = parsed.get("bank")
        if b:
            known_banks.add(b.lower())
    # first, find bank using known_banks
    t_lower = text.lower()
    for b in known_banks:
        if b and b in t_lower:
            res["bank"] = b
            break

    # fallback to builtin bank list
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

    # normalization: make sure types are simple
    if isinstance(res["loan"], int) and res["loan"] < 1000:
        # probably not a loan, ignore
        res["loan"] = None

    return res

# --- endpoints ---
@app.route("/")
def root():
    return jsonify({"ok": True, "msg": "Parser server alive"})

@app.route("/parse", methods=["POST"])
def parse_endpoint():
    try:
        j = request.get_json(force=True)
        text = j.get("text", "") if isinstance(j, dict) else ""
    except Exception:
        text = request.data.decode("utf-8") if request.data else ""

    if not text:
        return jsonify({"ok": False, "error": "Empty text"}), 400

    t0 = time.time()
    parsed = parse_text(text)
    elapsed = time.time() - t0

    # save training record (text + parsed + timestamp)
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
    # return last 200 examples only
    return jsonify({"ok": True, "count": len(arr), "examples": arr[-200:]})

@app.route("/logs", methods=["GET"])
def get_logs():
    try:
        return send_file(LOG_FILE)
    except Exception:
        return jsonify({"ok": False, "error": "no logs"}), 404

# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"
    log(f"Starting server_fixed3 on {host}:{port}")
    app.run(host=host, port=port)
