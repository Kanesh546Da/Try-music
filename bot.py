import os
import asyncio
import pafy
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pytgcalls import PyTgCalls, idle, StreamType
from pytgcalls.types.input_stream import InputStream, InputAudioStream
from collections import deque

# =================== Flask Dummy Web Server (for Render) ===================

web = Flask(__name__)

@web.route("/")
def home():
    return "🎵 Telegram Music Bot is Running on Render!"

def run_web():
    web.run(host="0.0.0.0", port=8080)

# =================== Bot Configuration ===================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)
queues = {}

# =================== Get Audio Link from YouTube URL ===================

def get_audio_link(url):
    try:
        video = pafy.new(url)
        best_audio = video.getbestaudio()
        return best_audio.url, video.title
    except Exception as e:
        return None, str(e)

# =================== Stream Control ===================

async def stream_next(chat_id):
    queue = queues.get(chat_id)
    if not queue:
        await pytgcalls.leave_group_call(chat_id)
        return

    url, title = queue[0]
    await pytgcalls.join_group_call(
        chat_id,
        InputStream(InputAudioStream(url)),
        stream_type=StreamType().local_stream
    )

# =================== Bot Command Handlers ===================

@app.on_message(filters.command("play") & filters.group)
async def play_handler(_, msg):
    chat_id = msg.chat.id
    if len(msg.command) < 2:
        return await msg.reply("❌ Usage: `/play <YouTube URL>`")

    query = msg.command[1]
    url, title = get_audio_link(query)

    if not url:
        return await msg.reply(f"❌ Failed to fetch audio: {title}")

    if chat_id not in queues:
        queues[chat_id] = deque()
    queues[chat_id].append((url, title))

    await msg.reply(f"🎶 Queued: **{title}**")

    if len(queues[chat_id]) == 1:
        await stream_next(chat_id)

@app.on_message(filters.command("skip") & filters.group)
async def skip_handler(_, msg):
    chat_id = msg.chat.id
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].popleft()
        await msg.reply("⏭ Skipped current song.")
        await stream_next(chat_id)

@app.on_message(filters.command("pause") & filters.group)
async def pause_handler(_, msg):
    await pytgcalls.pause_stream(msg.chat.id)
    await msg.reply("⏸ Paused playback.")

@app.on_message(filters.command("resume") & filters.group)
async def resume_handler(_, msg):
    await pytgcalls.resume_stream(msg.chat.id)
    await msg.reply("▶️ Resumed playback.")

@app.on_message(filters.command("stop") & filters.group)
async def stop_handler(_, msg):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    await pytgcalls.leave_group_call(chat_id)
    await msg.reply("⏹ Stopped and cleared queue.")

@app.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, msg):
    q = queues.get(msg.chat.id, [])
    if not q:
        return await msg.reply("Queue is empty.")
    lines = [f"{i+1}. {title}" for i, (_, title) in enumerate(q)]
    await msg.reply("🎵 Current Queue:\n" + "\n".join(lines))

# =================== Main Bot Function ===================

async def main():
    await app.start()
    await pytgcalls.start()
    print("🎶 Bot is up and running!")
    await idle()
    await app.stop()

# =================== Start Everything ===================

if __name__ == "__main__":
    Thread(target=run_web).start()  # Keeps bot alive on Render
    asyncio.run(main())
      
