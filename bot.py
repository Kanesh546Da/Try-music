import os
import asyncio
from pyrogram import Client, filters
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import Update
from pytgcall
from pytgcalls.types.stream import StreamEnded
from pytgcalls.types.input_stream import InputStream, InputAudioStream
from yt_dlp import YoutubeDL
from collections import deque

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

queues = {}

ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}

def get_audio_link(query):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        url = info['url']
        title = info.get('title', 'Unknown Title')
        return url, title

async def stream_next(chat_id):
    queue = queues.get(chat_id)
    if not queue:
        await pytgcalls.leave_group_call(chat_id)
        return

    url, title = queue[0]
    await pytgcalls.join_group_call(
        chat_id,
        InputStream(InputAudioStream(url)),
        stream_type="local_stream"
    )

@pytgcalls.on_stream_end()
async def on_stream_end_handler(_, update: StreamEnded):
    chat_id = update.chat_id
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].popleft()
        await stream_next(chat_id)

@app.on_message(filters.command("play") & filters.group)
async def play_handler(_, msg):
    chat_id = msg.chat.id
    if len(msg.command) < 2:
        return await msg.reply("❌ Usage: `/play song name or URL`", quote=True)

    query = " ".join(msg.command[1:])
    url, title = get_audio_link(query)

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
        await msg.reply("⏭ Skipped.")
        await stream_next(chat_id)

@app.on_message(filters.command("pause") & filters.group)
async def pause_handler(_, msg):
    await pytgcalls.pause_stream(msg.chat.id)
    await msg.reply("⏸ Paused")

@app.on_message(filters.command("resume") & filters.group)
async def resume_handler(_, msg):
    await pytgcalls.resume_stream(msg.chat.id)
    await msg.reply("▶️ Resumed")

@app.on_message(filters.command("stop") & filters.group)
async def stop_handler(_, msg):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    await pytgcalls.leave_group_call(chat_id)
    await msg.reply("⏹ Stopped and queue cleared.")

@app.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, msg):
    q = queues.get(msg.chat.id, [])
    if not q:
        return await msg.reply("Queue is empty.")
    lines = [f"{i+1}. {title}" for i, (_, title) in enumerate(q)]
    await msg.reply("🎵 Current Queue:\n" + "\n".join(lines))

async def main():
    await app.start()
    await pytgcalls.start()
    print("Bot is running...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
    
