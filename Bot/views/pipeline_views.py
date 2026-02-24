"""Views для пайплайнов: история, расписания, Allure-отчёты, .properties."""

import logging
from datetime import datetime

import discord

from config_loader import FIXED_PROJECTS
from db_operations import connect_to_db
from gitlab_api import (
    get_pipelines,
    get_pipeline_details,
    get_pipeline_schedules,
    get_pipeline_schedule_details,
    play_pipeline_schedule,
    get_root_files,
    get_file_content,
    update_file_content,
    get_camera_statuses_from_env,
)

logger = logging.getLogger(__name__)

STATUS_EMOJI = {
    "success": "\u2705",
    "failed": "\u274c",
    "running": "\ud83d\udd04",
    "pending": "\u23f3",
}

STATUS_COLOR = {
    "success": discord.Color.green(),
    "failed": discord.Color.red(),
    "running": discord.Color.blue(),
    "pending": discord.Color.yellow(),
}


class PipelineProjectSelectView(discord.ui.View):
    """Выбор проекта для просмотра пайплайнов."""

    def __init__(self) -> None:
        super().__init__(timeout=180)
        options = [
            discord.SelectOption(label=name, value=pid, description=f"ID: {pid}")
            for pid, name in FIXED_PROJECTS.items()
        ]
        self.project_select.options = options

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Выберите проект...",
        custom_id="pipe:project_select",
        row=0,
    )
    async def project_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        """Обработка выбора проекта."""
        project_id = select.values[0]
        project_name = FIXED_PROJECTS.get(project_id, "Проект")
        view = PipelineOptionsView(project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Назад",
        style=discord.ButtonStyle.danger,
        custom_id="pipe:back_main",
        row=1,
    )
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться в главное меню."""
        from views.main_menu import MainMenuView, get_main_menu_embed
        from cogs.general import has_admin_role

        embed = get_main_menu_embed()
        view = MainMenuView(show_admin=has_admin_role(interaction))
        await interaction.response.edit_message(embed=embed, view=view)


class PipelineOptionsView(discord.ui.View):
    """Опции для выбранного проекта: история, расписания, отчёты, .properties."""

    def __init__(self, project_id: str) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id

    @discord.ui.button(label="История", style=discord.ButtonStyle.primary, row=0)
    async def history_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать последние пайплайны."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")

        try:
            pipelines_list = await get_pipelines(self.project_id)
        except Exception as e:
            logger.error(f"Ошибка получения пайплайнов: {e}")
            await interaction.followup.send("Ошибка при обращении к GitLab API.", ephemeral=True)
            return

        if not pipelines_list:
            await interaction.followup.send(
                f"Нет пайплайнов для проекта {project_name}.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"История пайплайнов — {project_name}",
            color=discord.Color.blurple(),
        )

        for pipeline in pipelines_list[:5]:
            emoji = STATUS_EMOJI.get(pipeline["status"], "\u2753")
            try:
                details = await get_pipeline_details(self.project_id, pipeline["id"])
                updated_at = details.get("updated_at", "") if details else ""
                dt = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                time_str = dt.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                time_str = "—"

            embed.add_field(
                name=f"{emoji} #{pipeline['id']} — {pipeline['status']}",
                value=f"Ветка: `{pipeline['ref']}`\nОбновлён: {time_str}",
                inline=False,
            )

        view = PipelineHistoryView(self.project_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Расписания", style=discord.ButtonStyle.primary, row=0)
    async def schedules_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать расписания пайплайнов."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")

        try:
            schedules = await get_pipeline_schedules(self.project_id)
        except Exception as e:
            logger.error(f"Ошибка получения расписаний: {e}")
            await interaction.followup.send("Ошибка при обращении к GitLab API.", ephemeral=True)
            return

        if not schedules:
            await interaction.followup.send(
                f"Нет расписаний для проекта {project_name}.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Расписания — {project_name}",
            color=discord.Color.blurple(),
        )

        for schedule in schedules[:10]:
            active = "\ud83d\udfe2" if schedule["active"] else "\ud83d\udd34"
            desc = schedule.get("description", "Без описания")
            cron = schedule["cron"]
            ref = schedule["ref"].replace("refs/heads/", "")
            embed.add_field(
                name=f"{active} {desc}",
                value=f"Cron: `{cron}`\nВетка: `{ref}`\nID: `{schedule['id']}`",
                inline=False,
            )

        view = SchedulesView(self.project_id, schedules[:10])
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Отчёты", style=discord.ButtonStyle.primary, row=0)
    async def reports_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать Allure-отчёты."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed, view = await _build_allure_page(self.project_id, page=1)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label=".properties", style=discord.ButtonStyle.secondary, row=1)
    async def properties_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Показать список .properties файлов."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        path = "src/test/resources/"

        try:
            files = await get_root_files(self.project_id, path)
        except Exception as e:
            logger.error(f"Ошибка получения .properties: {e}")
            await interaction.followup.send("Ошибка при загрузке файлов.", ephemeral=True)
            return

        if not files:
            await interaction.followup.send(
                f"Нет .properties файлов в проекте {project_name}.", ephemeral=True
            )
            return

        view = PropertiesSelectView(self.project_id, files)
        embed = discord.Embed(
            title=f".properties — {project_name}",
            description="Выберите файл для просмотра/редактирования:",
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=1)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к списку проектов."""
        view = PipelineProjectSelectView()
        embed = discord.Embed(
            title="Пайплайны",
            description="Выберите проект:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class PipelineHistoryView(discord.ui.View):
    """Кнопка обновления истории пайплайнов."""

    def __init__(self, project_id: str) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Перезагрузить историю."""
        await interaction.response.defer(ephemeral=True)
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")

        try:
            pipelines_list = await get_pipelines(self.project_id)
        except Exception as e:
            logger.error(f"Ошибка получения пайплайнов: {e}")
            await interaction.followup.send("Ошибка при обращении к GitLab API.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"История пайплайнов — {project_name}",
            color=discord.Color.blurple(),
        )

        for pipeline in (pipelines_list or [])[:5]:
            emoji = STATUS_EMOJI.get(pipeline["status"], "\u2753")
            try:
                details = await get_pipeline_details(self.project_id, pipeline["id"])
                updated_at = details.get("updated_at", "") if details else ""
                dt = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                time_str = dt.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                time_str = "—"

            embed.add_field(
                name=f"{emoji} #{pipeline['id']} — {pipeline['status']}",
                value=f"Ветка: `{pipeline['ref']}`\nОбновлён: {time_str}",
                inline=False,
            )

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=0)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к опциям проекта."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# --- Расписания ---

class SchedulesView(discord.ui.View):
    """Список расписаний с кнопкой запуска через Select."""

    def __init__(self, project_id: str, schedules: list) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id
        self.schedules = {str(s["id"]): s for s in schedules}

        options = [
            discord.SelectOption(
                label=s.get("description", "Без описания")[:100],
                value=str(s["id"]),
                description=f"Cron: {s['cron']} | {'Активен' if s['active'] else 'Неактивен'}",
            )
            for s in schedules
        ]
        if options:
            self.schedule_select.options = options
        else:
            self.remove_item(self.schedule_select)

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Выберите расписание для запуска...",
        row=0,
    )
    async def schedule_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        """Показать детали расписания и кнопку запуска."""
        schedule_id = select.values[0]
        schedule = self.schedules.get(schedule_id, {})
        desc = schedule.get("description", "Без описания")
        cron = schedule.get("cron", "—")
        ref = schedule.get("ref", "—").replace("refs/heads/", "")

        embed = discord.Embed(
            title=f"Расписание: {desc}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Cron", value=f"`{cron}`", inline=True)
        embed.add_field(name="Ветка", value=f"`{ref}`", inline=True)
        embed.add_field(name="ID", value=f"`{schedule_id}`", inline=True)

        view = ScheduleConfirmView(self.project_id, schedule_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=1)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к опциям проекта."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ScheduleConfirmView(discord.ui.View):
    """Подтверждение запуска расписания."""

    def __init__(self, project_id: str, schedule_id: str) -> None:
        super().__init__(timeout=60)
        self.project_id = project_id
        self.schedule_id = schedule_id

    @discord.ui.button(label="Запустить", style=discord.ButtonStyle.success, row=0)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Запуск расписания пайплайна."""
        await interaction.response.defer(ephemeral=True)

        try:
            success = await play_pipeline_schedule(self.project_id, self.schedule_id)
        except Exception as e:
            logger.error(f"Ошибка запуска расписания: {e}")
            success = False

        if success:
            embed = discord.Embed(
                title="Пайплайн запущен",
                description=f"Расписание `{self.schedule_id}` успешно запущено.",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="Ошибка запуска",
                description="Не удалось запустить пайплайн.",
                color=discord.Color.red(),
            )

        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Отмена запуска."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# --- Allure-отчёты ---

async def _build_allure_page(project_id: str, page: int = 1, limit: int = 5) -> tuple[discord.Embed, discord.ui.View]:
    """Строит embed и view для страницы Allure-отчётов."""
    project_name = FIXED_PROJECTS.get(project_id, "Проект")
    offset = (page - 1) * limit

    conn = await connect_to_db()
    if not conn:
        embed = discord.Embed(title="Ошибка", description="Нет подключения к БД.", color=discord.Color.red())
        return embed, discord.ui.View()

    try:
        rows = await conn.fetch(
            """
            SELECT pipeline_id, ref, status, stand, allure_report_url,
                   tests_passed, tests_failed, duration_sec, updated_at
            FROM pipeline_states
            WHERE project_id = $1
              AND allure_report_url IS NOT NULL
              AND status IN ('success', 'failed')
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3;
            """,
            project_id, limit, offset,
        )

        total_row = await conn.fetchrow(
            "SELECT COUNT(*) FROM pipeline_states WHERE project_id = $1 AND allure_report_url IS NOT NULL",
            project_id,
        )
        total = total_row[0] if total_row else 0
    finally:
        await conn.close()

    if not rows:
        embed = discord.Embed(
            title=f"Allure-отчёты — {project_name}",
            description="Нет доступных отчётов.",
            color=discord.Color.yellow(),
        )
        return embed, discord.ui.View()

    embed = discord.Embed(
        title=f"Allure-отчёты — {project_name}",
        description=f"Страница {page} (всего: {total})",
        color=discord.Color.blurple(),
    )

    for r in rows:
        emoji = STATUS_EMOJI.get(r["status"], "\u2753")
        passed = r["tests_passed"] or 0
        failed = r["tests_failed"] or 0
        duration = (r["duration_sec"] or 0) // 60
        dt = r["updated_at"]
        time_str = dt.strftime("%d.%m %H:%M") if dt else "—"
        url = r["allure_report_url"]
        stand = r["stand"] or "—"

        embed.add_field(
            name=f"{emoji} #{r['pipeline_id']} | {stand}",
            value=(
                f"Passed: {passed} | Failed: {failed} | {duration}м\n"
                f"{time_str} | [Отчёт]({url})"
            ),
            inline=False,
        )

    has_prev = page > 1
    has_next = total > page * limit
    view = AllureReportsView(project_id, page, has_prev, has_next)
    return embed, view


class AllureReportsView(discord.ui.View):
    """Пагинация Allure-отчётов."""

    def __init__(self, project_id: str, page: int, has_prev: bool, has_next: bool) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id
        self.page = page

        if not has_prev:
            self.prev_button.disabled = True
        if not has_next:
            self.next_button.disabled = True

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Предыдущая страница."""
        await interaction.response.defer(ephemeral=True)
        embed, view = await _build_allure_page(self.project_id, self.page - 1)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Следующая страница."""
        await interaction.response.defer(ephemeral=True)
        embed, view = await _build_allure_page(self.project_id, self.page + 1)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=0)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к опциям проекта."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# --- .properties ---

class PropertiesSelectView(discord.ui.View):
    """Выбор .properties файла для просмотра/редактирования."""

    def __init__(self, project_id: str, files: list[str]) -> None:
        super().__init__(timeout=180)
        self.project_id = project_id
        options = [
            discord.SelectOption(label=f, value=f)
            for f in files[:25]
        ]
        self.file_select.options = options

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Выберите файл...",
        row=0,
    )
    async def file_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        """Показать содержимое файла."""
        file_name = select.values[0]
        full_path = f"src/test/resources/{file_name}"

        await interaction.response.defer(ephemeral=True)

        try:
            content = await get_file_content(self.project_id, full_path)
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            await interaction.followup.send("Ошибка при загрузке файла.", ephemeral=True)
            return

        if not content or not content.strip():
            await interaction.followup.send("Файл пуст или не найден.", ephemeral=True)
            return

        # Обрезаем до 4000 символов для embed
        display_content = content.strip()[:3900]

        embed = discord.Embed(
            title=f"Файл: {file_name}",
            description=f"```properties\n{display_content}\n```",
            color=discord.Color.blurple(),
        )

        view = PropertyFileView(self.project_id, file_name, content)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=1)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к опциям проекта."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class PropertyFileView(discord.ui.View):
    """Просмотр и редактирование .properties файла."""

    def __init__(self, project_id: str, file_name: str, content: str) -> None:
        super().__init__(timeout=300)
        self.project_id = project_id
        self.file_name = file_name
        self.original_content = content

    @discord.ui.button(label="Редактировать", style=discord.ButtonStyle.primary, row=0)
    async def edit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Открыть модальное окно для редактирования."""
        modal = PropertyEditModal(
            self.project_id, self.file_name, self.original_content
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.danger, row=0)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Вернуться к опциям проекта."""
        project_name = FIXED_PROJECTS.get(self.project_id, "Проект")
        view = PipelineOptionsView(self.project_id)
        embed = discord.Embed(
            title=f"Пайплайны — {project_name}",
            description="Выберите действие:",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class PropertyEditModal(discord.ui.Modal, title="Редактирование .properties"):
    """Modal для редактирования .properties файла.

    Пользователь вводит строки ключ=значение — они мержатся с оригиналом.
    """

    changes = discord.ui.TextInput(
        label="Изменения (ключ=значение, по одному на строку)",
        style=discord.TextStyle.paragraph,
        placeholder="base.url=https://example.com\ntimeout=30",
        required=True,
        max_length=4000,
    )

    def __init__(self, project_id: str, file_name: str, original_content: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.file_name = file_name
        self.original_content = original_content

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Применить изменения и показать diff."""
        new_lines = self.changes.value.strip().split("\n")
        original_lines = self.original_content.split("\n")

        # Парсим оригинал
        original_dict: dict[str, str] = {}
        for line in original_lines:
            stripped = line.strip()
            if "=" in line and not stripped.startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key:
                    original_dict[key] = line

        # Применяем изменения
        updated_dict = original_dict.copy()
        changes_applied: list[str] = []
        for line in new_lines:
            stripped = line.strip()
            if "=" in line and not stripped.startswith("#"):
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key:
                    updated_dict[key] = f"{key}={value}"
                    changes_applied.append(f"`{key}` = `{value}`")

        # Собираем итоговое содержимое
        updated_content: list[str] = []
        for line in original_lines:
            stripped = line.strip()
            if "=" in line and not stripped.startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key in updated_dict:
                    updated_content.append(updated_dict[key])
                else:
                    updated_content.append(line)
            else:
                updated_content.append(line)

        new_content = "\n".join(updated_content)

        if not changes_applied:
            await interaction.response.send_message(
                "Не обнаружено корректных изменений.", ephemeral=True
            )
            return

        # Показываем diff + кнопку сохранения
        diff_text = "\n".join(changes_applied)
        embed = discord.Embed(
            title=f"Изменения в {self.file_name}",
            description=f"**Обновлённые ключи:**\n{diff_text}",
            color=discord.Color.yellow(),
        )

        view = PropertySaveView(self.project_id, self.file_name, new_content)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PropertySaveView(discord.ui.View):
    """Подтверждение сохранения .properties файла."""

    def __init__(self, project_id: str, file_name: str, new_content: str) -> None:
        super().__init__(timeout=120)
        self.project_id = project_id
        self.file_name = file_name
        self.new_content = new_content

    @discord.ui.button(label="Сохранить", style=discord.ButtonStyle.success, row=0)
    async def save_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Сохранить файл через GitLab API."""
        await interaction.response.defer(ephemeral=True)
        full_path = f"src/test/resources/{self.file_name}"

        try:
            success = await update_file_content(self.project_id, full_path, self.new_content)
        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            success = False

        if success:
            embed = discord.Embed(
                title="Файл сохранён",
                description=f"`{self.file_name}` успешно обновлён.",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="Ошибка сохранения",
                description="Не удалось сохранить файл через GitLab API.",
                color=discord.Color.red(),
            )

        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Отменить сохранение."""
        await interaction.response.edit_message(
            content="Сохранение отменено.", embed=None, view=None
        )
