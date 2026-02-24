"""Главное меню бота — persistent view."""

import discord


class MainMenuView(discord.ui.View):
    """Главное меню с кнопками навигации. Persistent (timeout=None)."""

    def __init__(self, show_admin: bool = False) -> None:
        super().__init__(timeout=None)
        if not show_admin:
            self.remove_item(self.admin_button)

    @discord.ui.button(
        label="Подписки",
        style=discord.ButtonStyle.primary,
        custom_id="main:subscriptions",
        row=0,
    )
    async def subscriptions_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Открыть меню подписок."""
        await interaction.response.send_message(
            "Меню подписок будет доступно в следующем обновлении.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Пайплайны",
        style=discord.ButtonStyle.primary,
        custom_id="main:pipelines",
        row=0,
    )
    async def pipelines_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Открыть меню пайплайнов."""
        await interaction.response.send_message(
            "Меню пайплайнов будет доступно в следующем обновлении.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Справка",
        style=discord.ButtonStyle.secondary,
        custom_id="main:help",
        row=0,
    )
    async def help_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать справку."""
        embed = discord.Embed(
            title="Справка",
            description=(
                "**Доступные команды:**\n"
                "`/start` — Главное меню\n"
                "`/help` — Справка\n"
                "`/request_access` — Запрос доступа\n\n"
                "**Кнопки меню:**\n"
                "**Подписки** — управление подписками на проекты\n"
                "**Пайплайны** — история и управление пайплайнами\n"
                "**Админ** — панель администратора (по роли)"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Админ",
        style=discord.ButtonStyle.danger,
        custom_id="main:admin",
        row=1,
    )
    async def admin_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Открыть админ-панель."""
        await interaction.response.send_message(
            "Админ-панель будет доступна в следующем обновлении.",
            ephemeral=True,
        )


def get_main_menu_embed() -> discord.Embed:
    """Embed для главного меню."""
    return discord.Embed(
        title="GitLab Monitor Bot",
        description="Выберите действие:",
        color=discord.Color.blurple(),
    )
