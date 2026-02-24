"""Slash-команды администратора: /admin."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config_loader import DISCORD_ADMIN_ROLE
from views.admin_views import AdminPanelView, AccessRequestsView, UsersView

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Команды администрирования бота."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    admin_group = app_commands.Group(
        name="admin",
        description="Панель администратора",
    )

    @admin_group.command(name="panel", description="Открыть админ-панель")
    @app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
    async def admin_panel(self, interaction: discord.Interaction) -> None:
        """Главное меню админ-панели."""
        embed = discord.Embed(
            title="Админ-панель",
            description="Выберите действие:",
            color=discord.Color.red(),
        )
        view = AdminPanelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_group.command(
        name="requests", description="Просмотр запросов на доступ"
    )
    @app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
    async def admin_requests(self, interaction: discord.Interaction) -> None:
        """Список pending-запросов с кнопками approve/reject."""
        view = await AccessRequestsView.create(self.bot)
        embed = await AccessRequestsView.build_embed(view)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_group.command(name="users", description="Управление пользователями")
    @app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
    async def admin_users(self, interaction: discord.Interaction) -> None:
        """Список пользователей с кнопками ban/unban."""
        view = await UsersView.create(self.bot)
        embed = await UsersView.build_embed(view)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_group.command(
        name="testit", description="Настройки Test IT"
    )
    @app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
    async def admin_testit(self, interaction: discord.Interaction) -> None:
        """Меню настроек Test IT."""
        from views.testit_views import TestITMenuView

        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_panel.error
    @admin_requests.error
    @admin_users.error
    @admin_testit.error
    async def admin_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Обработка ошибки отсутствия роли."""
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message(
                "У вас нет доступа к админ-панели.", ephemeral=True
            )
        else:
            logger.error(f"Ошибка в admin: {error}", exc_info=True)
            await interaction.response.send_message(
                "Произошла ошибка.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Регистрация cog."""
    await bot.add_cog(AdminCog(bot))
