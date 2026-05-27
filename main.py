"""
Discord-бот для автоматизації навчального процесу
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import Database

BOT_DIR = Path(__file__).parent.resolve()
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
os.chdir(BOT_DIR)

# ── Логування ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")

load_dotenv()

# ── Список Cogs для завантаження ───────────────────────────────────────────────
COGS = [
    "cogs.tasks",
    "cogs.notifications",
    "cogs.admin",
    "cogs.stats",
]


# ── Bot ────────────────────────────────────────────────────────────────────────
class StudyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,           # власна /help через Cog
        )
        self.db: Database | None = None

    async def setup_hook(self):
        """Викликається перед on_ready — ініціалізація БД та Cogs."""
        self.db = Database("tasks.db")
        await self.db.init()
        log.info("База даних ініціалізована")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Cog завантажено: {cog}")
            except Exception as e:
                log.error(f"Помилка завантаження {cog}: {e}", exc_info=True)

        # Синхронізуємо slash-команди з Discord
        # synced = await self.tree.sync()
        # Для швидкого тестування — синхронізація лише для свого сервера
        synced = await self.tree.sync()

        log.info(f"Синхронізовано {len(synced)} slash-команд")

    async def on_ready(self):
        log.info(f"Бот запущено як {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="за завданнями 📚",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Глобальна обробка помилок prefix-команд."""
        if isinstance(error, commands.CommandNotFound):
            return  # ігноруємо — всі команди тепер slash (/)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Пропущений аргумент: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Невірний тип аргументу")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("⛔ Недостатньо прав для цієї команди")
        else:
            log.error(f"Необроблена помилка: {error}", exc_info=True)


# ── Запуск ─────────────────────────────────────────────────────────────────────
async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.critical("DISCORD_TOKEN не знайдено у .env файлі!")
        return

    async with StudyBot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())