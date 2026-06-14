"""Обработчики сообщений от обычных пользователей."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart

import db
import texts
from config import ADMIN_IDS
from keyboards import notify_kb

logger = logging.getLogger(__name__)

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message):
    await message.answer(texts.USER_WELCOME)


@router.message(Command("help"))
async def cmd_help(message):
    await message.answer(texts.USER_WELCOME)


@router.message(F.chat.type == "private")
async def on_user_message(message, bot: Bot):
    user = message.from_user
    ticket_id, is_new = await db.get_or_create_open_ticket(user)
    content_type, text, file_id = texts.extract(message)
    await db.add_user_message(
        ticket_id, user, content_type, text, file_id, message.message_id
    )

    if is_new:
        await message.answer(
            f"✅ Обращение принято. Ваш тикет <b>#{ticket_id}</b>.\n"
            "Оператор ответит вам в ближайшее время."
        )
    else:
        await message.answer("✅ Передал оператору.")

    ticket = await db.get_ticket(ticket_id)
    header = texts.admin_notification(ticket, content_type, text, is_new)
    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(
                admin_id, header, reply_markup=notify_kb(ticket_id)
            )
            await db.save_notify(admin_id, sent.message_id, ticket_id)
            if content_type != "text":
                await bot.copy_message(admin_id, message.chat.id, message.message_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, e)
