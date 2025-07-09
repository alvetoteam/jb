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

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === FastAPI setup ===
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

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    new_data = analyze_image(image_bytes)
    return JSONResponse(content={
        "timestamp": datetime.utcnow().isoformat(),
        "raw": new_data  # نرجع البيانات بدون مقارنة
    })

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

api_thread = threading.Thread(target=run_api)
api_thread.start()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.attachments:
        return

    all_new_data = []

    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            await message.channel.send(f"📷 تحليل الصورة: `{attachment.filename}`...")

            image_bytes = await attachment.read()
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("file", image_bytes, filename=attachment.filename, content_type="image/png")

                try:
                    async with session.post("http://localhost:8000/upload", data=form) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            players = data.get("raw", [])
                            all_new_data.extend(players)
                        else:
                            await message.channel.send(f"⚠️ فشل في تحليل: {attachment.filename}")
                except Exception as e:
                    await message.channel.send(f"❌ خطأ: {e}")

    if not all_new_data:
        await message.channel.send("❌ لم يتم العثور على بيانات.")
        return

    # دمج اللاعبين
    merged = {}
    for player in all_new_data:
        name = player["name"]
        power = player["power"]
        if name in merged:
            merged[name] += power
        else:
            merged[name] = power

    # مقارنة مع القديمة
    old_data = load_data()
    comparison = []
    for name, new_power in merged.items():
        old_power = next((p["power"] for p in old_data if p["name"] == name), 0)
        diff = new_power - old_power
        percent = round((diff / old_power) * 100, 2) if old_power > 0 else 0
        comparison.append({
            "name": name,
            "old": old_power,
            "new": new_power,
            "diff": diff,
            "percent": percent
        })

    # حفظ البيانات الجديدة
    save_data([{"name": name, "power": power} for name, power in merged.items()])

    # إرسال الرد
    msg = "📊 **مقارنة القوة بعد دمج الصور:**\n"
    for p in comparison:
        msg += f"**{p['name']}**\n"
        msg += f"القديمة: {p['old']:,} | الجديدة: {p['new']:,} | الفرق: {p['diff']:+,} | النسبة: {p['percent']}%\n\n"
    await message.channel.send(msg)

client.run(TOKEN)
