import sqlite3
from datetime import datetime, timezone, timedelta

DB_FILE = "messages.db"


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id      TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                date    TEXT NOT NULL,
                text    TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON messages(date)")


def save_messages(messages: list[dict]) -> int:
    saved = 0
    with sqlite3.connect(DB_FILE) as conn:
        for m in messages:
            msg_id = f"{m['channel']}_{m['date']}"
            conn.execute(
                "INSERT OR IGNORE INTO messages (id, channel, date, text) VALUES (?, ?, ?, ?)",
                (msg_id, m["channel"], m["date"], m["text"]),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                saved += 1
    return saved


def get_messages_since(hours: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT channel, date, text FROM messages WHERE date >= ? ORDER BY date ASC",
            (since,),
        ).fetchall()
    return [{"channel": r[0], "date": r[1], "text": r[2]} for r in rows]


def count_messages() -> int:
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
