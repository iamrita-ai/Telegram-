import os
import aiohttp
import asyncio
import yt_dlp
import hashlib
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
YT_API_KEY = os.environ.get("YT_API_KEY")
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", 8))
DOWNLOAD_TEMP_DIR = os.environ.get("DOWNLOAD_TEMP_DIR", "./tmp")

os.makedirs(DOWNLOAD_TEMP_DIR, exist_ok=True)

async def yt_search(query: str, max_results: int = MAX_SEARCH_RESULTS):
    # Uses YouTube Data API v3 search
    import urllib.parse
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YT_API_KEY,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=15) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"YT Search error {resp.status}: {text}")
            data = await resp.json()
            results = []
            for item in data.get("items", []):
                v = {
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "duration": None,  # We can fetch later via videos.list if desired
                }
                results.append(v)
            return results

def sanitize_filename(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c in " .-_").strip()

async def download_audio(video_id: str, title: str):
    # Download and convert to mp3 using yt-dlp
    outname = sanitize_filename(f"{title}_{video_id}.%(ext)s")
    outpath = os.path.join(DOWNLOAD_TEMP_DIR, outname)
    mp3_path = os.path.splitext(outpath)[0] + ".mp3"
    # yt-dlp options
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outpath,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        # limit rate if you want: "ratelimit": "500K",
        # progress_hooks: not used here
    }
    loop = asyncio.get_event_loop()
    def run_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    await loop.run_in_executor(None, run_download)
    # return path to mp3
    if os.path.exists(mp3_path):
        return mp3_path
    # Fallback: try to find any file
    for f in os.listdir(DOWNLOAD_TEMP_DIR):
        if f.endswith(".mp3") and video_id in f:
            return os.path.join(DOWNLOAD_TEMP_DIR, f)
    raise FileNotFoundError("Failed to produce mp3")