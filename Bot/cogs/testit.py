"""Slash-команда /testit — быстрый доступ к настройкам Test IT."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config_loader import DISCORD_ADMIN_ROLE
from views.testit_views import TestITMenuView

logger = logging.getLogger(__name__)


class TestITCog(commands.Cog):
    """Настройки Test IT."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="testit", description="Настройки Test IT (только для админов)"
    )
    @app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
    async def testit_settings(self, interaction: discord.Interaction) -> None:
        """Открыть меню настроек Test IT."""
        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @testit_settings.error
    async def testit_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message(
                "У вас нет доступа к настройкам Test IT.", ephemeral=True
            )
        else:
            logger.error(f"Ошибка в testit: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка.", ephemeral=True
                )


async def setup(bot: commands.Bot) -> None:
    """Регистрация cog."""
    await bot.add_cog(TestITCog(bot))
