import os
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
db = client["telegram_music_bot"]

# Collections:
users_col = db["users"]         # user_id, is_premium_until, last_sent
stats_col = db["stats"]         # basic stats