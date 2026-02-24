"""Discord UI компоненты настроек Test IT."""

import logging
from datetime import datetime, timedelta, timezone

import discord

from db_operations import connect_to_db
from scheduler import reschedule_daily_stats_job

logger = logging.getLogger(__name__)

MSK_TZ = timezone(timedelta(hours=3))


# ── Главное меню TestIT ────────────────────────────────────


class TestITMenuView(discord.ui.View):
    """Меню настроек Test IT."""

    def __init__(self) -> None:
        super().__init__(timeout=180)

    @discord.ui.button(
        label="Участники",
        style=discord.ButtonStyle.primary,
        custom_id="testit:participants",
        row=0,
    )
    async def participants_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Список участников с toggle."""
        view = await ParticipantsView.create()
        embed = await ParticipantsView.build_embed(view)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Период",
        style=discord.ButtonStyle.primary,
        custom_id="testit:period",
        row=0,
    )
    async def period_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Настройки периода статистики."""
        embed = discord.Embed(
            title="⏰ Период статистики",
            description="Выберите период подсчёта или установите время:",
            color=discord.Color.blurple(),
        )
        view = PeriodView()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Настройки баллов",
        style=discord.ButtonStyle.primary,
        custom_id="testit:scoring",
        row=0,
    )
    async def scoring_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Настройки весов событий."""
        view = await ScoringView.create()
        embed = await ScoringView.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.secondary,
        custom_id="testit:back_admin",
        row=1,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Назад в админ-панель."""
        from views.admin_views import AdminPanelView

        embed = discord.Embed(
            title="Админ-панель",
            description="Выберите действие:",
            color=discord.Color.red(),
        )
        view = AdminPanelView()
        await interaction.response.edit_message(embed=embed, view=view)


# ── Участники ──────────────────────────────────────────────


class ParticipantsView(discord.ui.View):
    """Список участников Test IT с кнопками toggle."""

    def __init__(self, participants: list) -> None:
        super().__init__(timeout=180)
        self.participants = participants

        for p in participants[:20]:
            self.add_item(ToggleParticipantButton(p["author"], p["is_active"]))

        self.add_item(BackToTestITButton())

    @classmethod
    async def create(cls) -> "ParticipantsView":
        conn = await connect_to_db()
        participants = []
        if conn:
            try:
                participants = await conn.fetch(
                    "SELECT author, is_active FROM testit_participants ORDER BY author;"
                )
            finally:
                await conn.close()
        return cls(participants)

    @staticmethod
    async def build_embed(view: "ParticipantsView") -> discord.Embed:
        if not view.participants:
            return discord.Embed(
                title="👥 Участники Test IT",
                description="Нет участников.",
                color=discord.Color.greyple(),
            )

        lines = []
        for p in view.participants[:20]:
            status = "✅" if p["is_active"] else "❌"
            lines.append(f"{status} **{p['author']}**")

        return discord.Embed(
            title="👥 Участники Test IT",
            description="\n".join(lines) + "\n\nНажмите для включения/выключения:",
            color=discord.Color.blurple(),
        )


class ToggleParticipantButton(discord.ui.Button):
    """Кнопка переключения участника."""

    def __init__(self, author: str, is_active: bool) -> None:
        status = "✅" if is_active else "❌"
        super().__init__(
            label=f"{status} {author}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"testit:toggle:{author}",
        )
        self.author = author

    async def callback(self, interaction: discord.Interaction) -> None:
        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            current = await conn.fetchval(
                "SELECT is_active FROM testit_participants WHERE author = $1;",
                self.author,
            )
            new_status = not current
            await conn.execute(
                "UPDATE testit_participants SET is_active = $1 WHERE author = $2;",
                new_status,
                self.author,
            )
        finally:
            await conn.close()

        view = await ParticipantsView.create()
        embed = await ParticipantsView.build_embed(view)
        await interaction.response.edit_message(embed=embed, view=view)


# ── Период ─────────────────────────────────────────────────


class PeriodView(discord.ui.View):
    """Настройки периода статистики."""

    def __init__(self) -> None:
        super().__init__(timeout=180)

    @discord.ui.button(
        label="📅 Ежедневно",
        style=discord.ButtonStyle.primary,
        custom_id="testit:period_daily",
        row=0,
    )
    async def daily_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = await connect_to_db()
        if conn:
            await conn.execute(
                "UPDATE testit_config SET scoring_period = 'daily', "
                "updated_at = CURRENT_TIMESTAMP WHERE id = 1;"
            )
            await conn.close()
        await interaction.response.send_message(
            "✅ Период установлен: ежедневный", ephemeral=True
        )

    @discord.ui.button(
        label="📆 Еженедельно",
        style=discord.ButtonStyle.primary,
        custom_id="testit:period_weekly",
        row=0,
    )
    async def weekly_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = await connect_to_db()
        if conn:
            await conn.execute(
                "UPDATE testit_config SET scoring_period = 'weekly', "
                "updated_at = CURRENT_TIMESTAMP WHERE id = 1;"
            )
            await conn.close()
        await interaction.response.send_message(
            "✅ Период установлен: еженедельный", ephemeral=True
        )

    @discord.ui.button(
        label="⏰ Время отправки",
        style=discord.ButtonStyle.success,
        custom_id="testit:set_time",
        row=1,
    )
    async def time_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Открыть модальное окно для ввода времени."""
        await interaction.response.send_modal(StatsTimeModal())

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.secondary,
        custom_id="testit:period_back",
        row=1,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class StatsTimeModal(discord.ui.Modal, title="Время отправки статистики"):
    """Модальное окно для ввода времени отправки (ЧЧ:ММ)."""

    time_input = discord.ui.TextInput(
        label="Время (MSK)",
        placeholder="18:00",
        min_length=4,
        max_length=5,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = self.time_input.value.strip()
        try:
            hours, minutes = map(int, text.split(":"))
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Неверный формат. Используйте ЧЧ:ММ (например: 18:00)",
                ephemeral=True,
            )
            return

        now_msk = datetime.now(MSK_TZ)
        target_dt = datetime(
            now_msk.year, now_msk.month, now_msk.day,
            hours, minutes, 0, tzinfo=MSK_TZ,
        )
        next_utc = target_dt.astimezone(timezone.utc)

        conn = await connect_to_db()
        if not conn:
            await interaction.response.send_message("Ошибка БД.", ephemeral=True)
            return

        try:
            await conn.execute(
                "UPDATE scheduled_tasks SET next_execute_at = $1 "
                "WHERE name = 'send_daily_testit_stats';",
                next_utc,
            )
            new_next = await reschedule_daily_stats_job(conn)
            if new_next:
                await interaction.response.send_message(
                    f"✅ Время отправки установлено: {hours:02d}:{minutes:02d} (MSK)",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "❌ Не удалось пересчитать расписание.", ephemeral=True
                )
        finally:
            await conn.close()


# ── Настройки баллов ───────────────────────────────────────


class ScoringView(discord.ui.View):
    """Настройки весов событий Test IT."""

    def __init__(self, created_w: float, updated_w: float, deleted_w: float) -> None:
        super().__init__(timeout=180)
        self.created_w = created_w
        self.updated_w = updated_w
        self.deleted_w = deleted_w

    @classmethod
    async def create(cls) -> "ScoringView":
        conn = await connect_to_db()
        c_w, u_w, d_w = 1.0, 0.1, 0.05
        if conn:
            try:
                row = await conn.fetchrow(
                    "SELECT created_weight, updated_weight, deleted_weight "
                    "FROM testit_config WHERE id = 1;"
                )
                if row:
                    c_w = row["created_weight"] or 1.0
                    u_w = row["updated_weight"] or 0.1
                    d_w = row["deleted_weight"] or 0.05
            finally:
                await conn.close()
        return cls(c_w, u_w, d_w)

    @staticmethod
    async def build_embed() -> discord.Embed:
        return discord.Embed(
            title="⚖️ Настройка весов событий",
            description=(
                "🟢 — учитывается в баллах\n"
                "🔴 — игнорируется\n\n"
                "Нажмите кнопку для изменения веса:"
            ),
            color=discord.Color.blurple(),
        )

    @discord.ui.button(
        label="Вес: Создано",
        style=discord.ButtonStyle.primary,
        custom_id="testit:edit_created_w",
        row=0,
    )
    async def edit_created(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            WeightModal("created", "Создано", self.created_w)
        )

    @discord.ui.button(
        label="Вес: Редактировано",
        style=discord.ButtonStyle.primary,
        custom_id="testit:edit_updated_w",
        row=0,
    )
    async def edit_updated(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            WeightModal("updated", "Отредактировано", self.updated_w)
        )

    @discord.ui.button(
        label="Вес: Удалено",
        style=discord.ButtonStyle.primary,
        custom_id="testit:edit_deleted_w",
        row=0,
    )
    async def edit_deleted(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            WeightModal("deleted", "Удалено", self.deleted_w)
        )

    @discord.ui.button(
        label="Toggle: учёт редактирования",
        style=discord.ButtonStyle.secondary,
        custom_id="testit:toggle_include_updated",
        row=1,
    )
    async def toggle_updated(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = await connect_to_db()
        if conn:
            await conn.execute(
                "UPDATE testit_participants "
                "SET include_updated = NOT ("
                "  SELECT bool_and(include_updated) FROM testit_participants"
                ") WHERE author IN (SELECT author FROM testit_participants);"
            )
            await conn.close()

        view = await ScoringView.create()
        embed = await ScoringView.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Toggle: учёт удаления",
        style=discord.ButtonStyle.secondary,
        custom_id="testit:toggle_include_deleted",
        row=1,
    )
    async def toggle_deleted(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = await connect_to_db()
        if conn:
            await conn.execute(
                "UPDATE testit_participants "
                "SET include_deleted = NOT ("
                "  SELECT bool_and(include_deleted) FROM testit_participants"
                ") WHERE author IN (SELECT author FROM testit_participants);"
            )
            await conn.close()

        view = await ScoringView.create()
        embed = await ScoringView.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.secondary,
        custom_id="testit:scoring_back",
        row=2,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class WeightModal(discord.ui.Modal):
    """Модальное окно для ввода веса события."""

    weight_input = discord.ui.TextInput(
        label="Новое значение",
        placeholder="1.0",
        min_length=1,
        max_length=5,
        required=True,
    )

    def __init__(self, weight_type: str, label: str, current: float) -> None:
        super().__init__(title=f"Вес: {label}")
        self.weight_type = weight_type
        self.weight_input.default = str(current)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            value = float(self.weight_input.value.strip())
            if value < 0 or value > 10:
                await interaction.response.send_message(
                    "Значение должно быть от 0 до 10.", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Введите число (например: 1.0)", ephemeral=True
            )
            return

        field_map = {
            "created": "created_weight",
            "updated": "updated_weight",
            "deleted": "deleted_weight",
        }
        column = field_map[self.weight_type]

        conn = await connect_to_db()
        if conn:
            await conn.execute(
                f"UPDATE testit_config SET {column} = $1, "  # noqa: S608
                "updated_at = CURRENT_TIMESTAMP WHERE id = 1;",
                value,
            )
            await conn.close()

        await interaction.response.send_message(
            f"✅ {column} обновлён: {value}", ephemeral=True
        )


# ── Общие компоненты ───────────────────────────────────────


class BackToTestITButton(discord.ui.Button):
    """Кнопка 'Назад' в меню Test IT."""

    def __init__(self) -> None:
        super().__init__(
            label="Назад",
            style=discord.ButtonStyle.secondary,
            custom_id="testit:back_menu",
            row=4,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🎮 Настройки Test IT",
            description="Выберите раздел:",
            color=discord.Color.blurple(),
        )
        view = TestITMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
