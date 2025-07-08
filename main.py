import os
import json
import easyocr
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from datetime import datetime

# إعداد
app = FastAPI()
reader = easyocr.Reader(['en'], gpu=False)
DATA_FILE = "data.json"

# قراءة البيانات القديمة
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# حفظ البيانات الجديدة
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# تحليل صورة واحدة
def analyze_image(image_bytes):
    results = reader.readtext(image_bytes)
    players = []
    for i in range(len(results)):
        text = results[i][1]
        if text.replace(",", "").isdigit():
            if i > 0:
                player_name = results[i - 1][1]
                power = int(text.replace(",", ""))
                players.append({"name": player_name, "power": power})
    return players

# مقارنة بيانات
def compare(old, new):
    comparison = []
    for new_player in new:
        name = new_player["name"]
        new_power = new_player["power"]
        old_power = next((p["power"] for p in old if p["name"] == name), None)
        if old_power is not None:
            diff = new_power - old_power
            percent = round((diff / old_power) * 100, 2) if old_power > 0 else 0
            comparison.append({
                "name": name,
                "old": old_power,
                "new": new_power,
                "diff": diff,
                "percent": percent
            })
    return comparison

# API: رفع صورة جديدة
@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    new_data = analyze_image(image_bytes)
    old_data = load_data()

    comparison = compare(old_data, new_data)

    # تحديث التخزين
    save_data(new_data)

    return JSONResponse(content={
        "timestamp": datetime.utcnow().isoformat(),
        "results": comparison
    })
