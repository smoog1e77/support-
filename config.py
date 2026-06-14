"""Загрузка конфигурации из .env."""
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
    if x.strip().lstrip("-").isdigit()
}

DB_PATH = os.getenv("DB_PATH", "support.db").strip() or "support.db"

try:
    PAGE_SIZE = max(1, int(os.getenv("PAGE_SIZE", "6")))
except ValueError:
    PAGE_SIZE = 6

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Откройте .env и впишите токен от @BotFather "
        "(см. .env.example)."
    )

if not ADMIN_IDS:
    raise RuntimeError(
        "ADMIN_IDS не задан. Укажите в .env Telegram ID администратора "
        "(узнать свой ID можно у @userinfobot)."
    )
