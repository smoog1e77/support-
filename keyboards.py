"""Inline-клавиатуры админ-панели."""
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from texts import display_name, status_meta


def main_menu_kb(c):
    b = InlineKeyboardBuilder()
    b.button(text=f"🆕 Ожидают ({c['waiting']})", callback_data="list:waiting:0")
    b.button(text=f"✉️ Отвечено ({c['answered']})", callback_data="list:answered:0")
    b.button(text=f"🔒 Закрытые ({c['closed']})", callback_data="list:closed:0")
    b.button(text=f"📥 Все ({c['total']})", callback_data="list:all:0")
    b.button(text="🔎 Поиск", callback_data="search")
    b.button(text="📊 Статистика", callback_data="stats")
    b.button(text="🔄 Обновить", callback_data="menu")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def back_to_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🏠 В меню", callback_data="menu")
    return b.as_markup()


def tickets_list_kb(tickets, status, page, total_count, page_size):
    b = InlineKeyboardBuilder()
    for t in tickets:
        emoji = status_meta(t["status"])[0]
        label = f"{emoji} #{t['id']} {display_name(t)}"
        if t["last_preview"]:
            label += f" · {t['last_preview']}"
        b.row(
            InlineKeyboardButton(
                text=label[:60],
                callback_data=f"ticket:{t['id']}:{status}:{page}",
            )
        )

    pages = max(1, (total_count + page_size - 1) // page_size)
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"list:{status}:{page - 1}")
        )
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if (page + 1) * page_size < total_count:
        nav.append(
            InlineKeyboardButton(text="➡️", callback_data=f"list:{status}:{page + 1}")
        )
    if len(nav) > 1:
        b.row(*nav)

    b.row(InlineKeyboardButton(text="🏠 В меню", callback_data="menu"))
    return b.as_markup()


def ticket_card_kb(t, back_status, back_page):
    tid = t["id"]
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✍️ Ответить", callback_data=f"reply:{tid}:{back_status}:{back_page}"
        )
    )
    row2 = [
        InlineKeyboardButton(
            text="📜 История", callback_data=f"history:{tid}:{back_status}:{back_page}"
        )
    ]
    if t["status"] == "closed":
        row2.append(
            InlineKeyboardButton(
                text="🔓 Открыть",
                callback_data=f"reopen:{tid}:{back_status}:{back_page}",
            )
        )
    else:
        row2.append(
            InlineKeyboardButton(
                text="🔒 Закрыть",
                callback_data=f"close:{tid}:{back_status}:{back_page}",
            )
        )
    b.row(*row2)
    b.row(
        InlineKeyboardButton(
            text="⬅️ К списку", callback_data=f"list:{back_status}:{back_page}"
        ),
        InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
    )
    return b.as_markup()


def notify_kb(ticket_id):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✍️ Ответить", callback_data=f"reply:{ticket_id}:waiting:0"
        ),
        InlineKeyboardButton(
            text="📋 Открыть", callback_data=f"ticket:{ticket_id}:waiting:0"
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="🔒 Закрыть", callback_data=f"close:{ticket_id}:waiting:0"
        )
    )
    return b.as_markup()


def cancel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✖️ Отмена", callback_data="cancel")
    return b.as_markup()
