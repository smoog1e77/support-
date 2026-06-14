"""Тексты сообщений и форматирование (HTML parse mode)."""
import html
from datetime import datetime

# --- Статусы тикетов ---
STATUS_WAITING = "waiting"
STATUS_ANSWERED = "answered"
STATUS_CLOSED = "closed"

STATUS_META = {
    STATUS_WAITING: ("🆕", "Ожидает ответа"),
    STATUS_ANSWERED: ("✉️", "Отвечено"),
    STATUS_CLOSED: ("🔒", "Закрыто"),
}

LIST_TITLE = {
    STATUS_WAITING: "🆕 Ожидают ответа",
    STATUS_ANSWERED: "✉️ Отвечено",
    STATUS_CLOSED: "🔒 Закрытые",
    "all": "📥 Все тикеты",
}

CONTENT_LABEL = {
    "text": "текст",
    "photo": "фото",
    "document": "файл",
    "voice": "голосовое",
    "video": "видео",
    "audio": "аудио",
    "animation": "GIF",
    "video_note": "видео-кружок",
    "sticker": "стикер",
    "location": "геопозиция",
    "contact": "контакт",
    "other": "вложение",
}

USER_WELCOME = (
    "👋 Здравствуйте! Это служба поддержки.\n\n"
    "Опишите ваш вопрос одним сообщением — можно отправить текст, фото или файл. "
    "Оператор увидит обращение и ответит вам прямо здесь."
)


# --- Вспомогательные ---
def status_meta(status):
    return STATUS_META.get(status, ("•", status))


def ru_content_label(content_type):
    return CONTENT_LABEL.get(content_type, "вложение")


def content_preview(content_type, text):
    """Короткое превью сообщения для списка/уведомления."""
    if text and text.strip():
        return text.strip().replace("\n", " ")[:90]
    return f"[{ru_content_label(content_type)}]"


def fmt_dt(ts):
    return datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")


def display_name(t):
    """Имя для кнопок (обычный текст, без HTML)."""
    name = " ".join(x for x in (t["first_name"], t["last_name"]) if x)
    if name:
        return name
    if t["username"]:
        return "@" + t["username"]
    return f"id{t['user_id']}"


def fmt_user_line(t):
    name = " ".join(x for x in (t["first_name"], t["last_name"]) if x) or "Без имени"
    uname = f"@{t['username']}" if t["username"] else "без username"
    return (
        f"👤 <b>{html.escape(name)}</b> · {html.escape(uname)} · "
        f"id <code>{t['user_id']}</code>"
    )


def extract(message):
    """Достаёт (content_type, text, file_id) из сообщения aiogram."""
    if message.text is not None:
        return "text", message.text, None
    if message.photo:
        return "photo", message.caption, message.photo[-1].file_id
    if message.document:
        return "document", message.caption, message.document.file_id
    if message.voice:
        return "voice", message.caption, message.voice.file_id
    if message.video:
        return "video", message.caption, message.video.file_id
    if message.audio:
        return "audio", message.caption, message.audio.file_id
    if message.animation:
        return "animation", message.caption, message.animation.file_id
    if message.video_note:
        return "video_note", None, message.video_note.file_id
    if message.sticker:
        return "sticker", None, message.sticker.file_id
    if message.location:
        return "location", None, None
    if message.contact:
        return "contact", None, None
    return "other", message.caption, None


# --- Экраны ---
def menu_text(c):
    return (
        "🛟 <b>Панель поддержки</b>\n\n"
        f"🆕 Ожидают ответа: <b>{c['waiting']}</b>\n"
        f"✉️ Отвечено: <b>{c['answered']}</b>\n"
        f"🔒 Закрыто: <b>{c['closed']}</b>\n"
        f"📥 Всего тикетов: <b>{c['total']}</b>\n\n"
        "Выберите раздел 👇"
    )


def list_header(status, count):
    title = LIST_TITLE.get(status, "Тикеты")
    if not count:
        return f"<b>{title}</b>\n\n<i>Пусто 🤷</i>"
    return f"<b>{title}</b> — {count}\n\nВыберите тикет:"


def fmt_ticket(t, messages, title="История"):
    emoji, label = status_meta(t["status"])
    lines = [
        f"🎫 <b>Тикет #{t['id']}</b> · {emoji} {label}",
        fmt_user_line(t),
        f"🕒 создан {fmt_dt(t['created_at'])} · обновлён {fmt_dt(t['last_message_at'])}",
        "",
    ]
    if not messages:
        lines.append("<i>Сообщений пока нет.</i>")
    else:
        lines.append(f"<b>{title}:</b>")
        for m in messages:
            who = "👤" if m["sender"] == "user" else "🛟"
            if m["text"] and m["text"].strip():
                body = html.escape(m["text"].strip())[:400]
            else:
                body = f"<i>[{ru_content_label(m['content_type'])}]</i>"
            lines.append(f"{who} <i>{fmt_dt(m['created_at'])}</i> — {body}")
    return "\n".join(lines)[:4000]


def admin_notification(t, content_type, text, is_new):
    head = "🆕 <b>Новый тикет</b>" if is_new else "💬 <b>Новое сообщение</b>"
    if text and text.strip():
        body = html.escape(text.strip())[:600]
    else:
        body = f"<i>[{ru_content_label(content_type)}]</i>"
    return (
        f"{head} · #{t['id']}\n"
        f"{fmt_user_line(t)}\n"
        f"🕒 {fmt_dt(t['last_message_at'])}\n\n"
        f"{body}\n\n"
        "↩️ Ответьте на это сообщение или нажмите «Ответить»."
    )


def stats_text(c, extra):
    return (
        "📊 <b>Статистика</b>\n\n"
        f"🆕 Ожидают ответа: <b>{c['waiting']}</b>\n"
        f"✉️ Отвечено: <b>{c['answered']}</b>\n"
        f"🔒 Закрыто: <b>{c['closed']}</b>\n"
        f"📥 Всего тикетов: <b>{c['total']}</b>\n"
        f"👥 Уникальных пользователей: <b>{extra['users']}</b>\n"
        f"✉️ Сообщений всего: <b>{extra['messages']}</b>"
    )
