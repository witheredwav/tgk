import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID")                  # @username или -100...
CHANNEL_LINK = os.getenv("CHANNEL_LINK")              # https://t.me/...
WORKS_CHANNEL_LINK = os.getenv("WORKS_CHANNEL_LINK")  # https://t.me/...
DM_LINK = os.getenv("DM_LINK")                        # https://t.me/username

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан! Добавь переменную окружения BOT_TOKEN.")

DB_FILE = "db.json"

# Реферальная система: сколько приглашённых друзей нужно для бонуса
REFERRAL_BONUS_THRESHOLD = int(os.getenv("REFERRAL_BONUS_THRESHOLD", "3"))
