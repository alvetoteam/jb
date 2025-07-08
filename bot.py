import discord
import aiohttp
import os
import threading
import easyocr
import json
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime

# === إعداد ديسكورد ===
TOKEN = os.getenv("DISCORD_TOKEN")
OCR_API_URL = "http://localhost:8000/upload"  # لأن FastAPI شغال داخلياً

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === إعداد FastAPI ===
app = FastAPI()
reader = easyocr.Reader(['en'], gpu=False)
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    new_data = analyze_image(image_bytes)
    old_data = load_data()
    comparison = compare(old_data, new_data)
    save_data(new_data)

    return JSONResponse(content={
        "timestamp": datetime.utcnow().isoformat(),
        "results": comparison
    })

# === تشغيل FastAPI في الخلفية ===
def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

api_thread = threading.Thread(target=run_api)
api_thread.start()

# === بوت ديسكورد ===
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.attachments:
        return

    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            await message.channel.send("📷 جارٍ تحليل الصورة...")

            image_bytes = await attachment.read()
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("file", image_bytes, filename=attachment.filename, content_type="image/png")

                try:
                    async with session.post(OCR_API_URL, data=form) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if not results:
                                await message.channel.send("❌ لا يوجد فرق واضح أو بيانات مقارنة.")
                                return

                            msg = "📊 **مقارنة القوة:**\n"
                            for p in results:
                                msg += f"**{p['name']}**\n"
                                msg += f"القديمة: {p['old']:,} | الجديدة: {p['new']:,} | الفرق: {p['diff']:+,} | النسبة: {p['percent']}%\n\n"
                            await message.channel.send(msg)
                        else:
                            await message.channel.send("⚠️ فشل الاتصال بخدمة OCR.")
                except Exception as e:
                    await message.channel.send(f"❌ خطأ داخلي: {e}")

client.run(TOKEN)
