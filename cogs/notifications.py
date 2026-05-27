"""
Cog: Notifications
Фонова задача для автоматичних нагадувань про дедлайни.
"""

import logging
from datetime import date

import discord
from discord.ext import commands, tasks

log = logging.getLogger("cogs.notifications")


class Notifications(commands.Cog, name="Сповіщення"):
    """Фоновий моніторинг дедлайнів і відправка нагадувань."""

    def __init__(self, bot):
        self.bot = bot
        self.check_deadlines.start()

    @property
    def db(self):
        return self.bot.db

    def cog_unload(self):
        self.check_deadlines.cancel()

    # ── Фоновий цикл ─────────────────────────────────────────────────────────
    @tasks.loop(minutes=1)
    async def check_deadlines(self):
        """Перевіряє дедлайни кожні 30 хвилин."""
        try:
            rows = await self.db.get_pending_notifications()
            today = date.today().isoformat()
            notified_count = 0

            for row in rows:
                channel = self.bot.get_channel(row["channel_id"])
                if not channel:
                    log.warning(f"Канал {row['channel_id']} не знайдено")
                    continue

                embed = self._build_notification_embed(row, today)
                await channel.send(embed=embed)
                await self.db.mark_notified(row["id"])
                notified_count += 1

            if notified_count:
                log.info(f"Відправлено {notified_count} нагадувань")

        except Exception as e:
            log.error(f"Помилка в check_deadlines: {e}", exc_info=True)

    @check_deadlines.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _build_notification_embed(self, row, today: str) -> discord.Embed:
        is_today = row["deadline"] == today

        if is_today:
            embed = discord.Embed(
                title="🚨 Дедлайн СЬОГОДНІ!",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title="🔔 Дедлайн завтра",
                color=discord.Color.orange(),
            )

        embed.add_field(name="Предмет", value=row["subject"], inline=True)
        embed.add_field(name="ID", value=f"`#{row['id']}`", inline=True)
        embed.add_field(name="Завдання", value=row["title"], inline=False)
        embed.add_field(name="Дедлайн", value=f"📅 `{row['deadline']}`", inline=True)
        embed.set_footer(text="Навчальний бот | Система моніторингу завдань")

        return embed


async def setup(bot):
    await bot.add_cog(Notifications(bot))
