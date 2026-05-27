"""
Cog: Admin
Команди для викладачів: налаштування каналу, видалення завдань.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("cogs.admin")


def is_teacher():
    """Перевірка: чи є роль 'Teacher' або 'Адміністратор'."""
    async def predicate(interaction: discord.Interaction) -> bool:
        allowed_roles = {"teacher", "викладач", "адміністратор"}
        user_roles = {r.name.lower() for r in interaction.user.roles}
        has_role = bool(allowed_roles & user_roles)
        is_admin = interaction.user.guild_permissions.administrator

        if not (has_role or is_admin):
            await interaction.response.send_message(
                "⛔ Ця команда доступна лише викладачам або адміністраторам",
                ephemeral=True,
            )
            return False
        return True

    return app_commands.check(predicate)


class Admin(commands.Cog, name="Адміністрування"):
    """Команди для управління ботом (тільки для викладачів)."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /setchannel ───────────────────────────────────────────────────────────
    @app_commands.command(
        name="setchannel",
        description="Встановити канал для автоматичних нагадувань (тільки викладач)",
    )
    @is_teacher()
    async def slash_setchannel(self, interaction: discord.Interaction):
        await self.db.set_channel(interaction.guild_id, interaction.channel_id)

        embed = discord.Embed(
            title="✅ Канал встановлено",
            description=f"Нагадування надходитимуть у {interaction.channel.mention}",
            color=discord.Color.green(),
        )
        log.info(
            f"Канал нагадувань встановлено: {interaction.channel_id} "
            f"(guild: {interaction.guild_id})"
        )
        await interaction.response.send_message(embed=embed)

    # ── /delete ───────────────────────────────────────────────────────────────
    @app_commands.command(
        name="delete",
        description="Видалити завдання за ID (тільки викладач)",
    )
    @app_commands.describe(task_id="ID завдання для видалення")
    @is_teacher()
    async def slash_delete(self, interaction: discord.Interaction, task_id: int):
        # Перевіряємо, чи існує завдання
        task = await self.db.get_task(task_id)
        if not task:
            await interaction.response.send_message(
                f"⚠️ Завдання `#{task_id}` не знайдено", ephemeral=True
            )
            return

        await self.db.delete_task(task_id)

        embed = discord.Embed(
            title="🗑️ Завдання видалено",
            description=f"Завдання `#{task_id}` — **{task['title']}** видалено",
            color=discord.Color.red(),
        )
        log.info(
            f"Завдання #{task_id} видалено викладачем {interaction.user.id}"
        )
        await interaction.response.send_message(embed=embed)

    # ── /help ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="help", description="Довідка по командах бота")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📘 Довідка | Навчальний бот",
            description="Усі команди доступні через `/`",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="📝 Завдання",
            value=(
                "`/add` — додати завдання\n"
                "`/list` — всі завдання сервера\n"
                "`/mytasks` — ваші завдання\n"
                "`/done` — позначити як виконане\n"
                "`/overdue` — прострочені завдання\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="📊 Аналітика",
            value="`/stats` — статистика завдань",
            inline=False,
        )
        embed.add_field(
            name="⚙️ Адміністрування",
            value=(
                "`/setchannel` — канал для нагадувань\n"
                "`/delete` — видалити завдання\n"
            ),
            inline=False,
        )
        embed.set_footer(text="Discord-бот для автоматизації навчального процесу")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
