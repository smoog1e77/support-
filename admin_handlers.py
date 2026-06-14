"""Админ-панель внутри Telegram: тикеты, фильтры, ответы."""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
import texts
from config import ADMIN_IDS, PAGE_SIZE
from keyboards import (
    back_to_menu_kb,
    cancel_kb,
    main_menu_kb,
    ticket_card_kb,
    tickets_list_kb,
)

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminSG(StatesGroup):
    replying = State()
    searching = State()


# --------------------------- helpers ---------------------------
async def safe_edit(cb, text, kb=None, alert=None):
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            try:
                await cb.message.answer(text, reply_markup=kb)
            except TelegramBadRequest:
                pass
    await cb.answer(alert)


async def deliver_admin_message(bot: Bot, ticket, message):
    """Отправляет ответ админа пользователю и сохраняет его в историю."""
    content_type, text, file_id = texts.extract(message)
    try:
        if content_type == "text":
            await bot.send_message(ticket["user_id"], text)
        else:
            await bot.copy_message(
                ticket["user_id"], message.chat.id, message.message_id
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("Не доставлено пользователю %s: %s", ticket["user_id"], e)
        return False
    await db.add_admin_message(
        ticket["id"], content_type, text, file_id, message.message_id
    )
    return True


async def show_card(cb, ticket_id, status, page, alert=None):
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    msgs = await db.get_messages(ticket_id, 12)
    await safe_edit(
        cb,
        texts.fmt_ticket(ticket, msgs, "Последние сообщения"),
        ticket_card_kb(ticket, status, page),
        alert=alert,
    )


# --------------------------- commands ---------------------------
@router.message(Command("start", "panel", "admin", "menu"))
async def cmd_panel(message, state: FSMContext):
    await state.clear()
    c = await db.count_by_status()
    await message.answer(texts.menu_text(c), reply_markup=main_menu_kb(c))


@router.message(Command("cancel"))
async def cmd_cancel(message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. /panel — открыть меню.")


# --------------------------- FSM input ---------------------------
@router.message(AdminSG.replying)
async def on_reply_input(message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    tid = data.get("ticket_id")
    ticket = await db.get_ticket(tid)
    await state.clear()
    if not ticket:
        await message.answer("Тикет не найден.")
        return

    ok = await deliver_admin_message(bot, ticket, message)
    if ok:
        await message.answer(f"✅ Ответ отправлен пользователю (тикет #{tid}).")
    else:
        await message.answer(
            "⚠️ Не удалось доставить. Возможно, пользователь заблокировал бота."
        )

    ticket = await db.get_ticket(tid)
    msgs = await db.get_messages(tid, 12)
    chat, mid = data.get("prompt_chat"), data.get("prompt_msg")
    if chat and mid:
        try:
            await bot.edit_message_text(
                texts.fmt_ticket(ticket, msgs, "Последние сообщения"),
                chat_id=chat,
                message_id=mid,
                reply_markup=ticket_card_kb(
                    ticket, data.get("back_status", "waiting"), data.get("back_page", 0)
                ),
            )
        except TelegramBadRequest:
            pass


@router.message(AdminSG.searching)
async def on_search_input(message, state: FSMContext, bot: Bot):
    q = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()

    results = await db.search_tickets(q)
    shown = results[:PAGE_SIZE]
    if not results:
        text = f"🔎 По запросу «{html.escape(q)}» ничего не найдено."
        kb = back_to_menu_kb()
    else:
        text = f"🔎 Найдено: {len(results)}"
        if len(results) > len(shown):
            text += f" (показаны первые {len(shown)}, уточните запрос)"
        kb = tickets_list_kb(shown, "all", 0, len(shown), PAGE_SIZE)

    chat, mid = data.get("prompt_chat"), data.get("prompt_msg")
    if chat and mid:
        try:
            await bot.edit_message_text(
                text, chat_id=chat, message_id=mid, reply_markup=kb
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


# --------------------------- reply shortcut ---------------------------
@router.message(StateFilter(None), F.reply_to_message)
async def on_reply_shortcut(message, bot: Bot):
    ref = message.reply_to_message
    tid = await db.get_ticket_by_notify(message.chat.id, ref.message_id)
    if not tid:
        c = await db.count_by_status()
        await message.answer(
            "Не понял, к какому тикету относится ответ. Откройте /panel.",
            reply_markup=main_menu_kb(c),
        )
        return
    ticket = await db.get_ticket(tid)
    if not ticket:
        await message.answer("Тикет не найден.")
        return
    ok = await deliver_admin_message(bot, ticket, message)
    await message.answer(
        f"✅ Ответ отправлен (тикет #{tid})."
        if ok
        else "⚠️ Не удалось доставить."
    )


# --------------------------- fallback ---------------------------
@router.message(StateFilter(None))
async def admin_fallback(message):
    c = await db.count_by_status()
    await message.answer(
        "Это панель поддержки 🛟\nОткройте меню кнопкой ниже или командой /panel.",
        reply_markup=main_menu_kb(c),
    )


# --------------------------- callbacks ---------------------------
@router.callback_query(F.data == "noop")
async def cb_noop(cb):
    await cb.answer()


@router.callback_query(F.data == "menu")
async def cb_menu(cb, state: FSMContext):
    await state.clear()
    c = await db.count_by_status()
    await safe_edit(cb, texts.menu_text(c), main_menu_kb(c))


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb, state: FSMContext):
    await state.clear()
    c = await db.count_by_status()
    await safe_edit(cb, texts.menu_text(c), main_menu_kb(c), alert="Отменено")


@router.callback_query(F.data == "stats")
async def cb_stats(cb):
    c = await db.count_by_status()
    extra = await db.extra_stats()
    await safe_edit(cb, texts.stats_text(c, extra), back_to_menu_kb())


@router.callback_query(F.data == "search")
async def cb_search(cb, state: FSMContext):
    await state.set_state(AdminSG.searching)
    await state.update_data(
        prompt_chat=cb.message.chat.id, prompt_msg=cb.message.message_id
    )
    await safe_edit(
        cb,
        "🔎 Введите запрос: ID пользователя, ID тикета, @username или часть текста.\n"
        "/cancel — отмена.",
        cancel_kb(),
    )


@router.callback_query(F.data.startswith("list:"))
async def cb_list(cb, state: FSMContext):
    await state.clear()
    _, status, page = cb.data.split(":")
    page = int(page)
    c = await db.count_by_status()
    total = c["total"] if status == "all" else c.get(status, 0)
    tickets = await db.list_tickets(
        None if status == "all" else status, PAGE_SIZE, page * PAGE_SIZE
    )
    await safe_edit(
        cb,
        texts.list_header(status, total),
        tickets_list_kb(tickets, status, page, total, PAGE_SIZE),
    )


@router.callback_query(F.data.startswith("ticket:"))
async def cb_ticket(cb, state: FSMContext):
    await state.clear()
    _, tid, status, page = cb.data.split(":")
    await show_card(cb, int(tid), status, int(page))


@router.callback_query(F.data.startswith("history:"))
async def cb_history(cb):
    _, tid, status, page = cb.data.split(":")
    ticket = await db.get_ticket(int(tid))
    if not ticket:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    msgs = await db.get_messages(int(tid), 50)
    await safe_edit(
        cb,
        texts.fmt_ticket(ticket, msgs, "Полная история"),
        ticket_card_kb(ticket, status, int(page)),
    )


@router.callback_query(F.data.startswith("reply:"))
async def cb_reply(cb, state: FSMContext):
    _, tid, status, page = cb.data.split(":")
    ticket = await db.get_ticket(int(tid))
    if not ticket:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    await state.set_state(AdminSG.replying)
    await state.update_data(
        ticket_id=int(tid),
        back_status=status,
        back_page=int(page),
        prompt_chat=cb.message.chat.id,
        prompt_msg=cb.message.message_id,
    )
    name = texts.display_name(ticket)
    await safe_edit(
        cb,
        f"✍️ <b>Ответ для тикета #{tid}</b> ({html.escape(name)})\n\n"
        "Напишите сообщение — можно текст, фото или файл. "
        "Оно будет отправлено пользователю.\n\n/cancel — отмена.",
        cancel_kb(),
    )


@router.callback_query(F.data.startswith("close:"))
async def cb_close(cb, state: FSMContext, bot: Bot):
    await state.clear()
    _, tid, status, page = cb.data.split(":")
    ticket = await db.get_ticket(int(tid))
    if not ticket:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    await db.set_status(int(tid), texts.STATUS_CLOSED)
    try:
        await bot.send_message(
            ticket["user_id"],
            f"🔒 Ваш тикет #{tid} закрыт. Спасибо за обращение!\n"
            "Если вопрос снова актуален — просто напишите сюда.",
        )
    except Exception:  # noqa: BLE001
        pass
    await show_card(cb, int(tid), status, int(page), alert="Тикет закрыт")


@router.callback_query(F.data.startswith("reopen:"))
async def cb_reopen(cb, state: FSMContext):
    await state.clear()
    _, tid, status, page = cb.data.split(":")
    ticket = await db.get_ticket(int(tid))
    if not ticket:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    await db.set_status(int(tid), texts.STATUS_WAITING)
    await show_card(cb, int(tid), status, int(page), alert="Тикет открыт")
