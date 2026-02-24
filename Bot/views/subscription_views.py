"""Views для системы подписок: выбор проектов, подписка/отписка."""

import logging

import discord

from config_loader import FIXED_PROJECTS
from db_operations import connect_to_db

logger = logging.getLogger(__name__)


def _resolve_source(interaction: discord.Interaction) -> tuple[str, int | None, int | None, int | None]:
    """Определяет контекст подписки: source_type, channel_id, thread_id, guild_id."""
    guild_id = interaction.guild_id

    if interaction.guild is None:
        # DM
        return "dm", None, None, guild_id

    channel = interaction.channel
    if isinstance(channel, discord.Thread):
        return "thread", channel.parent_id, channel.id, guild_id

    return "channel", channel.id, None, guild_id


class SubscriptionMenuView(discord.ui.View):
    """Меню подписок: Select для проектов, кнопки для камер/TestIT."""

    def __init__(self) -> None:
        super().__init__(timeout=180)

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Выберите проект...",
        custom_id="sub:project_select",
        row=0,
    )
    async def project_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        """Обработка выбора проекта из списка."""
        project_id = select.values[0]
        project_name = FIXED_PROJECTS.get(project_id, "Проект")
        view = await ProjectSubscriptionView.create(interaction, project_id)
        embed = discord.Embed(
            title=f"Подписки — {project_name}",
            description="Управляйте подписками на уведомления:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Камеры",
        style=discord.ButtonStyle.secondary,
        custom_id="sub:cameras",
        row=1,
    )
    async def cameras_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Подписка/отписка на статусы камер."""
        user_id = interaction.user.id
        source_type, channel_id, thread_id, guild_id = _resolve_source(interaction)

        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка подключения к БД.", ephemeral=True)
            return

        try:
            existing = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1
                  AND project_id = 'camera_monitoring'
                  AND notification_type IN ('camera_status', 'camera_new', 'camera_transfer')
                  AND source_type = $2
                  AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                  AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                """,
                user_id, source_type, channel_id, thread_id,
            )

            if existing:
                await conn.execute(
                    """
                    DELETE FROM subscribers
                    WHERE user_id = $1
                      AND project_id = 'camera_monitoring'
                      AND notification_type IN ('camera_status', 'camera_new', 'camera_transfer')
                      AND source_type = $2
                      AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                      AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                    """,
                    user_id, source_type, channel_id, thread_id,
                )
                text = "Вы отписались от уведомлений о камерах."
            else:
                for ntype in ("camera_status", "camera_new", "camera_transfer"):
                    await conn.execute(
                        """
                        INSERT INTO subscribers (user_id, project_id, notification_type, channel_id, thread_id, guild_id, source_type)
                        VALUES ($1, 'camera_monitoring', $2, $3, $4, $5, $6)
                        ON CONFLICT DO NOTHING;
                        """,
                        user_id, ntype, channel_id, thread_id, guild_id, source_type,
                    )
                text = "Вы подписались на уведомления о камерах."
        finally:
            await conn.close()

        # Обновляем кнопку
        view = await SubscriptionMenuView.create_with_state(interaction)
        embed = discord.Embed(title="Подписки", description=text, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Test IT",
        style=discord.ButtonStyle.secondary,
        custom_id="sub:testit",
        row=1,
    )
    async def testit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Подписка/отписка на Test IT уведомления."""
        user_id = interaction.user.id
        source_type, channel_id, thread_id, guild_id = _resolve_source(interaction)

        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка подключения к БД.", ephemeral=True)
            return

        try:
            existing = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1
                  AND notification_type = 'testit_case'
                  AND (project_id = '*' OR project_id IS NULL)
                  AND source_type = $2
                  AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                  AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                """,
                user_id, source_type, channel_id, thread_id,
            )

            if existing:
                await conn.execute(
                    """
                    DELETE FROM subscribers
                    WHERE user_id = $1
                      AND notification_type = 'testit_case'
                      AND (project_id = '*' OR project_id IS NULL)
                      AND source_type = $2
                      AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                      AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                    """,
                    user_id, source_type, channel_id, thread_id,
                )
                text = "Вы отписались от уведомлений Test IT."
            else:
                await conn.execute(
                    """
                    INSERT INTO subscribers (user_id, project_id, notification_type, channel_id, thread_id, guild_id, source_type)
                    VALUES ($1, '*', 'testit_case', $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING;
                    """,
                    user_id, channel_id, thread_id, guild_id, source_type,
                )
                text = "Вы подписались на уведомления Test IT."
        finally:
            await conn.close()

        view = await SubscriptionMenuView.create_with_state(interaction)
        embed = discord.Embed(title="Подписки", description=text, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.danger,
        custom_id="sub:back_main",
        row=2,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться в главное меню."""
        from views.main_menu import MainMenuView, get_main_menu_embed
        from cogs.general import has_admin_role

        is_admin = has_admin_role(interaction)
        embed = get_main_menu_embed()
        view = MainMenuView(show_admin=is_admin)
        await interaction.response.edit_message(embed=embed, view=view)

    @classmethod
    async def create_with_state(cls, interaction: discord.Interaction) -> "SubscriptionMenuView":
        """Создаёт view с актуальными label-ами кнопок (подписан/отписан)."""
        view = cls()
        user_id = interaction.user.id
        source_type, channel_id, thread_id, _ = _resolve_source(interaction)

        # Заполняем Select опциями проектов
        view.project_select.options = [
            discord.SelectOption(label=name, value=pid, description=f"ID: {pid}")
            for pid, name in FIXED_PROJECTS.items()
        ]

        conn = await connect_to_db()
        if not conn:
            return view

        try:
            # Проверяем подписку на камеры
            camera_sub = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1
                  AND project_id = 'camera_monitoring'
                  AND notification_type IN ('camera_status', 'camera_new', 'camera_transfer')
                  AND source_type = $2
                  AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                  AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                """,
                user_id, source_type, channel_id, thread_id,
            )
            if camera_sub:
                view.cameras_button.label = "Отписаться от камер"
                view.cameras_button.style = discord.ButtonStyle.danger
            else:
                view.cameras_button.label = "Камеры"
                view.cameras_button.style = discord.ButtonStyle.secondary

            # Проверяем подписку на TestIT
            testit_sub = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1
                  AND notification_type = 'testit_case'
                  AND (project_id = '*' OR project_id IS NULL)
                  AND source_type = $2
                  AND (channel_id = $3 OR (channel_id IS NULL AND $3::bigint IS NULL))
                  AND (thread_id = $4 OR (thread_id IS NULL AND $4::bigint IS NULL));
                """,
                user_id, source_type, channel_id, thread_id,
            )
            if testit_sub:
                view.testit_button.label = "Отписаться от Test IT"
                view.testit_button.style = discord.ButtonStyle.danger
            else:
                view.testit_button.label = "Test IT"
                view.testit_button.style = discord.ButtonStyle.secondary
        finally:
            await conn.close()

        return view


class ProjectSubscriptionView(discord.ui.View):
    """Подписки на пайплайны и MR для конкретного проекта."""

    def __init__(self, project_id: str) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id

    @discord.ui.button(
        label="Подписаться на пайплайны",
        style=discord.ButtonStyle.primary,
        custom_id="sub:pipelines",
        row=0,
    )
    async def pipelines_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Подписка/отписка на пайплайны проекта."""
        await self._toggle_subscription(interaction, "pipeline", "пайплайны")

    @discord.ui.button(
        label="Подписаться на MR",
        style=discord.ButtonStyle.primary,
        custom_id="sub:mr",
        row=0,
    )
    async def mr_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Подписка/отписка на MR проекта."""
        await self._toggle_subscription(interaction, "mr", "MR")

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.danger,
        custom_id="sub:back_projects",
        row=1,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к списку проектов."""
        view = await SubscriptionMenuView.create_with_state(interaction)
        embed = discord.Embed(
            title="Подписки",
            description="Выберите проект или тип подписки:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _toggle_subscription(
        self,
        interaction: discord.Interaction,
        notification_type: str,
        label_ru: str,
    ) -> None:
        """Универсальная подписка/отписка для проекта."""
        user_id = interaction.user.id
        source_type, channel_id, thread_id, guild_id = _resolve_source(interaction)
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")

        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка подключения к БД.", ephemeral=True)
            return

        try:
            existing = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1
                  AND project_id = $2
                  AND notification_type = $3
                  AND source_type = $4
                  AND (channel_id = $5 OR (channel_id IS NULL AND $5::bigint IS NULL))
                  AND (thread_id = $6 OR (thread_id IS NULL AND $6::bigint IS NULL));
                """,
                user_id, self.project_id, notification_type,
                source_type, channel_id, thread_id,
            )

            if existing:
                await conn.execute(
                    """
                    DELETE FROM subscribers
                    WHERE user_id = $1
                      AND project_id = $2
                      AND notification_type = $3
                      AND source_type = $4
                      AND (channel_id = $5 OR (channel_id IS NULL AND $5::bigint IS NULL))
                      AND (thread_id = $6 OR (thread_id IS NULL AND $6::bigint IS NULL));
                    """,
                    user_id, self.project_id, notification_type,
                    source_type, channel_id, thread_id,
                )
                text = f"Вы отписались от {label_ru} проекта {project_name}."
            else:
                await conn.execute(
                    """
                    INSERT INTO subscribers (user_id, project_id, notification_type, channel_id, thread_id, guild_id, source_type)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING;
                    """,
                    user_id, self.project_id, notification_type,
                    channel_id, thread_id, guild_id, source_type,
                )
                text = f"Вы подписались на {label_ru} проекта {project_name}."
        finally:
            await conn.close()

        view = await ProjectSubscriptionView.create(interaction, self.project_id)
        embed = discord.Embed(
            title=f"Подписки — {project_name}",
            description=text,
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @classmethod
    async def create(
        cls, interaction: discord.Interaction, project_id: str
    ) -> "ProjectSubscriptionView":
        """Создаёт view с актуальным состоянием кнопок."""
        view = cls(project_id)
        user_id = interaction.user.id
        source_type, channel_id, thread_id, _ = _resolve_source(interaction)

        conn = await connect_to_db()
        if not conn:
            return view

        try:
            # Пайплайны
            pipe_sub = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1 AND project_id = $2 AND notification_type = 'pipeline'
                  AND source_type = $3
                  AND (channel_id = $4 OR (channel_id IS NULL AND $4::bigint IS NULL))
                  AND (thread_id = $5 OR (thread_id IS NULL AND $5::bigint IS NULL));
                """,
                user_id, project_id, source_type, channel_id, thread_id,
            )
            if pipe_sub:
                view.pipelines_button.label = "Отписаться от пайплайнов"
                view.pipelines_button.style = discord.ButtonStyle.danger
            else:
                view.pipelines_button.label = "Подписаться на пайплайны"
                view.pipelines_button.style = discord.ButtonStyle.primary

            # MR
            mr_sub = await conn.fetch(
                """
                SELECT id FROM subscribers
                WHERE user_id = $1 AND project_id = $2 AND notification_type = 'mr'
                  AND source_type = $3
                  AND (channel_id = $4 OR (channel_id IS NULL AND $4::bigint IS NULL))
                  AND (thread_id = $5 OR (thread_id IS NULL AND $5::bigint IS NULL));
                """,
                user_id, project_id, source_type, channel_id, thread_id,
            )
            if mr_sub:
                view.mr_button.label = "Отписаться от MR"
                view.mr_button.style = discord.ButtonStyle.danger
            else:
                view.mr_button.label = "Подписаться на MR"
                view.mr_button.style = discord.ButtonStyle.primary
        finally:
            await conn.close()

        return view
