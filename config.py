import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///trading_bot.db")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")
