import os
import asyncio
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message

# কনফিগারেশন ভ্যারিয়েবল
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "0"))
PORT = int(os.environ.get("PORT", 8080))
FQDN = os.environ.get("FQDN", "").rstrip("/")

bot = Client(
    "StreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

routes = web.RouteTableDef()

@routes.get("/")
async def root_route(request):
    return web.Response(text="Server is Live and Streaming Bot is Active!")

@routes.get("/watch/{msg_id}")
async def watch_route(request):
    msg_id = int(request.match_info["msg_id"])
    stream_url = f"{FQDN}/stream/{msg_id}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Video Stream</title>
        <style>
            body {{ margin: 0; background: #000; display: flex; align-items: center; justify-content: center; height: 100vh; }}
            video {{ width: 100%; height: 100%; max-height: 100vh; }}
        </style>
    </head>
    <body>
        <video controls autoplay playsinline controlsList="nodownload">
            <source src="{stream_url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

@routes.get("/stream/{msg_id}")
async def stream_route(request):
    msg_id = int(request.match_info["msg_id"])
    try:
        msg = await bot.get_messages(BIN_CHANNEL, msg_id)
        media = msg.video or msg.document or msg.audio
        if not media:
            return web.Response(status=404, text="Media not found")

        file_size = media.file_size
        range_header = request.headers.get("Range")

        from_bytes = 0
        until_bytes = file_size - 1

        if range_header:
            parts = range_header.replace("bytes=", "").split("-")
            from_bytes = int(parts[0]) if parts[0] else 0
            until_bytes = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        chunk_size = 1024 * 1024  # 1MB chunks
        length = until_bytes - from_bytes + 1

        headers = {
            "Content-Type": getattr(media, "mime_type", "video/mp4"),
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(
            status=206 if range_header else 200,
            headers=headers
        )
        await response.prepare(request)

        async for chunk in bot.stream_media(msg, offset=from_bytes // (1024 * 1024), limit=length):
            await response.write(chunk)

        await response.write_eof()
        return response
    except Exception as e:
        return web.Response(status=500, text=str(e))

@bot.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply_text(
        "👋 স্বাগতম! আমাকে যেকোনো ভিডিও বা ফাইল পাঠান, আমি আপনাকে সরাসরি ওয়েবসাইট এম্বেড ও স্ট্রিমিং লিংক তৈরি করে দেব।"
    )

@bot.on_message(filters.video | filters.document | filters.audio)
async def media_handler(client, message: Message):
    status = await message.reply_text("⏳ প্রসেসিং হচ্ছে, চ্যানেল ফরোয়ার্ড করা হচ্ছে...")
    try:
        forwarded = await message.forward(BIN_CHANNEL)
        msg_id = forwarded.id

        watch_link = f"{FQDN}/watch/{msg_id}"
        stream_link = f"{FQDN}/stream/{msg_id}"

        embed_code = f'&lt;iframe src="{watch_link}" width="100%" height="450" frameborder="0" allowfullscreen&gt;&lt;/iframe&gt;'

        text = (
            f"✅ **আপনার লিংক প্রস্তুত:**\n\n"
            f"🔗 **Web Player Link:**\n`{watch_link}`\n\n"
            f"⚡ **Direct MP4 Stream:**\n`{stream_link}`\n\n"
            f"💻 **Website Embed Code:**\n`{embed_code}`"
        )
        await status.edit_text(text, disable_web_page_preview=True)
    except Exception as e:
        await status.edit_text(f"❌ এরর: {str(e)}")

async def start_services():
    await bot.start()
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Server started on port {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_services())
