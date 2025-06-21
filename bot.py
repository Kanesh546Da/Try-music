import os
import asyncio
import pafy
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pytgcalls import PyTgCalls, idle
from pytgcalls.types.input_stream import InputStream, InputAudioStream
from collections import deque

web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Telegram Music Bot is Running (Render)"

def run_web():
    web.run(host="0.0.0.0", port=8080)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)
queues = {}

def get_audio_link(url):
    try:
        video = pafy.new(url)
        best = video.getbestaudio()
        return best.url, video.title
    except Exception as e:
        return None, str(e)

async def stream_next(chat_id):
    queue = queues.get(chat_id)
    if not queue:
        await pytgcalls.leave_group_call(chat_id)
        return
    url, title = queue[0]
    await pytgcalls.join_group_call(
        chat_id,
        InputStream(InputAudioStream(url))
    )

@app.on_message(filters.command("play") & filters.group)
async def play_handler(_, msg):
    chat_id = msg.chat.id
    if len(msg.command) < 2:
        return await msg.reply("❌ Usage: `/play <YouTube URL>`")
    url, title = get_audio_link(msg.command[1])
    if not url:
        return await msg.reply(f"❌ Failed: {title}")
    if chat_id not in queues:
        queues[chat_id] = deque()
    queues[chat_id].append((url, title))
    await msg.reply(f"🎶 Queued: **{title}**")
    if len(queues[chat_id]) == 1:
        await stream_next(chat_id)

@app.on_message(filters.command("skip") & filters.group)
async def skip_handler(_, msg):
    q = queues.get(msg.chat.id)
    if q:
        q.popleft()
        await msg.reply("⏭ Skipped.")
        await stream_next(msg.chat.id)

@app.on_message(filters.command("pause") & filters.group)
async def pause_handler(_, msg):
    await pytgcalls.pause_stream(msg.chat.id)
    await msg.reply("⏸ Paused.")

@app.on_message(filters.command("resume") & filters.group)
async def resume_handler(_, msg):
    await pytgcalls.resume_stream(msg.chat.id)
    await msg.reply("▶️ Resumed.")

@app.on_message(filters.command("stop") & filters.group)
async def stop_handler(_, msg):
    queues.pop(msg.chat.id, None)
    await pytgcalls.leave_group_call(msg.chat.id)
    await msg.reply("⏹ Stopped & queue cleared.")

@app.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, msg):
    q = queues.get(msg.chat.id, [])
    if not q:
        return await msg.reply("Queue is empty.")
    text = "\n".join(f"{i+1}. {t}" for i, (_, t) in enumerate(q))
    await msg.reply("🎵 Queue:\n" + text)

async def main():
    await app.start()
    await pytgcalls.start()
    print("🎶 Bot started!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    Thread(target=run_web).start()
    asyncio.run(main())
    
