"""Точка входа Discord-бота для мониторинга GitLab."""

import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config_loader import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Intents для работы бота
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True
intents.message_content = True


class GitLabBot(commands.Bot):
    """Основной класс бота."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self) -> None:
        """Загрузка cogs и persistent views при старте."""
        from views.main_menu import MainMenuView
        self.add_view(MainMenuView())

        # Загрузка cogs
        cog_extensions = [
            "cogs.general",
            "cogs.subscriptions",
            "cogs.pipelines",
        ]
        for ext in cog_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Загружен cog: {ext}")
            except Exception as e:
                logger.error(f"Ошибка загрузки cog {ext}: {e}")

        # Синхронизация slash-команд для guild
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Slash-команды синхронизированы для guild {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Slash-команды синхронизированы глобально")

    async def on_ready(self) -> None:
        """Событие подключения к Discord."""
        logger.info(f"Бот подключён как {self.user} (ID: {self.user.id})")
        logger.info(f"Серверов: {len(self.guilds)}")


bot = GitLabBot()


def main() -> None:
    """Запуск бота."""
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN не задан!")
        return
    bot.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
