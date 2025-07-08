import discord
import aiohttp
import os

TOKEN = os.getenv("DISCORD_TOKEN")
OCR_API = os.getenv("OCR_API_URL")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

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

                async with session.post(OCR_API, data=form) as resp:
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
