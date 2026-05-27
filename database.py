"""
Шар доступу до бази даних (async).
Використовує aiosqlite для безпечної роботи в asyncio-середовищі.
"""

import logging
from datetime import date, datetime
from typing import Optional

import aiosqlite

log = logging.getLogger("database")

# ── SQL-схема ──────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    guild_id    INTEGER NOT NULL,
    title       TEXT    NOT NULL,
    subject     TEXT    NOT NULL,
    deadline    TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',   -- active | done | overdue
    notified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    guild_id    INTEGER PRIMARY KEY,
    channel_id  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_user    ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_guild   ON tasks(guild_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
"""


class Database:
    """Обгортка над aiosqlite з методами для роботи з завданнями."""

    def __init__(self, path: str):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        """Відкриває з'єднання та створює таблиці."""
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row      # доступ через ім'я колонки
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        log.info(f"SQLite підключено: {self.path}")

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Tasks ──────────────────────────────────────────────────────────────────

    async def add_task(
        self,
        user_id: int,
        guild_id: int,
        title: str,
        subject: str,
        deadline: str,
    ) -> int:
        """Додає нове завдання, повертає його ID."""
        async with self._db.execute(
            """
            INSERT INTO tasks (user_id, guild_id, title, subject, deadline)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, guild_id, title, subject, deadline),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def get_all_tasks(self, guild_id: int) -> list[aiosqlite.Row]:
        async with self._db.execute(
            "SELECT * FROM tasks WHERE guild_id = ? ORDER BY deadline",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()

    async def get_user_tasks(self, user_id: int, guild_id: int) -> list[aiosqlite.Row]:
        async with self._db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND guild_id = ? ORDER BY deadline",
            (user_id, guild_id),
        ) as cur:
            return await cur.fetchall()

    async def get_task(self, task_id: int) -> Optional[aiosqlite.Row]:
        async with self._db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            return await cur.fetchone()

    async def mark_done(self, task_id: int, user_id: int) -> bool:
        """Позначає завдання як виконане. Повертає True якщо зміна відбулась."""
        async with self._db.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ) as cur:
            await self._db.commit()
            return cur.rowcount > 0

    async def delete_task(self, task_id: int) -> bool:
        async with self._db.execute(
            "DELETE FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            await self._db.commit()
            return cur.rowcount > 0

    async def get_overdue_tasks(self, guild_id: int) -> list[aiosqlite.Row]:
        today = date.today().isoformat()
        async with self._db.execute(
            """
            SELECT * FROM tasks
            WHERE guild_id = ? AND status = 'active' AND deadline < ?
            ORDER BY deadline
            """,
            (guild_id, today),
        ) as cur:
            return await cur.fetchall()

    async def get_pending_notifications(self) -> list[aiosqlite.Row]:
        """Повертає завдання, що потребують нагадування (дедлайн сьогодні або завтра)."""
        today = date.today().isoformat()
        async with self._db.execute(
            """
            SELECT t.*, s.channel_id
            FROM tasks t
            JOIN settings s ON t.guild_id = s.guild_id
            WHERE t.status = 'active'
              AND t.notified = 0
              AND t.deadline <= date('now', '+1 day')
            """,
        ) as cur:
            return await cur.fetchall()

    async def mark_notified(self, task_id: int):
        await self._db.execute(
            "UPDATE tasks SET notified = 1 WHERE id = ?", (task_id,)
        )
        await self._db.commit()

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def get_stats(self, guild_id: int) -> dict:
        async with self._db.execute(
            "SELECT COUNT(*) FROM tasks WHERE guild_id = ?", (guild_id,)
        ) as cur:
            total = (await cur.fetchone())[0]

        async with self._db.execute(
            "SELECT COUNT(*) FROM tasks WHERE guild_id = ? AND status = 'done'",
            (guild_id,),
        ) as cur:
            done = (await cur.fetchone())[0]

        today = date.today().isoformat()
        async with self._db.execute(
            "SELECT COUNT(*) FROM tasks WHERE guild_id = ? AND status = 'active' AND deadline < ?",
            (guild_id, today),
        ) as cur:
            overdue = (await cur.fetchone())[0]

        return {
            "total": total,
            "done": done,
            "active": total - done - overdue,
            "overdue": overdue,
        }

    # ── Settings ───────────────────────────────────────────────────────────────

    async def set_channel(self, guild_id: int, channel_id: int):
        await self._db.execute(
            """
            INSERT INTO settings (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            (guild_id, channel_id),
        )
        await self._db.commit()

    async def get_channel(self, guild_id: int) -> Optional[int]:
        async with self._db.execute(
            "SELECT channel_id FROM settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return row["channel_id"] if row else None
