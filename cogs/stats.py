"""
Cog: Stats
Статистика та аналітика завдань.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("cogs.stats")


class Stats(commands.Cog, name="Статистика"):
    """Команди для перегляду статистики навчального процесу."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @app_commands.command(name="stats", description="Статистика завдань сервера")
    async def slash_stats(self, interaction: discord.Interaction):
        data = await self.db.get_stats(interaction.guild_id)

        total = data["total"]
        done = data["done"]
        active = data["active"]
        overdue = data["overdue"]

        # Прогрес-бар виконання
        percent = round((done / total * 100) if total else 0)
        bar_filled = round(percent / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(
            title="📊 Статистика навчального процесу",
            color=discord.Color.gold(),
        )
        embed.add_field(name="📚 Всього завдань", value=str(total), inline=True)
        embed.add_field(name="✅ Виконано", value=str(done), inline=True)
        embed.add_field(name="🔴 Активні", value=str(active), inline=True)
        embed.add_field(name="⚠️ Прострочені", value=str(overdue), inline=True)
        embed.add_field(
            name=f"📈 Прогрес виконання: {percent}%",
            value=f"`{bar}`",
            inline=False,
        )
        embed.set_footer(text=f"Сервер: {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Stats(bot))
