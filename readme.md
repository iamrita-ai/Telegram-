# Telegram Music & Channel File Bot

A Telegram bot that:
- Lets users search YouTube from a private chat and receive MP3 files (not links).
- Sends files stored in your Telegram channel to users via `/file <filename>`.
- Supports a premium system (add/remove days) stored in MongoDB.
- Owner-only management commands: `/add`, `/rem`, `/broadcast`.
- 10-second per-file cooldown per user to avoid suspensions.
- Search results are paginated (Next button) and users pick which song to download.
- Includes deployment instructions for Render, Docker, and Heroku.

Contact / Support: @technicalserena

---

Contents
- bot.py — main bot implementation (Pyrogram + asyncio)
- db.py — MongoDB helpers (motor)
- utils.py — helper utilities (YouTube search, yt-dlp wrapper)
- requirements.txt — Python dependencies
- Dockerfile, .dockerignore
- Procfile (Heroku)
- render.yaml — Render service template
- config.example.env — environment variables example
- README.md — this file

---

Quick setup (development)
1. Clone repo.
2. Copy `config.example.env` to `.env` and fill values:
   - BOT_TOKEN — Bot token from BotFather
   - API_ID — Telegram API ID (integer)
   - API_HASH — Telegram API Hash
   - YT_API_KEY — YouTube Data API v3 key
   - MONGO_URI — MongoDB connection URI
   - OWNER_ID — your Telegram user ID (integer)
   - CHANNEL_ID — your channel ID (e.g., -1001234567890)
   - LOG_CHANNEL_ID — channel ID used for files/logs (if different)
3. Create a Python venv and install requirements:
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
4. Run:
   python bot.py

---

Environment variables (config.example.env)
- BOT_TOKEN="123456:ABC-DEF..."
- API_ID=123456
- API_HASH="your_api_hash"
- YT_API_KEY="AIza..."
- MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/dbname"
- OWNER_ID=123456789
- CHANNEL_ID="-100xxxxxxxxxx"
- LOG_CHANNEL_ID="-100yyyyyyyyyy"
- MAX_SEARCH_RESULTS=8
- DOWNLOAD_TEMP_DIR="./tmp"

---

How it works (short)
- User DM with the bot: send a message with song name or use `/song <name>` — bot performs YouTube Data API search and returns a paginated list of results.
- The list items are InlineKeyboard buttons. Press one to request MP3.
- Bot downloads the audio via yt-dlp, converts to mp3, and sends as an audio/file to the user.
- After sending, downloads are removed. There is a 10-second cooldown between file sends to a user. Premium users can be handled as desired (you may change limits).
- `/file <filename>` will search pinned/posted files in your CHANNEL_ID and copy the matching file message to the user (requires bot be a member/admin of your channel).

---

Commands (user-facing)
- /start — Info and owner contact.
- /help — Usage and examples.
- /song <query> or plain text query in DM — search YouTube.
- (From results) — tap a result to download MP3.
- /file <filename> — copy a file from your channel to the user DM (searches filenames).
- Owner-only:
  - /add <user_id> <days> — add premium for X days to a user.
  - /rem <user_id> — remove premium.
  - /broadcast <message> — send message to all users in DB.

Examples:
- /song never gonna give you up
- /file MySong.mp3
- /add 123456789 30
- /rem 123456789
- /broadcast Hello premium users!

---

Hosting on Render
- Use the included Dockerfile and `render.yaml` to create a web service.
- Add environment variables in the Render dashboard exactly as in `.env`.
- Render will run the container; the bot starts and will keep running.

Heroku
- Use the `Procfile` (web: python bot.py) and set env vars in Heroku settings.
- Use Heroku Container Registry if you prefer Docker.

Security notes
- Keep your BOT_TOKEN, API_HASH, YT_API_KEY, and MONGO_URI secret.
- The bot downloads files temporarily — ensure proper disk size and clean-up.

---

Limitations & Notes
- You must provide API_ID (Telegram), API_HASH, BOT_TOKEN, YT_API_KEY, MONGO_URI, OWNER_ID, CHANNEL_ID.
- Bot must be added to your channel and allowed to read messages (and if copying from a private channel, it must be an admin or post messages).
- YouTube TOS: make sure your usage complies with YouTube terms.
- This implementation uses basic rate-limiting and a premium flag in MongoDB. Adjust as needed.

---

If you want, I can:
- Push this repository to GitHub for you (I will need the repo owner/name or permission).
- Add CI, tests, or a web dashboard.
