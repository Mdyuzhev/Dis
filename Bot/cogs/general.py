"""Базовые slash-команды: /start, /help, /request_access."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config_loader import DISCORD_ADMIN_ROLE, FIXED_PROJECTS
from db_operations import connect_to_db
from views.main_menu import MainMenuView, get_main_menu_embed

logger = logging.getLogger(__name__)


def has_admin_role(interaction: discord.Interaction) -> bool:
    """Проверяет наличие роли администратора у пользователя."""
    if not interaction.guild:
        return False
    return any(role.name == DISCORD_ADMIN_ROLE for role in interaction.user.roles)


async def check_user_access(user_id: int) -> str | None:
    """Проверяет статус пользователя в white_list. Возвращает status или None."""
    conn = await connect_to_db()
    if not conn:
        return None
    try:
        return await conn.fetchval(
            "SELECT status FROM white_list WHERE user_id = $1;",
            user_id,
        )
    finally:
        await conn.close()


class GeneralCog(commands.Cog):
    """Базовые команды бота."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="start", description="Главное меню бота")
    async def start(self, interaction: discord.Interaction) -> None:
        """Показать главное меню с проверкой доступа."""
        user_id = interaction.user.id
        user_status = await check_user_access(user_id)

        if user_status == "banned":
            await interaction.response.send_message(
                "Ваш аккаунт заблокирован. Обратитесь к администратору.",
                ephemeral=True,
            )
            return

        is_admin = has_admin_role(interaction)

        if is_admin or user_status == "approved":
            embed = get_main_menu_embed()
            view = MainMenuView(show_admin=is_admin)
            await interaction.response.send_message(embed=embed, view=view)
            return

        if user_status == "pending":
            await interaction.response.send_message(
                "Ваш запрос на доступ отправлен. Ожидайте решения администратора.",
                ephemeral=True,
            )
            return

        # Нет доступа — предложить запросить
        await interaction.response.send_message(
            "У вас нет доступа к боту. Используйте `/request_access` для запроса.",
            ephemeral=True,
        )

    @app_commands.command(name="help", description="Справка по командам бота")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Показать справку."""
        projects_list = "\n".join(
            f"• **{name}** (ID: {pid})" for pid, name in FIXED_PROJECTS.items()
        )
        embed = discord.Embed(
            title="Справка — GitLab Monitor Bot",
            description=(
                "**Команды:**\n"
                "`/start` — Главное меню\n"
                "`/help` — Справка\n"
                "`/request_access` — Запрос доступа\n\n"
                f"**Проекты:**\n{projects_list}"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="request_access", description="Запросить доступ к боту"
    )
    async def request_access(self, interaction: discord.Interaction) -> None:
        """Создание запроса на доступ в БД, уведомление админов."""
        user_id = interaction.user.id

        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message(
                "Ошибка подключения к БД.", ephemeral=True
            )
            return

        try:
            user_status = await conn.fetchval(
                "SELECT status FROM white_list WHERE user_id = $1;", user_id
            )

            if user_status == "banned":
                message = "Ваш аккаунт заблокирован. Обратитесь к администратору."
            elif user_status == "approved":
                message = "У вас уже есть доступ к боту."
            elif user_status == "pending":
                message = "Ваш запрос уже отправлен. Ожидайте решения администратора."
            else:
                # Создаём запрос
                await conn.execute(
                    """
                    INSERT INTO white_list (user_id, role, status)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id) DO UPDATE
                    SET role = EXCLUDED.role, status = EXCLUDED.status;
                    """,
                    user_id,
                    "user",
                    "pending",
                )
                message = "Ваш запрос на доступ отправлен. Ожидайте решения администратора."

                # Уведомление в канал с ролью BotAdmin
                await self._notify_admins(interaction)

            await interaction.response.send_message(message, ephemeral=True)
        finally:
            await conn.close()

    async def _notify_admins(self, interaction: discord.Interaction) -> None:
        """Отправка уведомления о новом запросе в первый канал, доступный боту."""
        if not interaction.guild:
            return

        embed = discord.Embed(
            title="Новый запрос на доступ",
            description=(
                f"**Пользователь:** {interaction.user.mention} "
                f"({interaction.user.name}, ID: {interaction.user.id})"
            ),
            color=discord.Color.yellow(),
        )
        embed.add_field(
            name="Действия",
            value="Используйте админ-панель для одобрения/отклонения.",
        )

        # Отправляем в system_channel или первый текстовый канал
        channel = interaction.guild.system_channel
        if not channel:
            for ch in interaction.guild.text_channels:
                if ch.permissions_for(interaction.guild.me).send_messages:
                    channel = ch
                    break

        if channel:
            await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Регистрация cog."""
    await bot.add_cog(GeneralCog(bot))
