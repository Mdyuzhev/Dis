"""Cog пайплайнов: /pipelines — история, расписания, отчёты, .properties."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.general import check_user_access, has_admin_role
from config_loader import FIXED_PROJECTS
from views.pipeline_views import PipelineProjectSelectView

logger = logging.getLogger(__name__)


class PipelinesCog(commands.Cog):
    """Управление пайплайнами: история, расписания, Allure-отчёты."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pipelines", description="Просмотр пайплайнов, расписаний и отчётов")
    @app_commands.describe(project="Название или ID проекта")
    async def pipelines(
        self, interaction: discord.Interaction, project: str | None = None
    ) -> None:
        """Открыть меню пайплайнов с проверкой доступа."""
        user_id = interaction.user.id
        user_status = await check_user_access(user_id)
        is_admin = has_admin_role(interaction)

        if not is_admin and user_status != "approved":
            await interaction.response.send_message(
                "У вас нет доступа. Используйте `/request_access`.",
                ephemeral=True,
            )
            return

        # Если указан проект — сразу к опциям
        if project:
            project_id = _resolve_project(project)
            if project_id:
                from views.pipeline_views import PipelineOptionsView

                project_name = FIXED_PROJECTS[project_id]
                view = PipelineOptionsView(project_id)
                embed = discord.Embed(
                    title=f"Пайплайны — {project_name}",
                    description="Выберите действие:",
                    color=discord.Color.blurple(),
                )
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

        # Иначе — список проектов
        view = PipelineProjectSelectView()
        embed = discord.Embed(
            title="Пайплайны",
            description="Выберите проект:",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @pipelines.autocomplete("project")
    async def project_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Автокомплит названий проектов."""
        choices = []
        for pid, name in FIXED_PROJECTS.items():
            if current.lower() in name.lower() or current in pid:
                choices.append(app_commands.Choice(name=f"{name} ({pid})", value=pid))
        return choices[:25]


def _resolve_project(value: str) -> str | None:
    """Разрешает проект по ID или названию."""
    if value in FIXED_PROJECTS:
        return value
    for pid, name in FIXED_PROJECTS.items():
        if value.lower() in name.lower():
            return pid
    return None


async def setup(bot: commands.Bot) -> None:
    """Регистрация cog."""
    await bot.add_cog(PipelinesCog(bot))
