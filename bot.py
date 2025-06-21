import os
import asyncio
from pyrogram import Client, filters
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import Update
from pytgcalls.types.stream import StreamAudioEnded
from yt_dlp import YoutubeDL
from ffmpeg import input as ffmpeg_input
from collections import deque

# Config
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Pyrogram & PyTgCalls setup
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

# Queue per chat
queues = {}

# YT downloader options
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'outtmpl': '%(id)s.%(ext)s'
}

def download_audio(query: str) -> str:
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        # pick first result if search
        url = info['formats'][0]['url']
        return url, info.get('title', "Unknown Title")

async def play_next(chat_id: int):
    queue = queues[chat_id]
    if not queue:
        await pytgcalls.leave_group_call(chat_id)
        return

    url, title = queue[0]
    await pytgcalls.join_group_call(
        chat_id,
        pytgcalls.stream(url),
        stream_type="stream"
    )

@pytgcalls.on_stream_end()
async def on_stream_end_handler(update: Update):
    chat_id = update.chat_id
    queue = queues.get(chat_id)
    if queue:
        queue.popleft()
        await play_next(chat_id)

# Bot commands
@app.on_message(filters.command("play") & filters.group)
async def cmd_play(_, msg):
    chat_id = msg.chat.id
    query = " ".join(msg.command[1:])
    if not query:
        return await msg.reply_text("Usage: /play <YouTube URL or song name>")

    url, title = download_audio(query)
    if chat_id not in queues:
        queues[chat_id] = deque()
    queues[chat_id].append((url, title))
    await msg.reply_text(f"Queued: **{title}**")

    if len(queues[chat_id]) == 1:
        await play_next(chat_id)

@app.on_message(filters.command("skip") & filters.group)
async def cmd_skip(_, msg):
    chat_id = msg.chat.id
    if queues.get(chat_id):
        queues[chat_id].popleft()
        await msg.reply_text("Skipped current track.")
        await play_next(chat_id)

@app.on_message(filters.command("pause") & filters.group)
async def cmd_pause(_, msg):
    await pytgcalls.pause_stream(msg.chat.id)
    await msg.reply_text("⏸ Paused")

@app.on_message(filters.command("resume") & filters.group)
async def cmd_resume(_, msg):
    await pytgcalls.resume_stream(msg.chat.id)
    await msg.reply_text("▶️ Resumed")

@app.on_message(filters.command("stop") & filters.group)
async def cmd_stop(_, msg):
    queues.pop(msg.chat.id, None)
    await pytgcalls.leave_group_call(msg.chat.id)
    await msg.reply_text("Stopped playback and cleared queue.")

@app.on_message(filters.command("queue") & filters.group)
async def cmd_queue(_, msg):
    q = queues.get(msg.chat.id, [])
    if not q:
        return await msg.reply_text("Queue is empty.")
    lines = [f"{i+1}. {t}" for i, (_, t) in enumerate(q)]
    await msg.reply_text("Upcoming tracks:\n" + "\n".join(lines))

# Launch
async def main():
    await app.start()
    await pytgcalls.start()
    print("Bot is online.")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
      
