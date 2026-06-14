"""Слой работы с SQLite (через aiosqlite)."""
import time

import aiosqlite

from config import DB_PATH
from texts import content_preview, STATUS_ANSWERED, STATUS_CLOSED, STATUS_WAITING

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    first_name      TEXT,
    last_name       TEXT,
    status          TEXT NOT NULL DEFAULT 'waiting',
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL,
    last_message_at INTEGER NOT NULL,
    last_preview    TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     INTEGER NOT NULL,
    sender        TEXT NOT NULL,             -- 'user' | 'admin'
    content_type  TEXT NOT NULL DEFAULT 'text',
    text          TEXT,
    file_id       TEXT,
    tg_message_id INTEGER,
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notify_map (
    chat_id    INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    ticket_id  INTEGER NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_user   ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON messages(ticket_id);
"""


def now():
    return int(time.time())


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_or_create_open_ticket(user):
    """Возвращает (ticket_id, is_new). Открытый = не закрытый тикет пользователя."""
    ts = now()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id FROM tickets WHERE user_id=? AND status!=? "
            "ORDER BY id DESC LIMIT 1",
            (user.id, STATUS_CLOSED),
        )
        row = await cur.fetchone()
        if row:
            return row["id"], False
        cur = await db.execute(
            "INSERT INTO tickets (user_id, username, first_name, last_name, "
            "status, created_at, updated_at, last_message_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                STATUS_WAITING,
                ts,
                ts,
                ts,
            ),
        )
        await db.commit()
        return cur.lastrowid, True


async def add_user_message(ticket_id, user, content_type, text, file_id, tg_message_id):
    ts = now()
    preview = content_preview(content_type, text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content_type, text, "
            "file_id, tg_message_id, created_at) VALUES (?,?,?,?,?,?,?)",
            (ticket_id, "user", content_type, text, file_id, tg_message_id, ts),
        )
        await db.execute(
            "UPDATE tickets SET status=?, updated_at=?, last_message_at=?, "
            "last_preview=?, username=?, first_name=?, last_name=? WHERE id=?",
            (
                STATUS_WAITING,
                ts,
                ts,
                preview,
                user.username,
                user.first_name,
                user.last_name,
                ticket_id,
            ),
        )
        await db.commit()


async def add_admin_message(ticket_id, content_type, text, file_id, tg_message_id):
    ts = now()
    preview = content_preview(content_type, text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content_type, text, "
            "file_id, tg_message_id, created_at) VALUES (?,?,?,?,?,?,?)",
            (ticket_id, "admin", content_type, text, file_id, tg_message_id, ts),
        )
        await db.execute(
            "UPDATE tickets SET status=?, updated_at=?, last_message_at=?, "
            "last_preview=? WHERE id=?",
            (STATUS_ANSWERED, ts, ts, "🛟 " + preview, ticket_id),
        )
        await db.commit()


async def set_status(ticket_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status=?, updated_at=? WHERE id=?",
            (status, now(), ticket_id),
        )
        await db.commit()


async def get_ticket(ticket_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        return await cur.fetchone()


async def list_tickets(status, limit, offset):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cur = await db.execute(
                "SELECT * FROM tickets WHERE status=? "
                "ORDER BY last_message_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM tickets ORDER BY "
                "CASE status WHEN 'waiting' THEN 0 WHEN 'answered' THEN 1 ELSE 2 END, "
                "last_message_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return await cur.fetchall()


async def count_by_status():
    out = {"waiting": 0, "answered": 0, "closed": 0, "total": 0}
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status")
        for status, cnt in await cur.fetchall():
            if status in out:
                out[status] = cnt
            out["total"] += cnt
    return out


async def get_messages(ticket_id, limit=12):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM (SELECT * FROM messages WHERE ticket_id=? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
            (ticket_id, limit),
        )
        return await cur.fetchall()


async def search_tickets(query, limit=50):
    query = (query or "").strip()
    if not query:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if query.isdigit():
            cur = await db.execute(
                "SELECT * FROM tickets WHERE id=? OR user_id=? "
                "ORDER BY last_message_at DESC LIMIT ?",
                (int(query), int(query), limit),
            )
            return await cur.fetchall()

        # Текстовый поиск делаем на стороне Python: SQLite LIKE/LOWER
        # регистронезависимы только для ASCII, а нам нужна и кириллица.
        needle = query.lstrip("@").casefold()
        msg_ids = set()
        cur = await db.execute(
            "SELECT ticket_id, text FROM messages WHERE text IS NOT NULL"
        )
        for ticket_id, text in await cur.fetchall():
            if text and needle in text.casefold():
                msg_ids.add(ticket_id)

        cur = await db.execute(
            "SELECT * FROM tickets ORDER BY last_message_at DESC"
        )
        results = []
        for row in await cur.fetchall():
            name = " ".join(
                x for x in (row["username"], row["first_name"], row["last_name"]) if x
            ).casefold()
            if needle in name or row["id"] in msg_ids:
                results.append(row)
                if len(results) >= limit:
                    break
        return results


async def save_notify(chat_id, message_id, ticket_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO notify_map (chat_id, message_id, ticket_id) "
            "VALUES (?,?,?)",
            (chat_id, message_id, ticket_id),
        )
        await db.commit()


async def get_ticket_by_notify(chat_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT ticket_id FROM notify_map WHERE chat_id=? AND message_id=?",
            (chat_id, message_id),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def extra_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(DISTINCT user_id) FROM tickets")
        users = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM messages")
        messages = (await cur.fetchone())[0]
    return {"users": users, "messages": messages}
