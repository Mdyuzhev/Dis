"""Точка входа Discord-бота для мониторинга GitLab."""

import asyncio
import logging

import discord
import uvicorn
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from config_loader import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, WEBHOOK_PORT

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
        self._webhook_started = False

    async def setup_hook(self) -> None:
        """Загрузка cogs и persistent views при старте."""
        from views.main_menu import MainMenuView

        # show_admin=True чтобы все custom_id (включая main:admin) были зарегистрированы
        self.add_view(MainMenuView(show_admin=True))

        # Загрузка cogs (команды)
        cog_extensions = [
            "cogs.general",
            "cogs.subscriptions",
            "cogs.pipelines",
            "cogs.admin",
            "cogs.testit",
        ]
        # Фоновые задачи (tasks)
        task_extensions = [
            "tasks.pipeline_checker",
            "tasks.camera_checker",
            "tasks.stats_sender",
        ]
        for ext in cog_extensions + task_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Загружен: {ext}")
            except Exception as e:
                logger.error(f"Ошибка загрузки {ext}: {e}")

        # Синхронизация slash-команд для guild
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Slash-команды синхронизированы для guild {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Slash-команды синхронизированы глобально")

        # Глобальный обработчик ошибок slash-команд
        self.tree.on_error = self._on_app_command_error

    async def _on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Глобальный обработчик ошибок slash-команд."""
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message(
                "Недостаточно прав для выполнения команды.", ephemeral=True
            )
        elif isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Команда на перезарядке. Повторите через {error.retry_after:.0f}с.",
                ephemeral=True,
            )
        else:
            logger.error(f"Ошибка команды: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при выполнении команды.", ephemeral=True
                )

    async def on_ready(self) -> None:
        """Событие подключения к Discord + запуск вебхук-сервера."""
        logger.info(f"Бот подключён как {self.user} (ID: {self.user.id})")
        logger.info(f"Серверов: {len(self.guilds)}")

        # Защита от повторного запуска при реконнекте
        if self._webhook_started:
            return

        # Запуск FastAPI вебхука для Test IT
        try:
            from testit_webhook import create_app

            app = create_app(self)
            config = uvicorn.Config(
                app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="info"
            )
            server = uvicorn.Server(config)
            asyncio.create_task(server.serve())
            self._webhook_started = True
            logger.info(f"TestIT webhook запущен на порту {WEBHOOK_PORT}")
        except Exception as e:
            logger.error(f"Не удалось запустить TestIT webhook: {e}")


bot = GitLabBot()


def main() -> None:
    """Запуск бота."""
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN не задан!")
        return
    bot.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
