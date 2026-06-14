"""Точка входа: запуск бота поддержки (long polling)."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from admin_handlers import router as admin_router
from user_handlers import router as user_router


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    await db.init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)  # важно: админ-роутер первым
    dp.include_router(user_router)

    me = await bot.get_me()
    logging.info(
        "Бот запущен: @%s (id %s). Админы: %s", me.username, me.id, config.ADMIN_IDS
    )

    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nОстановлено.")
