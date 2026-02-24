"""Discord UI компоненты админ-панели."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from db_operations import connect_to_db

logger = logging.getLogger(__name__)


# ── Админ-панель ───────────────────────────────────────────


class AdminPanelView(discord.ui.View):
    """Главное меню админ-панели. Ephemeral."""

    def __init__(self) -> None:
        super().__init__(timeout=180)

    @discord.ui.button(
        label="Запросы на доступ",
        style=discord.ButtonStyle.primary,
        custom_id="admin:requests",
        row=0,
    )
    async def requests_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать запросы на доступ."""
        view = await AccessRequestsView.create(interaction.client)
        embed = await AccessRequestsView.build_embed(view)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Пользователи",
        style=discord.ButtonStyle.primary,
        custom_id="admin:users",
        row=0,
    )
    async def users_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать список пользователей."""
        view = await UsersView.create(interaction.client)
        embed = await UsersView.build_embed(view)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Test IT",
        style=discord.ButtonStyle.primary,
        custom_id="admin:testit",
        row=0,
    )
    async def testit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать настройки Test IT."""
        from views.testit_views import TestITMenuView

        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.secondary,
        custom_id="admin:back_main",
        row=1,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться в главное меню."""
        from views.main_menu import MainMenuView, get_main_menu_embed

        embed = get_main_menu_embed()
        view = MainMenuView(show_admin=True)
        await interaction.response.edit_message(embed=embed, view=view)


# ── Запросы на доступ ──────────────────────────────────────


class AccessRequestsView(discord.ui.View):
    """Список pending-запросов с кнопками Approve/Reject."""

    def __init__(self, bot: commands.Bot, requests: list) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.requests = requests

        for req in requests[:10]:
            user_id = req["user_id"]
            self.add_item(ApproveButton(user_id))
            self.add_item(RejectButton(user_id))

        self.add_item(BackToAdminButton())

    @classmethod
    async def create(cls, bot: commands.Bot) -> "AccessRequestsView":
        """Создаёт view, загружая данные из БД."""
        conn = await connect_to_db()
        requests = []
        if conn:
            try:
                requests = await conn.fetch(
                    "SELECT user_id FROM white_list WHERE status = 'pending';"
                )
            finally:
                await conn.close()
        return cls(bot, requests)

    @staticmethod
    async def build_embed(view: "AccessRequestsView") -> discord.Embed:
        """Формирует embed со списком запросов."""
        if not view.requests:
            return discord.Embed(
                title="Запросы на доступ",
                description="Нет новых запросов.",
                color=discord.Color.green(),
            )

        desc_lines = []
        for req in view.requests[:10]:
            user_id = req["user_id"]
            desc_lines.append(f"• Пользователь: `{user_id}`")

        return discord.Embed(
            title="Запросы на доступ",
            description="\n".join(desc_lines),
            color=discord.Color.yellow(),
        )


class ApproveButton(discord.ui.Button):
    """Кнопка одобрения запроса."""

    def __init__(self, user_id: int) -> None:
        super().__init__(
            label=f"✅ {user_id}",
            style=discord.ButtonStyle.success,
            custom_id=f"admin:approve:{user_id}",
        )
        self.target_user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            result = await conn.execute(
                "UPDATE white_list SET status = 'approved' "
                "WHERE user_id = $1 AND status = 'pending';",
                self.target_user_id,
            )
            if result == "UPDATE 1":
                # DM пользователю
                try:
                    user = interaction.client.get_user(
                        self.target_user_id
                    ) or await interaction.client.fetch_user(self.target_user_id)
                    await user.send("Ваш запрос на доступ одобрен!")
                except Exception as e:
                    logger.warning(f"Не удалось отправить DM {self.target_user_id}: {e}")

                # Обновляем view
                view = await AccessRequestsView.create(interaction.client)
                embed = await AccessRequestsView.build_embed(view)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"Запрос для {self.target_user_id} не найден.", ephemeral=True
                )
        finally:
            await conn.close()


class RejectButton(discord.ui.Button):
    """Кнопка отклонения запроса."""

    def __init__(self, user_id: int) -> None:
        super().__init__(
            label=f"❌ {user_id}",
            style=discord.ButtonStyle.danger,
            custom_id=f"admin:reject:{user_id}",
        )
        self.target_user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            result = await conn.execute(
                "UPDATE white_list SET status = 'rejected' "
                "WHERE user_id = $1 AND status = 'pending';",
                self.target_user_id,
            )
            if result == "UPDATE 1":
                try:
                    user = interaction.client.get_user(
                        self.target_user_id
                    ) or await interaction.client.fetch_user(self.target_user_id)
                    await user.send("Ваш запрос на доступ был отклонён.")
                except Exception as e:
                    logger.warning(f"Не удалось отправить DM {self.target_user_id}: {e}")

                view = await AccessRequestsView.create(interaction.client)
                embed = await AccessRequestsView.build_embed(view)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"Запрос для {self.target_user_id} не найден.", ephemeral=True
                )
        finally:
            await conn.close()


# ── Управление пользователями ──────────────────────────────


class UsersView(discord.ui.View):
    """Список пользователей с кнопками Ban/Unban."""

    def __init__(self, bot: commands.Bot, users: list) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.users = users

        for u in users[:20]:
            user_id = u["user_id"]
            status = u["status"]
            role = u["role"]

            if status == "approved" and role == "user":
                self.add_item(BanButton(user_id))
            elif status in ("rejected", "banned"):
                self.add_item(UnbanButton(user_id))

        self.add_item(BackToAdminButton())

    @classmethod
    async def create(cls, bot: commands.Bot) -> "UsersView":
        """Создаёт view, загружая данные из БД."""
        conn = await connect_to_db()
        users = []
        if conn:
            try:
                users = await conn.fetch(
                    "SELECT user_id, status, role FROM white_list ORDER BY user_id;"
                )
            finally:
                await conn.close()
        return cls(bot, users)

    @staticmethod
    async def build_embed(view: "UsersView") -> discord.Embed:
        """Формирует embed со списком пользователей."""
        if not view.users:
            return discord.Embed(
                title="Пользователи",
                description="Нет пользователей.",
                color=discord.Color.greyple(),
            )

        status_emoji = {
            "approved": "🟢",
            "pending": "🟡",
            "rejected": "🔴",
            "banned": "⛔",
        }

        desc_lines = []
        for u in view.users[:20]:
            emoji = status_emoji.get(u["status"], "❓")
            desc_lines.append(
                f"{emoji} `{u['user_id']}` — {u['status']} ({u['role']})"
            )

        return discord.Embed(
            title="Пользователи",
            description="\n".join(desc_lines),
            color=discord.Color.blurple(),
        )


class BanButton(discord.ui.Button):
    """Кнопка бана пользователя."""

    def __init__(self, user_id: int) -> None:
        super().__init__(
            label=f"🔒 Бан {user_id}",
            style=discord.ButtonStyle.danger,
            custom_id=f"admin:ban:{user_id}",
        )
        self.target_user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            result = await conn.execute(
                "UPDATE white_list SET status = 'banned' "
                "WHERE user_id = $1 AND status = 'approved' AND role = 'user';",
                self.target_user_id,
            )
            if result == "UPDATE 1":
                try:
                    user = interaction.client.get_user(
                        self.target_user_id
                    ) or await interaction.client.fetch_user(self.target_user_id)
                    await user.send("Ваш доступ был заблокирован администратором.")
                except Exception as e:
                    logger.warning(f"Не удалось отправить DM {self.target_user_id}: {e}")

                view = await UsersView.create(interaction.client)
                embed = await UsersView.build_embed(view)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"Не удалось забанить {self.target_user_id}.", ephemeral=True
                )
        finally:
            await conn.close()


class UnbanButton(discord.ui.Button):
    """Кнопка разбана пользователя."""

    def __init__(self, user_id: int) -> None:
        super().__init__(
            label=f"🔓 Разбан {user_id}",
            style=discord.ButtonStyle.success,
            custom_id=f"admin:unban:{user_id}",
        )
        self.target_user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            result = await conn.execute(
                "UPDATE white_list SET status = 'pending' "
                "WHERE user_id = $1 AND status IN ('banned', 'rejected');",
                self.target_user_id,
            )
            if result == "UPDATE 1":
                try:
                    user = interaction.client.get_user(
                        self.target_user_id
                    ) or await interaction.client.fetch_user(self.target_user_id)
                    await user.send(
                        "Ваш доступ восстановлен. Ожидается рассмотрение заявки."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить DM {self.target_user_id}: {e}")

                view = await UsersView.create(interaction.client)
                embed = await UsersView.build_embed(view)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"Не удалось разбанить {self.target_user_id}.", ephemeral=True
                )
        finally:
            await conn.close()


# ── Общие компоненты ───────────────────────────────────────


class BackToAdminButton(discord.ui.Button):
    """Кнопка 'Назад' в админ-панель."""

    def __init__(self) -> None:
        super().__init__(
            label="Назад",
            style=discord.ButtonStyle.secondary,
            custom_id="admin:back_panel",
            row=4,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Админ-панель",
            description="Выберите действие:",
            color=discord.Color.red(),
        )
        view = AdminPanelView()
        await interaction.response.edit_message(embed=embed, view=view)
