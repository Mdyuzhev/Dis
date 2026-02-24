"""Cog подписок: /subscribe — управление подписками на уведомления."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.general import check_user_access, has_admin_role
from views.subscription_views import SubscriptionMenuView

logger = logging.getLogger(__name__)


class SubscriptionsCog(commands.Cog):
    """Управление подписками на пайплайны, MR, камеры, TestIT."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="subscribe", description="Управление подписками на уведомления")
    async def subscribe(self, interaction: discord.Interaction) -> None:
        """Открыть меню подписок с проверкой доступа."""
        user_id = interaction.user.id
        user_status = await check_user_access(user_id)
        is_admin = has_admin_role(interaction)

        if not is_admin and user_status != "approved":
            await interaction.response.send_message(
                "У вас нет доступа. Используйте `/request_access`.",
                ephemeral=True,
            )
            return

        view = await SubscriptionMenuView.create_with_state(interaction)
        embed = discord.Embed(
            title="Подписки",
            description="Выберите проект или тип подписки:",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Регистрация cog."""
    await bot.add_cog(SubscriptionsCog(bot))
