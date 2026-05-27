"""
Cog: Tasks
Команди для управління навчальними завданнями (slash + prefix).
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("cogs.tasks")

STATUS_EMOJI = {"active": "🔴", "done": "✅", "overdue": "⚠️"}


def format_task_row(row) -> str:
    emoji = STATUS_EMOJI.get(row["status"], "❓")
    return (
        f"`#{row['id']}` {emoji} **{row['subject']}** — {row['title']}\n"
        f"      📅 Дедлайн: `{row['deadline']}`\n"
    )


class Tasks(commands.Cog, name="Завдання"):
    """Команди для додавання, перегляду та управління завданнями."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /add ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="add", description="Додати нове навчальне завдання")
    @app_commands.describe(
        subject="Назва предмету (напр. Математика)",
        title="Опис завдання (напр. Лабораторна №3)",
        deadline="Дедлайн у форматі РРРР-ММ-ДД (напр. 2026-06-01)",
    )
    async def slash_add(
        self,
        interaction: discord.Interaction,
        subject: str,
        title: str,
        deadline: str,
    ):
        # Валідація дати
        try:
            datetime.strptime(deadline, "%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Невірний формат дати. Використовуйте `РРРР-ММ-ДД`", ephemeral=True
            )
            return

        task_id = await self.db.add_task(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            title=title,
            subject=subject,
            deadline=deadline,
        )

        embed = discord.Embed(
            title="✅ Завдання додано",
            color=discord.Color.green(),
        )
        embed.add_field(name="ID", value=f"`#{task_id}`", inline=True)
        embed.add_field(name="Предмет", value=subject, inline=True)
        embed.add_field(name="Завдання", value=title, inline=False)
        embed.add_field(name="Дедлайн", value=f"📅 `{deadline}`", inline=True)
        embed.set_footer(text=f"Додав: {interaction.user.display_name}")

        log.info(f"Завдання #{task_id} додано користувачем {interaction.user.id}")
        await interaction.response.send_message(embed=embed)

    # ── /list ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="list", description="Переглянути всі завдання сервера")
    async def slash_list(self, interaction: discord.Interaction):
        rows = await self.db.get_all_tasks(interaction.guild_id)

        if not rows:
            await interaction.response.send_message("📭 Завдань ще немає", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 Всі завдання",
            color=discord.Color.blurple(),
        )

        # Пагінація: максимум 10 завдань в embed
        for row in rows[:10]:
            embed.add_field(
                name=f"#{row['id']} [{row['subject']}]",
                value=f"{row['title']}\n📅 `{row['deadline']}` {STATUS_EMOJI.get(row['status'], '')}",
                inline=False,
            )

        if len(rows) > 10:
            embed.set_footer(text=f"Показано 10 з {len(rows)}. Використайте /mytasks для власних завдань.")
        else:
            embed.set_footer(text=f"Всього завдань: {len(rows)}")

        await interaction.response.send_message(embed=embed)

    # ── /mytasks ──────────────────────────────────────────────────────────────
    @app_commands.command(name="mytasks", description="Переглянути власні завдання")
    async def slash_mytasks(self, interaction: discord.Interaction):
        rows = await self.db.get_user_tasks(interaction.user.id, interaction.guild_id)

        if not rows:
            await interaction.response.send_message(
                "📭 У вас немає завдань. Додайте через `/add`", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 Завдання {interaction.user.display_name}",
            color=discord.Color.blue(),
        )

        for row in rows:
            embed.add_field(
                name=f"#{row['id']} [{row['subject']}]",
                value=f"{row['title']}\n📅 `{row['deadline']}` {STATUS_EMOJI.get(row['status'], '')}",
                inline=False,
            )

        embed.set_footer(text=f"Всього: {len(rows)} завдань")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /done ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="done", description="Позначити завдання як виконане")
    @app_commands.describe(task_id="ID завдання (видно у /list)")
    async def slash_done(self, interaction: discord.Interaction, task_id: int):
        success = await self.db.mark_done(task_id, interaction.user.id)

        if not success:
            await interaction.response.send_message(
                f"⚠️ Завдання `#{task_id}` не знайдено або воно не ваше",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="✅ Завдання виконано!",
            description=f"Завдання `#{task_id}` позначено як виконане.",
            color=discord.Color.green(),
        )
        log.info(f"Завдання #{task_id} виконано користувачем {interaction.user.id}")
        await interaction.response.send_message(embed=embed)

    # ── /overdue ──────────────────────────────────────────────────────────────
    @app_commands.command(name="overdue", description="Показати прострочені завдання")
    async def slash_overdue(self, interaction: discord.Interaction):
        rows = await self.db.get_overdue_tasks(interaction.guild_id)

        if not rows:
            await interaction.response.send_message(
                "✅ Прострочених завдань немає!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ Прострочені завдання",
            color=discord.Color.red(),
        )

        for row in rows:
            embed.add_field(
                name=f"#{row['id']} [{row['subject']}]",
                value=f"{row['title']}\n📅 Дедлайн був: `{row['deadline']}`",
                inline=False,
            )

        embed.set_footer(text=f"Прострочено: {len(rows)} завдань")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Tasks(bot))