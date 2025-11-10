import os
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import yt_search, download_audio
from db import users_col, stats_col
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
OWNER_ID = int(os.environ.get("OWNER_ID"))
CHANNEL_ID = os.environ.get("CHANNEL_ID")
LOG_CHANNEL_ID = os.environ.get("LOG_CHANNEL_ID", CHANNEL_ID)
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", 8))
DOWNLOAD_TEMP_DIR = os.environ.get("DOWNLOAD_TEMP_DIR", "./tmp")

if not all([BOT_TOKEN, API_HASH, API_ID, OWNER_ID, CHANNEL_ID]):
    logger.error("Missing one or more required environment variables. Check .env.")
    raise SystemExit(1)

app = Client("musicbot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Helper: basic cooldown check (10 seconds)
COOLDOWN_SECONDS = 10

async def is_premium(user_id: int):
    doc = await users_col.find_one({"user_id": user_id})
    if not doc:
        return False
    exp = doc.get("is_premium_until")
    if not exp:
        return False
    return exp > datetime.utcnow()

async def set_premium(user_id: int, days: int):
    until = datetime.utcnow() + timedelta(days=days)
    await users_col.update_one({"user_id": user_id}, {"$set": {"is_premium_until": until}}, upsert=True)
    return until

async def remove_premium(user_id: int):
    await users_col.update_one({"user_id": user_id}, {"$unset": {"is_premium_until": ""}})

async def can_send_file(user_id: int):
    doc = await users_col.find_one({"user_id": user_id})
    if not doc:
        return True
    last = doc.get("last_sent")
    if not last:
        return True
    delta = datetime.utcnow() - last
    return delta.total_seconds() >= COOLDOWN_SECONDS

async def mark_sent(user_id: int):
    await users_col.update_one({"user_id": user_id}, {"$set": {"last_sent": datetime.utcnow()}}, upsert=True)

# Commands
@app.on_message(filters.private & filters.command("start"))
async def start(_, message):
    text = (
        "👋 Hello! I'm a Music & Channel File Bot.\n\n"
        "You can send me a song name or use /song <query> to search YouTube.\n"
        "Use /file <filename> to retrieve files from the channel.\n\n"
        "Owner / Premium contact: @technicalserena\n\n"
        "Type /help for more commands."
    )
    await message.reply(text)

@app.on_message(filters.private & filters.command("help"))
async def help_cmd(_, message):
    text = (
        "Commands:\n"
        "/song <query> - Search YouTube and get MP3.\n"
        "Or just send a text query in private chat to search.\n"
        "/file <filename> - Send file from the configured channel to you (bot must be in the channel).\n\n"
        "Owner only:\n"
        "/add <user_id> <days> - Add premium.\n"
        "/rem <user_id> - Remove premium.\n"
        "/broadcast <message> - Broadcast to all users in DB.\n\n"
        "Examples:\n"
        "/song never gonna give you up\n"
        "/file MyCoolSong.mp3\n"
    )
    await message.reply(text)

# Owner-only admin commands
@app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("add"))
async def add_premium(_, message):
    if len(message.command) < 3:
        await message.reply("Usage: /add <user_id> <days>")
        return
    try:
        user_id = int(message.command[1])
        days = int(message.command[2])
    except:
        await message.reply("user_id and days must be integers.")
        return
    until = await set_premium(user_id, days)
    await message.reply(f"✅ Premium granted to {user_id} until {until} UTC.")

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("rem"))
async def rem_premium(_, message):
    if len(message.command) < 2:
        await message.reply("Usage: /rem <user_id>")
        return
    try:
        user_id = int(message.command[1])
    except:
        await message.reply("user_id must be integer.")
        return
    await remove_premium(user_id)
    await message.reply(f"✅ Premium removed from {user_id}.")

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("broadcast"))
async def broadcast(_, message):
    if len(message.command) < 2:
        await message.reply("Usage: /broadcast <message text>")
        return
    text = message.text.partition(" ")[2]
    # send to all users in users_col
    cursor = users_col.find({}, {"user_id": 1})
    count = 0
    async for doc in cursor:
        uid = doc["user_id"]
        try:
            await app.send_message(uid, f"📣 Broadcast:\n\n{text}")
            count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")
    await message.reply(f"Broadcast sent to {count} users.")

# /file command: search in channel messages for filename
@app.on_message(filters.private & filters.command("file"))
async def send_file_from_channel(_, message):
    if len(message.command) < 2:
        await message.reply("Usage: /file <filename>")
        return
    filename = " ".join(message.command[1:])
    await message.reply("🔎 Searching channel for file...")
    # iterate last 200 messages in channel to find an attachment with matching file name
    found = None
    try:
        async for msg in app.search_messages(CHANNEL_ID, query=filename, limit=50):
            # Pyrogram's search_messages may return relevant messages
            # check for document/audio/video with file_name or title
            if msg.document and msg.document.file_name and filename.lower() in msg.document.file_name.lower():
                found = msg
                break
            if msg.audio and msg.audio.file_name and filename.lower() in msg.audio.file_name.lower():
                found = msg
                break
            if msg.video and msg.video.file_name and filename.lower() in msg.video.file_name.lower():
                found = msg
                break
            # caption matching
            if msg.caption and filename.lower() in msg.caption.lower():
                found = msg
                break
    except Exception as e:
        logger.exception("Error searching channel")
        await message.reply("Failed to search the channel. Make sure the bot has access and channel id is correct.")
        return

    if not found:
        await message.reply("❌ No file matched that filename in the channel.")
        return

    # Check cooldown
    uid = message.from_user.id
    if not await can_send_file(uid):
        await message.reply(f"⏳ Please wait {COOLDOWN_SECONDS} seconds between file sends.")
        return
    try:
        await app.copy_message(chat_id=uid, from_chat_id=CHANNEL_ID, message_id=found.message_id)
        await mark_sent(uid)
    except Exception as e:
        logger.exception("Failed to copy message")
        await message.reply("Failed to send the file. Ensure bot can read and copy messages from the channel.")

# Search handler: either /song or plain text
@app.on_message(filters.private & (filters.command("song") | filters.text))
async def search_handler(_, message):
    # If command /song or free text, extract query
    if message.text is None:
        return
    if message.text.startswith("/song"):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Usage: /song <query>")
            return
        query = parts[1]
    else:
        # treat plain text as search query
        if message.text.startswith("/"):
            # another command; ignore
            return
        query = message.text

    await message.reply("🔎 Searching YouTube...")
    try:
        results = await yt_search(query, max_results=MAX_SEARCH_RESULTS)
    except Exception as e:
        logger.exception("YouTube search failed")
        await message.reply("YouTube search failed. Check YT API key and quota.")
        return

    if not results:
        await message.reply("No results found.")
        return

    # Build inline keyboard
    buttons = []
    for i, item in enumerate(results, start=1):
        title = item["title"][:40]
        btn = InlineKeyboardButton(f"{i}. {title}", callback_data=f"dl|{item['id']}")
        buttons.append([btn])
    # Add "Next" not implemented for now (we returned MAX_SEARCH_RESULTS)
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply("Select a result to download MP3:", reply_markup=keyboard)

# Callback for inline button download
@app.on_callback_query(filters.regex(r"^dl\|"))
async def callback_download(_, cq):
    data = cq.data  # format: dl|video_id
    _, video_id = data.split("|", 1)
    user = cq.from_user
    uid = user.id

    # Cooldown check
    if not await can_send_file(uid):
        await cq.answer(f"⏳ Wait {COOLDOWN_SECONDS} seconds between downloads.", show_alert=True)
        return

    await cq.answer("Downloading... please wait", show_alert=False)
    # Download metadata (we might want to get title)
    # For simplicity, we will set title = video_id if not available
    title = video_id
    # attempt to obtain title by small API call
    import aiohttp
    YT_API_KEY = os.environ.get("YT_API_KEY")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.googleapis.com/youtube/v3/videos", params={"part": "snippet", "id": video_id, "key": YT_API_KEY}) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    items = js.get("items", [])
                    if items:
                        title = items[0]["snippet"]["title"]
    except Exception:
        pass

    try:
        mp3_path = await download_audio(video_id, title)
    except Exception as e:
        logger.exception("Download failed")
        await cq.message.reply("❌ Failed to download audio. Try again later.")
        return

    try:
        # send as audio file
        await app.send_audio(chat_id=uid, audio=mp3_path, title=title)
        await mark_sent(uid)
        # cleanup
        try:
            os.remove(mp3_path)
        except:
            pass
    except Exception as e:
        logger.exception("Failed to send audio")
        await cq.message.reply("❌ Failed to send audio. The file may be too large or Telegram blocked it.")
        return
    finally:
        # acknowledge the callback
        try:
            await cq.answer("Sent!", show_alert=False)
        except:
            pass

# On new user message, store them in DB if not exist
@app.on_message(filters.private)
async def store_user(_, message):
    uid = message.from_user.id
    name = message.from_user.first_name or ""
    await users_col.update_one({"user_id": uid}, {"$setOnInsert": {"user_id": uid, "first_name": name, "created_at": datetime.utcnow()}}, upsert=True)

# Start the bot
if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()